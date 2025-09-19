"""Metadata extraction and recommendation generation via OpenRouter."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from urllib.parse import urlparse

from pydantic import AnyHttpUrl, BaseModel, Field, ValidationError

from newsletter.io.models import (
    ClassifiedArticle,
    MetadataRecord,
    PrimaryTopic,
    RepositoryReference,
)
from newsletter.services.openrouter_client import OpenRouterClient, OpenRouterError

LOGGER = logging.getLogger(__name__)

DATASET_HINTS = ("dataset", "corpus", "benchmark")


class MetadataExtractionError(RuntimeError):
    """Raised when the metadata extractor cannot obtain valid data."""


class _LLMRepository(BaseModel):
    url: AnyHttpUrl
    provider: str = Field(description="Repository provider, e.g., github, huggingface-model, huggingface-dataset")
    reason: str = Field(description="Short justification linking the repository to the paper.")


class _LLMMetadata(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    recommendation: str
    subtopics: list[str] = Field(default_factory=list)
    repositories: list[_LLMRepository] = Field(default_factory=list)


@dataclass(slots=True)
class ExtractionConfig:
    max_attempts: int = 2
    max_snippet_chars: int = 1600
    recommendation_word_limit: int = 100


class MetadataExtractor:
    """Extract metadata and recommendation text for classified articles."""

    def __init__(self, client: OpenRouterClient, config: ExtractionConfig | None = None) -> None:
        self._client = client
        self._config = config or ExtractionConfig()

    def extract(self, article: ClassifiedArticle) -> MetadataRecord:
        payload = self._request_metadata(article)
        record = self._build_record(article, payload)
        record = self._add_repository_references(record, payload.repositories, article)
        enriched = self._enrich_with_detections(article, record)
        enriched = self._annotate_missing_optional(enriched)
        return enriched

    def _request_metadata(self, article: ClassifiedArticle) -> _LLMMetadata:
        attempts = self._config.max_attempts
        messages = self._build_messages(article)
        for attempt in range(1, attempts + 1):
            try:
                content = self._client.complete(messages, response_format={"type": "json_object"})
                data = json.loads(content)
                return _LLMMetadata.model_validate(data)
            except (OpenRouterError, json.JSONDecodeError, ValidationError) as exc:
                LOGGER.warning(
                    "Metadata extraction attempt %s/%s failed: %s", attempt, attempts, exc
                )
                if attempt == attempts:
                    raise MetadataExtractionError("Unable to parse structured metadata") from exc
        raise MetadataExtractionError("Metadata extraction attempt loop exited unexpectedly")

    def _build_record(self, article: ClassifiedArticle, payload: _LLMMetadata) -> MetadataRecord:
        recommendation = _truncate_words(
            payload.recommendation, self._config.recommendation_word_limit
        )
        organizations = _unique_ordered(payload.organizations)
        return MetadataRecord(
            topic=article.topic,
            title=payload.title.strip(),
            authors=[author.strip() for author in payload.authors if author.strip()],
            organizations=organizations,
            recommendation=recommendation,
            subtopics=self._normalize_subtopics(article.topic, payload.subtopics),
        )

    def _add_repository_references(
        self,
        record: MetadataRecord,
        repositories: list[_LLMRepository],
        article: ClassifiedArticle,
    ) -> MetadataRecord:
        references: list[RepositoryReference] = []
        seen: set[str] = set()
        for repo in repositories:
            provider = _normalize_provider(repo.provider, repo.url)
            if provider is None:
                continue
            url = str(repo.url)
            if url in seen:
                continue
            seen.add(url)
            reason = repo.reason.strip() or "Provided by LLM metadata extraction"
            references.append(RepositoryReference(url=url, provider=provider, reason=reason))

        if not references:
            # Fallback to text-based detection if the LLM did not return repositories.
            references = _detect_repositories(article.content.text)

        return record.model_copy(update={"repositories": references})

    def _enrich_with_detections(
        self, article: ClassifiedArticle, record: MetadataRecord
    ) -> MetadataRecord:
        detected_datasets = _detect_keywords(article.content.text, DATASET_HINTS)
        existing_urls = {str(ref.url) for ref in record.repositories}
        if not record.repositories:
            # Try to backfill repositories if none captured yet.
            fallback_repos = _detect_repositories(article.content.text)
            record = record.model_copy(update={"repositories": fallback_repos})
            existing_urls = {str(ref.url) for ref in record.repositories}
        else:
            # Ensure fallback doesn't add duplicates but may find extras.
            for fallback in _detect_repositories(article.content.text):
                if str(fallback.url) not in existing_urls:
                    existing_urls.add(str(fallback.url))
                    record.repositories.append(fallback)

        return record.model_copy(update={"datasets": detected_datasets})

    def _annotate_missing_optional(self, record: MetadataRecord) -> MetadataRecord:
        missing: list[str] = []
        if not record.repositories:
            missing.append("repositories")
        if not record.datasets:
            missing.append("datasets")
        if missing:
            LOGGER.info("Metadata missing optional fields: %s", ", ".join(missing))
        return record.model_copy(update={"missing_optional_fields": missing})

    def _build_messages(self, article: ClassifiedArticle) -> list[dict[str, str]]:
        snippet = article.content.text[: self._config.max_snippet_chars]
        instructions = (
            "You extract structured newsletter metadata for AI research and product updates. "
            "Return a JSON object with the keys: title (string), authors (array of strings), organizations "
            "(array of strings capturing author affiliations), recommendation (<=100 words string), subtopics "
            "(array of strings), repositories (array of objects with url, provider, reason). "
            "Only include repositories when you are confident they are official resources for this paper: "
            "GitHub code, Hugging Face models, or Hugging Face datasets. Use provider values 'github', "
            "'huggingface-model', or 'huggingface-dataset'. Provide the full URL and a concise reason pointing to "
            "the evidence in the content."
        )
        user_prompt = (
            f"Primary topic: {article.topic.value}\n"
            f"Title: {article.content.title or 'Unknown'}\n"
            f"URL: {article.content.url}\n"
            f"Content snippet:\n{snippet}"
        )
        return [
            {"role": "system", "content": instructions},
            {"role": "user", "content": user_prompt},
        ]

    @staticmethod
    def _normalize_subtopics(topic: PrimaryTopic, subtopics: Sequence[str]) -> list[str]:
        if topic is not PrimaryTopic.PAPERS:
            return []
        normalized: list[str] = []
        for entry in subtopics:
            cleaned = entry.strip()
            if cleaned:
                normalized.append(cleaned)
        return normalized


def _truncate_words(text: str, limit: int) -> str:
    words = text.split()
    if len(words) <= limit:
        return text.strip()
    truncated = " ".join(words[:limit])
    LOGGER.info("Truncated recommendation from %s to %s words", len(words), limit)
    return truncated + "…"


def _unique_ordered(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            ordered.append(cleaned)
    return ordered


def _detect_repositories(text: str) -> list[RepositoryReference]:
    pattern = re.compile(r"https?://[^\s)]+", flags=re.IGNORECASE)
    references: list[RepositoryReference] = []
    seen: set[str] = set()
    for match in pattern.finditer(text):
        cleaned = match.group(0).rstrip(".,")
        parsed = _ParsedUrl.from_text(cleaned)
        if parsed is None:
            continue
        if parsed.domain in {"github.com", "www.github.com"}:
            repo = parsed.github_repo()
            if repo and repo not in seen:
                seen.add(repo)
                references.append(
                    RepositoryReference(
                        url=repo,
                        provider="github",
                        reason=_build_repository_reason(text, match.start()),
                    )
                )
        elif parsed.domain in {"huggingface.co", "www.huggingface.co"}:
            repo = parsed.huggingface_repo()
            if repo and repo not in seen:
                seen.add(repo)
                references.append(
                    RepositoryReference(
                        url=repo,
                        provider=_resolve_huggingface_provider(parsed),
                        reason=_build_repository_reason(text, match.start()),
                    )
                )
    return references


def _detect_keywords(text: str, keywords: Iterable[str]) -> list[str]:
    lowered = text.lower()
    results = []
    for keyword in keywords:
        if keyword in lowered:
            results.append(keyword)
    return results


def _normalize_provider(provider: str, url: AnyHttpUrl) -> str | None:
    normalized = provider.strip().lower().replace(" ", "-")
    if normalized in {"github", "github.com"}:
        return "github"
    if normalized in {"huggingface", "huggingface.co", "hf"}:
        return _resolve_huggingface_provider(_ParsedUrl.from_text(str(url)))
    if normalized.startswith("huggingface-"):
        category = normalized.split("-", 1)[1]
        if category in {"models", "model", "datasets", "dataset", "spaces", "space"}:
            return f"huggingface-{_normalize_hf_category(category)}"
        return "huggingface"
    if normalized in {"model", "dataset"}:
        # assume huggingface reference if url matches domain
        parsed = _ParsedUrl.from_text(str(url))
        if parsed and parsed.domain.endswith("huggingface.co"):
            return _resolve_huggingface_provider(parsed)
    # Unknown provider; ignore to stay precise
    return None


def _normalize_hf_category(category: str) -> str:
    category = category.lower()
    if category in {"model", "models"}:
        return "model"
    if category in {"dataset", "datasets"}:
        return "dataset"
    if category in {"space", "spaces"}:
        return "space"
    return category


def _build_repository_reason(text: str, index: int, window: int = 80) -> str:
    start = max(0, index - window)
    end = min(len(text), index + window)
    snippet = " ".join(text[start:end].split())
    return f"Referenced in article content near: '{snippet}'"


class _ParsedUrl:
    __slots__ = ("domain", "path_parts")

    def __init__(self, domain: str, path_parts: list[str]) -> None:
        self.domain = domain
        self.path_parts = path_parts

    @staticmethod
    def from_text(url: str) -> "_ParsedUrl" | None:
        try:
            parsed = urlparse(url)
        except ValueError:
            return None
        domain = parsed.netloc.lower()
        if not domain:
            return None
        parts = [part for part in parsed.path.split("/") if part]
        return _ParsedUrl(domain, parts)

    def github_repo(self) -> str | None:
        if len(self.path_parts) < 2:
            return None
        owner, repo = self.path_parts[:2]
        if owner and repo:
            return f"https://github.com/{owner}/{repo.removesuffix('.git')}"
        return None

    def huggingface_repo(self) -> str | None:
        if not self.path_parts:
            return None
        first = self.path_parts[0]
        if first in {"datasets", "models", "spaces"}:
            if len(self.path_parts) >= 3:
                category, owner, name = self.path_parts[:3]
                return f"https://huggingface.co/{category}/{owner}/{name.removesuffix('.git')}"
            return None
        if len(self.path_parts) >= 2:
            owner, name = self.path_parts[:2]
            return f"https://huggingface.co/{owner}/{name.removesuffix('.git')}"
        return None

    def huggingface_category(self) -> str | None:
        if not self.path_parts:
            return None
        first = self.path_parts[0].lower()
        if first in {"datasets", "models", "spaces"}:
            return _normalize_hf_category(first)
        return "model"


def _resolve_huggingface_provider(parsed: _ParsedUrl | None) -> str:
    if parsed is None:
        return "huggingface-model"
    category = parsed.huggingface_category() or "model"
    return f"huggingface-{category}"


__all__ = ["MetadataExtractor", "MetadataExtractionError", "ExtractionConfig"]
