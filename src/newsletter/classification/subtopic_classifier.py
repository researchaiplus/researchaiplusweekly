"""LLM-powered subtopic classification for research papers."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence

from newsletter.io.models import NewsletterEntry, PrimaryTopic
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


class SubtopicClassifier:
    """Classify paper entries into subtopics using a single batched LLM call."""

    def __init__(
        self,
        llm_client: OpenRouterClient | None = None,
        supported_subtopics: Iterable[str] = SUPPORTED_SUBTOPICS,
    ) -> None:
        self._llm_client = llm_client
        self._supported_subtopics = tuple(supported_subtopics)

    def assign_subtopics(self, entries: Sequence[NewsletterEntry]) -> None:
        if self._llm_client is None:
            return

        papers = [entry for entry in entries if entry.topic is PrimaryTopic.PAPERS]
        if not papers:
            return

        messages = _build_messages(papers, self._supported_subtopics)
        try:
            response = self._llm_client.complete(messages, response_format={"type": "json_object"})
        except Exception:  # pragma: no cover - handled upstream when wired with real client
            return

        mapping = _parse_response(response, papers, self._supported_subtopics)
        for entry in papers:
            subtopics = mapping.get(entry.source_url) or mapping.get(entry.metadata.title)
            if not subtopics:
                entry.subtopics = []
                entry.metadata = entry.metadata.model_copy(update={"subtopics": []})
                continue
            entry.subtopics = subtopics
            entry.metadata = entry.metadata.model_copy(update={"subtopics": subtopics})


def _build_messages(
    papers: Sequence[NewsletterEntry], supported_subtopics: Iterable[str]
) -> list[dict[str, str]]:
    options = ", ".join(supported_subtopics)
    header_lines = ["You classify machine learning papers into subtopics for a weekly newsletter." ]
    header_lines.append(
        "For each paper, choose the best-fitting subtopic from the allowed list. If none fit, invent a concise new label."
    )
    header_lines.append(
        "Respond with JSON: {\"classifications\": [{\"id\": <number>, \"subtopics\": [\"label\"]}]}"
    )
    header_lines.append(
        "Choose at most one subtopic per paper unless two are clearly necessary."
    )
    header_lines.append(f"Allowed subtopics: {options}")

    lines = ["Papers:"]
    for index, entry in enumerate(papers, start=1):
        lines.append(f"Item {index}:")
        lines.append(f"Title: {entry.metadata.title}")
        lines.append(f"Recommendation: {entry.metadata.recommendation}")

    instructions = "\n".join(header_lines)
    user_content = "\n".join(lines)
    return [
        {"role": "system", "content": instructions},
        {"role": "user", "content": user_content},
    ]


def _parse_response(
    response: str,
    papers: Sequence[NewsletterEntry],
    supported_subtopics: Iterable[str],
) -> dict[str, list[str]]:
    try:
        data = json.loads(response)
    except json.JSONDecodeError:
        return {}

    if isinstance(data, dict) and "classifications" in data:
        payload = data.get("classifications", [])
    elif isinstance(data, list):
        payload = data
    else:
        payload = []

    allowed = {topic.lower(): topic for topic in supported_subtopics}
    mapping: dict[str, list[str]] = {}
    indexed_lookup = {str(i): entry for i, entry in enumerate(papers, start=1)}

    for item in payload:
        if not isinstance(item, dict):
            continue
        identifier = item.get("id")
        if identifier is None:
            continue
        entry = indexed_lookup.get(str(identifier))
        if entry is None:
            continue
        subtopics_field = item.get("subtopics")
        if not isinstance(subtopics_field, list):
            continue
        normalized = _normalize_subtopics(subtopics_field, allowed)
        if normalized:
            mapping[entry.source_url] = normalized

    return mapping


def _normalize_subtopics(candidates: Sequence[str], allowed: dict[str, str]) -> list[str]:
    normalized: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        cleaned = candidate.strip()
        if not cleaned:
            continue
        lookup = allowed.get(cleaned.lower())
        label = lookup or cleaned
        if label not in normalized:
            normalized.append(label)
    if len(normalized) > 1:
        return normalized[:2]
    return normalized


__all__ = ["SubtopicClassifier", "SUPPORTED_SUBTOPICS"]
