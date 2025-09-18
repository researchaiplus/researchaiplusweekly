from pathlib import Path

from newsletter.io.models import MetadataRecord, NewsletterEntry, PrimaryTopic
from newsletter.pipeline.markdown_renderer import MarkdownRenderer


def _entry(topic: PrimaryTopic, title: str, subtopics: list[str] | None = None) -> NewsletterEntry:
    metadata = MetadataRecord(
        topic=topic,
        title=title,
        authors=["Author A"],
        organizations=["Org"],
        recommendation="Insightful work",
        subtopics=subtopics or [],
        repositories=[],
        datasets=[],
        attachments=[],
        missing_optional_fields=[],
    )
    return NewsletterEntry(
        source_url="https://example.com", metadata=metadata, topic=topic, subtopics=subtopics or []
    )


def test_markdown_renderer_groups_papers() -> None:
    renderer = MarkdownRenderer()
    entries = [
        _entry(PrimaryTopic.PAPERS, "Paper A", ["LLM"]),
        _entry(PrimaryTopic.OPEN_SOURCE, "Repo A"),
    ]

    output = renderer.render(entries)

    assert "### 📄 Papers" in output
    assert "#### LLM" in output
    assert "### 🛠️ Open Source" in output


def test_markdown_renderer_writes_file(tmp_path: Path) -> None:
    renderer = MarkdownRenderer()
    entry = _entry(PrimaryTopic.BLOGS, "Blog Post")

    destination = tmp_path / "output"
    written = renderer.write([entry], destination)

    assert written.parent == destination
    assert written.read_text(encoding="utf-8").startswith("### ✍️ Blogs")
