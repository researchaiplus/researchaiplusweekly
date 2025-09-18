"""Markdown renderer for newsletter entries."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime
from pathlib import Path

from newsletter.io.models import NewsletterEntry, PrimaryTopic

TOPIC_HEADERS = {
    PrimaryTopic.PAPERS: "### 📄 Papers",
    PrimaryTopic.BLOGS: "### ✍️ Blogs",
    PrimaryTopic.OPEN_SOURCE: "### 🛠️ Open Source",
    PrimaryTopic.ENGINEERING_PRODUCT_BUSINESS: "### 🏢 Engineering & Product & Business",
    PrimaryTopic.UNKNOWN: "### ❓ Uncategorized",
}


class MarkdownRenderer:
    """Render newsletter entries into PRD-compliant Markdown."""

    def render(self, entries: Sequence[NewsletterEntry]) -> str:
        grouped = self._group_by_topic(entries)
        sections: list[str] = []

        for topic in self._topic_order():
            topic_entries = grouped.get(topic)
            if not topic_entries:
                continue
            sections.append(TOPIC_HEADERS.get(topic, f"### {topic.value}"))
            if topic is PrimaryTopic.PAPERS:
                sections.append(self._render_paper_subsections(topic_entries))
            else:
                sections.append(self._render_entries(topic_entries))

        return "\n\n".join(section.strip() for section in sections if section).strip() + "\n"

    def write(
        self, entries: Sequence[NewsletterEntry], output_dir: Path, filename: str | None = None
    ) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        final_name = filename or f"newsletter_{timestamp}.md"
        output_path = output_dir / final_name
        output_path.write_text(self.render(entries), encoding="utf-8")
        return output_path

    @staticmethod
    def _group_by_topic(
        entries: Sequence[NewsletterEntry],
    ) -> dict[PrimaryTopic, list[NewsletterEntry]]:
        grouped: dict[PrimaryTopic, list[NewsletterEntry]] = defaultdict(list)
        for entry in entries:
            grouped[entry.topic].append(entry)
        return grouped

    @staticmethod
    def _topic_order() -> Iterable[PrimaryTopic]:
        return (
            PrimaryTopic.PAPERS,
            PrimaryTopic.BLOGS,
            PrimaryTopic.OPEN_SOURCE,
            PrimaryTopic.ENGINEERING_PRODUCT_BUSINESS,
            PrimaryTopic.UNKNOWN,
        )

    def _render_paper_subsections(self, entries: Sequence[NewsletterEntry]) -> str:
        buckets: dict[str, list[NewsletterEntry]] = defaultdict(list)
        for entry in entries:
            subtopics = entry.subtopics or entry.metadata.subtopics or ["General"]
            for subtopic in subtopics:
                buckets[subtopic].append(entry)

        lines: list[str] = []
        for subtopic in sorted(buckets):
            lines.append(f"#### {subtopic}")
            lines.append(self._render_entries(buckets[subtopic]))
        return "\n\n".join(lines)

    @staticmethod
    def _render_entries(entries: Sequence[NewsletterEntry]) -> str:
        blocks: list[str] = []
        for entry in entries:
            metadata = entry.metadata
            block_lines = [f"**{metadata.title}**"]
            block_lines.append(f"Link: {entry.source_url}")
            if metadata.authors:
                block_lines.append("Authors: " + ", ".join(metadata.authors))
            if metadata.organizations:
                block_lines.append("Organizations: " + ", ".join(metadata.organizations))
            block_lines.append(f"Recommendation: {metadata.recommendation}")
            if metadata.repositories:
                block_lines.append("Repositories: " + ", ".join(metadata.repositories))
            if metadata.datasets:
                block_lines.append("Datasets: " + ", ".join(metadata.datasets))
            if metadata.attachments:
                block_lines.append("Attachments: " + ", ".join(metadata.attachments))
            blocks.append("  \n".join(block_lines))
        return "\n\n".join(blocks)


__all__ = ["MarkdownRenderer"]
