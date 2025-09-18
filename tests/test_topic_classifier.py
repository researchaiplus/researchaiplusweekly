from dataclasses import dataclass

from newsletter.classification.topic_classifier import TopicClassifier
from newsletter.io.models import ArticleContent, PrimaryTopic


@dataclass
class StubLLMClient:
    payload: str
    calls: int = 0

    def complete(self, messages):  # type: ignore[override]
        self.calls += 1
        return self.payload


def _article(url: str, text: str = "", title: str | None = None) -> ArticleContent:
    return ArticleContent(url=url, title=title, text=text or "Sample", raw_payload={})


def test_classifier_uses_domain_rules_for_paper() -> None:
    classifier = TopicClassifier()
    article = _article("https://arxiv.org/abs/1234.5678", text="")

    result = classifier.classify(article)

    assert result.topic == PrimaryTopic.PAPERS
    assert result.classification_source == "rules"


def test_classifier_detects_open_source() -> None:
    classifier = TopicClassifier()
    article = _article("https://github.com/org/repo", text="Code release")

    result = classifier.classify(article)

    assert result.topic == PrimaryTopic.OPEN_SOURCE


def test_classifier_falls_back_to_llm() -> None:
    stub = StubLLMClient("Blog")
    classifier = TopicClassifier(llm_client=stub)
    article = _article("https://unknownsite.com/post", text="")

    result = classifier.classify(article)

    assert result.topic == PrimaryTopic.BLOGS
    assert result.classification_source == "llm"
    assert stub.calls == 1


def test_classifier_caches_llm_calls() -> None:
    stub = StubLLMClient("Engineering")
    classifier = TopicClassifier(llm_client=stub)
    article = _article("https://unknownsite.com/post")

    classifier.classify(article)
    classifier.classify(article)

    assert stub.calls == 1
