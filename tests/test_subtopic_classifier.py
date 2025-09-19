import json

from newsletter.classification.subtopic_classifier import SubtopicClassifier
from newsletter.io.models import (
    ArticleContent,
    ClassifiedArticle,
    MetadataRecord,
    PrimaryTopic,
    RepositoryReference,
)


class StubLLM:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls = 0

    def complete(self, messages, response_format=None):  # type: ignore[override]
        self.calls += 1
        return self.payload


def _paper(text: str) -> ClassifiedArticle:
    content = ArticleContent(url="https://example.com", title="Title", text=text, raw_payload={})
    return ClassifiedArticle(
        content=content, topic=PrimaryTopic.PAPERS, classification_source="rules"
    )


def test_subtopic_classifier_heuristics() -> None:
    classifier = SubtopicClassifier()
    article = _paper("This reinforcement learning approach uses new policy gradients.")

    assert classifier.classify(article) == ["RL"]


def test_subtopic_classifier_non_paper() -> None:
    classifier = SubtopicClassifier()
    content = ArticleContent(
        url="https://blog.com", title="Blog", text="Agents everywhere", raw_payload={}
    )
    article = ClassifiedArticle(
        content=content, topic=PrimaryTopic.BLOGS, classification_source="rules"
    )

    assert classifier.classify(article) == []


def test_subtopic_classifier_llm_fallback() -> None:
    payload = json.dumps({"subtopics": ["Agents", "New Idea"]})
    stub = StubLLM(payload)
    classifier = SubtopicClassifier(llm_client=stub)
    article = _paper("An overview of tool use")
    metadata = MetadataRecord(
        topic=PrimaryTopic.PAPERS,
        title="Test",
        authors=[],
        organizations=[],
        recommendation="",
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

    result = classifier.classify(article, metadata)

    assert result == ["Agents"]
    assert stub.calls == 1
