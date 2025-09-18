"""Pipeline that orchestrates ingestion, enrichment, and assembly."""

from __future__ import annotations

import logging
from pathlib import Path

from newsletter.classification.subtopic_classifier import SubtopicClassifier
from newsletter.classification.topic_classifier import TopicClassifier
from newsletter.io.models import ClassifiedArticle, MetadataRecord, NewsletterEntry, PipelineResult
from newsletter.io.url_loader import UrlLoadError, load_urls
from newsletter.metadata.extractor import MetadataExtractionError, MetadataExtractor
from newsletter.services.jina_client import JinaClient, JinaClientError

LOGGER = logging.getLogger(__name__)


class NewsletterPipeline:
    """High-level orchestration for the newsletter workflow."""

    def __init__(
        self,
        url_loader=load_urls,
        jina_client: JinaClient | None = None,
        topic_classifier: TopicClassifier | None = None,
        metadata_extractor: MetadataExtractor | None = None,
        subtopic_classifier: SubtopicClassifier | None = None,
    ) -> None:
        if jina_client is None:
            raise ValueError("Jina client instance is required")
        if topic_classifier is None:
            raise ValueError("Topic classifier instance is required")
        if metadata_extractor is None:
            raise ValueError("Metadata extractor instance is required")
        if subtopic_classifier is None:
            raise ValueError("Subtopic classifier instance is required")

        self._load_urls = url_loader
        self._jina_client = jina_client
        self._topic_classifier = topic_classifier
        self._metadata_extractor = metadata_extractor
        self._subtopic_classifier = subtopic_classifier

    def run(self, manifest_path: str | Path) -> PipelineResult:
        LOGGER.info("Starting pipeline for manifest: %s", manifest_path)
        try:
            load_result = self._load_urls(manifest_path)
        except UrlLoadError as exc:
            LOGGER.error("Failed to load URLs: %s", exc)
            raise

        result = PipelineResult(invalid_urls=load_result.invalid_entries)
        result.skipped_urls = [str(url) for url in load_result.duplicate_urls]

        for entry in load_result.entries:
            normalized_url = str(entry.normalized_url)
            try:
                content = self._jina_client.fetch(normalized_url)
            except JinaClientError as exc:
                LOGGER.error("Skipping URL %s due to retrieval failure: %s", normalized_url, exc)
                result.failed_urls.append(normalized_url)
                continue

            classified = self._topic_classifier.classify(content)

            try:
                metadata = self._metadata_extractor.extract(classified)
            except MetadataExtractionError as exc:
                LOGGER.error("Skipping URL %s due to metadata failure: %s", normalized_url, exc)
                result.failed_urls.append(normalized_url)
                continue

            final_metadata = self._finalize_metadata(classified, metadata)
            newsletter_entry = NewsletterEntry(
                source_url=content.url,
                metadata=final_metadata,
                topic=classified.topic,
                subtopics=final_metadata.subtopics,
            )
            result.entries.append(newsletter_entry)

        LOGGER.info("Pipeline completed: %s entries", len(result.entries))
        return result

    def _finalize_metadata(
        self, classified: ClassifiedArticle, metadata: MetadataRecord
    ) -> MetadataRecord:
        subtopics = self._subtopic_classifier.classify(classified, metadata)
        if subtopics:
            return metadata.model_copy(update={"subtopics": subtopics})
        return metadata


__all__ = ["NewsletterPipeline"]
