import json
from collections import deque

import pytest

from newsletter.io.models import ArticleContent, ClassifiedArticle, MetadataRecord, PrimaryTopic
from newsletter.metadata.extractor import (
    ExtractionConfig,
    MetadataExtractionError,
    MetadataExtractor,
)


class StubLLM:
    def __init__(self, responses):
        self.responses = deque(responses)
        self.calls = 0

    def complete(self, messages, response_format=None):  # type: ignore[override]
        self.calls += 1
        if not self.responses:
            raise RuntimeError("No more responses")
        result = self.responses.popleft()
        if isinstance(result, Exception):
            raise result
        return result


def _article(text: str = "", url: str = "https://example.com") -> ClassifiedArticle:
    content = ArticleContent(url=url, title="Title", text=text or "Sample body", raw_payload={})
    return ClassifiedArticle(
        content=content, topic=PrimaryTopic.PAPERS, classification_source="rules"
    )


def test_metadata_extractor_success() -> None:
    response = json.dumps(
        {
            "title": "Great Paper",
            "authors": ["Alice", "Bob"],
            "organizations": ["Org1"],
            "recommendation": "This work introduces a novel method for transformers.",
            "subtopics": ["LLM"],
            "attachments": ["Slides"],
        }
    )
    llm = StubLLM([response])
    extractor = MetadataExtractor(llm)

    article = _article("Check the repo at https://github.com/org/repo")
    metadata = extractor.extract(article)

    assert isinstance(metadata, MetadataRecord)
    assert metadata.repositories == ["https://github.com/org/repo"]
    assert metadata.subtopics == ["LLM"]
    assert metadata.missing_optional_fields == ["datasets"]


def test_metadata_extractor_retries_and_truncates() -> None:
    long_text = "word " * 150
    responses = [
        "not json",
        json.dumps(
            {
                "title": "Paper",
                "authors": [],
                "organizations": [],
                "recommendation": long_text,
                "subtopics": [],
                "attachments": [],
            }
        ),
    ]
    llm = StubLLM(responses)
    extractor = MetadataExtractor(
        llm, ExtractionConfig(max_attempts=2, recommendation_word_limit=5)
    )

    article = _article("Dataset released for evaluation")
    metadata = extractor.extract(article)

    assert llm.calls == 2
    assert metadata.recommendation.endswith("…")
    assert "dataset" in metadata.datasets


def test_metadata_extractor_fails_after_retries() -> None:
    llm = StubLLM(["bad", "still bad"])
    extractor = MetadataExtractor(llm, ExtractionConfig(max_attempts=2))

    with pytest.raises(MetadataExtractionError):
        extractor.extract(_article())
