import json

from newsletter.classification.subtopic_classifier import SubtopicClassifier
from newsletter.io.models import MetadataRecord, NewsletterEntry, PrimaryTopic, RepositoryReference


class StubLLM:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls = 0

    def complete(self, messages, response_format=None):  # type: ignore[override]
        self.calls += 1
        return self.payload


def _paper_entry(title: str, recommendation: str = "") -> NewsletterEntry:
    metadata = MetadataRecord(
        topic=PrimaryTopic.PAPERS,
        title=title,
        authors=["Author"],
        organizations=["Org"],
        recommendation=recommendation,
        subtopics=[],
        repositories=[
            RepositoryReference(
                url="https://github.com/example/repo",
                provider="github",
                reason="Fixture",
            )
        ],
        datasets=[],
        missing_optional_fields=[],
    )
    return NewsletterEntry(
        source_url="https://example.com/paper",
        metadata=metadata,
        topic=PrimaryTopic.PAPERS,
        subtopics=[],
    )


def test_llm_assigns_subtopics() -> None:
    payload = json.dumps({"classifications": [{"id": 1, "subtopics": ["LLM"]}]})
    stub = StubLLM(payload)
    classifier = SubtopicClassifier(llm_client=stub)
    entry = _paper_entry("Transformers", "Investigates transformer scaling laws")

    classifier.assign_subtopics([entry])

    assert stub.calls == 1
    assert entry.subtopics == ["LLM"]
    assert entry.metadata.subtopics == ["LLM"]


def test_non_paper_entries_are_ignored() -> None:
    stub = StubLLM(json.dumps({"classifications": []}))
    classifier = SubtopicClassifier(llm_client=stub)
    metadata = MetadataRecord(
        topic=PrimaryTopic.BLOGS,
        title="Blog",
        authors=[],
        organizations=[],
        recommendation="",
        subtopics=[],
        repositories=[],
        datasets=[],
        missing_optional_fields=[],
    )
    entry = NewsletterEntry(
        source_url="https://example.com/blog",
        metadata=metadata,
        topic=PrimaryTopic.BLOGS,
        subtopics=[],
    )

    classifier.assign_subtopics([entry])

    assert entry.subtopics == []


def test_gracefully_handles_bad_json() -> None:
    stub = StubLLM("not json")
    classifier = SubtopicClassifier(llm_client=stub)
    entry = _paper_entry("Test Paper")

    classifier.assign_subtopics([entry])

    assert entry.subtopics == []
