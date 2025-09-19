"""Paper subtopic classification using heuristics with optional LLM fallback."""

from __future__ import annotations

import json
from collections.abc import Sequence
from functools import lru_cache

from newsletter.io.models import ClassifiedArticle, MetadataRecord, PrimaryTopic
from newsletter.services.openrouter_client import OpenRouterClient

SUPPORTED_SUBTOPICS = (
    "LLM",
    "Agents",
    "Multimodal",
    "RL",
    "System/Engineering",
    "Retrieval/RAG",
    "Evaluation",
    "Data/Synthetic Data",
    "Safety/Alignment",
)

RULE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "LLM": ("language model", "llm", "gpt", "transformer"),
    "Agents": ("agent", "tool use", "autonomous"),
    "Multimodal": ("multimodal", "vision-language", "image caption"),
    "RL": ("reinforcement learning", "policy gradient", "rl"),
    "System/Engineering": ("throughput", "latency", "system", "inference engine"),
    "Retrieval/RAG": ("retrieval", "rag", "retriever", "vector store"),
    "Evaluation": ("benchmark", "evaluation", "metrics"),
    "Data/Synthetic Data": ("dataset", "data generation", "synthetic data"),
    "Safety/Alignment": ("alignment", "safety", "guardrail", "red teaming"),
}


class SubtopicClassifier:
    """Assign a single paper subtopic using heuristics with optional LLM."""

    def __init__(self, llm_client: OpenRouterClient | None = None) -> None:
        self._llm_client = llm_client

    def classify(
        self, article: ClassifiedArticle, metadata: MetadataRecord | None = None
    ) -> list[str]:
        if article.topic is not PrimaryTopic.PAPERS:
            return []

        heuristic_match = _apply_rule_keywords(article.content.text, metadata)
        if heuristic_match:
            return [heuristic_match]

        if self._llm_client is None:
            return []

        response = self._llm_client.complete(
            _build_messages(article, metadata), response_format={"type": "json_object"}
        )
        parsed = _parse_subtopics_response(response)
        return parsed[:1]


def _apply_rule_keywords(text: str, metadata: MetadataRecord | None) -> str | None:
    lower_text = text.lower()
    for subtopic in SUPPORTED_SUBTOPICS:
        keywords = RULE_KEYWORDS.get(subtopic, ())
        if any(keyword in lower_text for keyword in keywords):
            return subtopic

    if metadata and metadata.recommendation:
        recommendation_text = metadata.recommendation.lower()
        for subtopic in SUPPORTED_SUBTOPICS:
            keywords = RULE_KEYWORDS.get(subtopic, ())
            if any(keyword in recommendation_text for keyword in keywords):
                return subtopic

    return None


def _build_messages(
    article: ClassifiedArticle, metadata: MetadataRecord | None
) -> list[dict[str, str]]:
    snippet_lines = [article.content.text[:1000]]
    if metadata:
        snippet_lines.append(metadata.recommendation)
    snippet = "\n".join(snippet_lines)
    system_prompt = (
        "Classify the research paper into exactly one best-fit subtopic. Use the candidate list and only "
        "introduce a new label if none apply. Return a JSON object with `subtopics` as an array containing a "
        "single string."
    )
    user_prompt = (
        f"Candidate subtopics: {', '.join(SUPPORTED_SUBTOPICS)}\n"
        f"Title: {article.content.title or 'Unknown'}\n"
        f"Content snippet:\n{snippet}"
    )
    return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]


def _parse_subtopics_response(response: str) -> list[str]:
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        return []

    if isinstance(data, dict) and isinstance(data.get("subtopics"), list):
        return _normalize_subtopics(data["subtopics"])
    if isinstance(data, list):
        return _normalize_subtopics(data)
    return []


@lru_cache(maxsize=32)
def _normalize_label(label: str) -> str:
    cleaned = label.strip()
    if not cleaned:
        return ""
    for candidate in SUPPORTED_SUBTOPICS:
        if cleaned.lower() == candidate.lower():
            return candidate
    return cleaned


def _normalize_subtopics(candidates: Sequence[str]) -> list[str]:
    normalized: list[str] = []
    for entry in candidates:
        if not isinstance(entry, str):
            continue
        label = _normalize_label(entry)
        if label and label not in normalized:
            normalized.append(label)
    return normalized


__all__ = ["SubtopicClassifier", "SUPPORTED_SUBTOPICS"]
