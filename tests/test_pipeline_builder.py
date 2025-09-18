
from newsletter.io.models import (
    ArticleContent,
    ClassifiedArticle,
    MetadataRecord,
    PrimaryTopic,
    UrlEntry,
    UrlLoadResult,
)
from newsletter.metadata.extractor import MetadataExtractionError
from newsletter.pipeline.builder import NewsletterPipeline


def _url_loader_success(path):
    return UrlLoadResult(
        entries=[
            UrlEntry(
                raw_url="https://example.com/a",
                normalized_url="https://example.com/a",
                source_line=1,
            )
        ]
    )


class StubJinaClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def fetch(self, url):
        self.calls += 1
        if isinstance(self.responses, Exception):
            raise self.responses
        return self.responses


class StubTopicClassifier:
    def __init__(self, topic: PrimaryTopic) -> None:
        self.topic = topic

    def classify(self, article: ArticleContent) -> ClassifiedArticle:  # type: ignore[override]
        return ClassifiedArticle(content=article, topic=self.topic, classification_source="rules")


class StubMetadataExtractor:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def extract(self, article):  # type: ignore[override]
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class StubSubtopicClassifier:
    def __init__(self, output):
        self.output = output

    def classify(self, article, metadata):  # type: ignore[override]
        return self.output


def test_pipeline_success_flow() -> None:
    content = ArticleContent(url="https://example.com/a", title="A", text="Body", raw_payload={})
    metadata = MetadataRecord(
        topic=PrimaryTopic.PAPERS,
        title="A",
        authors=["Author"],
        organizations=["Org"],
        recommendation="Great research",
        subtopics=[],
        repositories=[],
        datasets=[],
        attachments=[],
        missing_optional_fields=[],
    )

    pipeline = NewsletterPipeline(
        url_loader=_url_loader_success,
        jina_client=StubJinaClient(content),
        topic_classifier=StubTopicClassifier(PrimaryTopic.PAPERS),
        metadata_extractor=StubMetadataExtractor(metadata),
        subtopic_classifier=StubSubtopicClassifier(["LLM"]),
    )

    result = pipeline.run("manifest.txt")

    assert result.success_count == 1
    assert result.entries[0].metadata.subtopics == ["LLM"]
    assert result.failed_urls == []


def test_pipeline_handles_failures() -> None:
    content = ArticleContent(url="https://example.com/a", title="A", text="Body", raw_payload={})

    pipeline = NewsletterPipeline(
        url_loader=_url_loader_success,
        jina_client=StubJinaClient(content),
        topic_classifier=StubTopicClassifier(PrimaryTopic.PAPERS),
        metadata_extractor=StubMetadataExtractor(MetadataExtractionError("boom")),
        subtopic_classifier=StubSubtopicClassifier([]),
    )

    result = pipeline.run("manifest.txt")

    assert result.entries == []
    assert result.failed_urls == ["https://example.com/a"]
