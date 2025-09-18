"""Command-line entrypoint for the newsletter workflow."""

from __future__ import annotations

import logging
from pathlib import Path

import click

from newsletter.classification.subtopic_classifier import SubtopicClassifier
from newsletter.classification.topic_classifier import TopicClassifier
from newsletter.config import get_settings
from newsletter.io.models import PipelineResult
from newsletter.metadata.extractor import MetadataExtractor
from newsletter.pipeline.builder import NewsletterPipeline
from newsletter.pipeline.markdown_renderer import MarkdownRenderer
from newsletter.services.jina_client import JinaClient
from newsletter.services.openrouter_client import OpenRouterClient

LOGGER = logging.getLogger(__name__)

LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


@click.command()
@click.argument("manifest", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option(
    "--output-dir",
    type=click.Path(dir_okay=True, file_okay=False, path_type=Path),
    help="Directory where the rendered Markdown will be written.",
)
@click.option(
    "--log-level",
    type=click.Choice(LOG_LEVELS, case_sensitive=False),
    help="Override the configured log level.",
)
@click.option("--dry-run/--no-dry-run", default=False, help="Skip writing Markdown output to disk.")
def cli(manifest: Path, output_dir: Path | None, log_level: str | None, dry_run: bool) -> None:
    """Run the newsletter pipeline for the provided MANIFEST file."""

    settings = get_settings()
    level = (log_level or settings.newsletter.log_level).upper()
    numeric_level = getattr(logging, level, logging.INFO)
    logging.basicConfig(
        level=numeric_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    LOGGER.info("Loading configuration and initializing services")
    output_directory = output_dir or settings.newsletter.output_dir

    with (
        JinaClient(settings.jina) as jina_client,
        OpenRouterClient(settings.openrouter) as llm_client,
    ):
        topic_classifier = TopicClassifier(llm_client=llm_client)
        metadata_extractor = MetadataExtractor(llm_client)
        subtopic_classifier = SubtopicClassifier(llm_client=llm_client)
        pipeline = NewsletterPipeline(
            jina_client=jina_client,
            topic_classifier=topic_classifier,
            metadata_extractor=metadata_extractor,
            subtopic_classifier=subtopic_classifier,
        )

        result = pipeline.run(manifest)

        if result.entries:
            renderer = MarkdownRenderer()
            if dry_run:
                LOGGER.info("Dry-run enabled; skipping Markdown write")
                markdown_preview = renderer.render(result.entries)
                click.echo(markdown_preview)
            else:
                destination = Path(output_directory)
                output_path = renderer.write(result.entries, destination)
                click.echo(f"Markdown written to {output_path}")
        else:
            click.echo("No entries were produced; nothing to write.")

        click.echo(_format_summary(result))


def _format_summary(result: PipelineResult) -> str:
    parts = [
        f"Processed entries: {result.success_count}",
        f"Invalid URLs: {len(result.invalid_urls)}",
        f"Duplicates skipped: {len(result.skipped_urls)}",
        f"Failures: {len(result.failed_urls)}",
    ]
    return " | ".join(parts)


if __name__ == "__main__":  # pragma: no cover - CLI entry guard
    cli()
