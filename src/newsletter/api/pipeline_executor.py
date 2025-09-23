"""Pipeline execution helpers for the API layer."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Protocol, Sequence

from newsletter.classification.subtopic_classifier import SubtopicClassifier
from newsletter.classification.topic_classifier import TopicClassifier
from newsletter.config import AppSettings, get_settings
from newsletter.io.models import PipelineResult
from newsletter.metadata.extractor import MetadataExtractor
from newsletter.pipeline.builder import NewsletterPipeline
from newsletter.services.jina_client import JinaClient
from newsletter.services.openrouter_client import OpenRouterClient


class PipelineExecutor(Protocol):
    """Abstraction for executing the newsletter pipeline."""

    def execute(self, urls: Sequence[str]) -> PipelineResult:
        ...


class DefaultPipelineExecutor:
    """Concrete executor that relies on the production pipeline implementation."""

    def __init__(self, settings: AppSettings | None = None) -> None:
        self._settings = settings or get_settings()

    def execute(self, urls: Sequence[str]) -> PipelineResult:
        manifest_path = self._write_manifest(urls)
        try:
            with (
                JinaClient(self._settings.jina) as jina_client,
                OpenRouterClient(self._settings.openrouter) as llm_client,
            ):
                pipeline = NewsletterPipeline(
                    jina_client=jina_client,
                    topic_classifier=TopicClassifier(llm_client=llm_client),
                    metadata_extractor=MetadataExtractor(llm_client),
                    subtopic_classifier=SubtopicClassifier(llm_client=llm_client),
                )
                return pipeline.run(manifest_path)
        finally:
            manifest_path.unlink(missing_ok=True)

    @staticmethod
    def _write_manifest(urls: Sequence[str]) -> Path:
        if not urls:
            raise ValueError("At least one URL must be provided")
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", suffix=".txt") as handle:
            handle.write("\n".join(str(url) for url in urls))
            temp_path = Path(handle.name)
        return temp_path


__all__ = ["DefaultPipelineExecutor", "PipelineExecutor"]
