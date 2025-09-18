"""Metadata extraction and recommendation generation via OpenRouter."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from pydantic import BaseModel, Field, ValidationError

from newsletter.io.models import ClassifiedArticle, MetadataRecord, PrimaryTopic
from newsletter.services.openrouter_client import OpenRouterClient, OpenRouterError

LOGGER = logging.getLogger(__name__)

REPOSITORY_HOSTS = ("github.com", "gitlab.com", "huggingface.co")
DATASET_HINTS = ("dataset", "corpus", "benchmark")
ATTACHMENT_HINTS = ("slides", "appendix", "supplementary")


class MetadataExtractionError(RuntimeError):
    """Raised when the metadata extractor cannot obtain valid data."""


class _LLMMetadata(BaseModel):
    title: str
    authors: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    recommendation: str
    subtopics: list[str] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)


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
        return MetadataRecord(
            topic=article.topic,
            title=payload.title.strip(),
            authors=[author.strip() for author in payload.authors if author.strip()],
            organizations=[org.strip() for org in payload.organizations if org.strip()],
            recommendation=recommendation,
            subtopics=self._normalize_subtopics(article.topic, payload.subtopics),
            attachments=[
                attachment.strip() for attachment in payload.attachments if attachment.strip()
            ],
        )

    def _enrich_with_detections(
        self, article: ClassifiedArticle, record: MetadataRecord
    ) -> MetadataRecord:
        detected_repos = _detect_links(article.content.text, REPOSITORY_HOSTS)
        detected_datasets = _detect_keywords(article.content.text, DATASET_HINTS)
        return record.model_copy(
            update={"repositories": detected_repos, "datasets": detected_datasets}
        )

    def _annotate_missing_optional(self, record: MetadataRecord) -> MetadataRecord:
        missing: list[str] = []
        if not record.repositories:
            missing.append("repositories")
        if not record.datasets:
            missing.append("datasets")
        if not record.attachments:
            missing.append("attachments")
        if missing:
            LOGGER.info("Metadata missing optional fields: %s", ", ".join(missing))
        return record.model_copy(update={"missing_optional_fields": missing})

    def _build_messages(self, article: ClassifiedArticle) -> list[dict[str, str]]:
        snippet = article.content.text[: self._config.max_snippet_chars]
        instructions = (
            "You extract structured newsletter metadata for AI research and product updates. "
            "Return a JSON object with the keys: title (string), authors (array of strings), organizations "
            "(array of strings), recommendation (<=100 words string), subtopics (array of strings), attachments "
            "(array of strings). Use plain names without extra punctuation."
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


def _detect_links(text: str, hosts: Iterable[str]) -> list[str]:
    pattern = re.compile(r"https?://[^\s)]+", flags=re.IGNORECASE)
    links = []
    for match in pattern.findall(text):
        if any(host in match for host in hosts):
            links.append(match.rstrip(".,"))
    return links


def _detect_keywords(text: str, keywords: Iterable[str]) -> list[str]:
    lowered = text.lower()
    results = []
    for keyword in keywords:
        if keyword in lowered:
            results.append(keyword)
    return results


__all__ = ["MetadataExtractor", "MetadataExtractionError", "ExtractionConfig"]
