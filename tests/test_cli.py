from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner

from newsletter.cli import cli
from newsletter.io.models import (
    MetadataRecord,
    NewsletterEntry,
    PipelineResult,
    PrimaryTopic,
    RepositoryReference,
)


def _pipeline_result() -> PipelineResult:
    metadata = MetadataRecord(
        topic=PrimaryTopic.BLOGS,
        title="Sample",
        authors=["Alice"],
        organizations=["Org"],
        recommendation="Great read",
        subtopics=[],
        repositories=[
            RepositoryReference(
                url="https://github.com/example/repo",
                provider="github",
                reason="Provided in tests",
            )
        ],
        datasets=[],
        missing_optional_fields=[],
    )
    entry = NewsletterEntry(
        source_url="https://example.com", metadata=metadata, topic=PrimaryTopic.BLOGS, subtopics=[]
    )
    return PipelineResult(entries=[entry])


class DummyContext:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


class DummyPipeline:
    def __init__(self, **_: object) -> None:
        self.result = _pipeline_result()

    def run(self, manifest: Path) -> PipelineResult:
        return self.result


class DummyRenderer:
    def __init__(self) -> None:
        self.entries = None

    def render(self, entries):
        self.entries = entries
        return "MARKDOWN"

    def write(self, entries, destination):
        self.entries = entries
        output_path = destination / "newsletter.md"
        destination.mkdir(parents=True, exist_ok=True)
        output_path.write_text("MARKDOWN", encoding="utf-8")
        return output_path


def _prepare_settings(output_dir: Path) -> SimpleNamespace:
    return SimpleNamespace(
        openrouter=SimpleNamespace(
            api_key="key", base_url="https://openrouter.ai", model="m", timeout_seconds=1
        ),
        jina=SimpleNamespace(
            api_key="jinakey", base_url="https://r.jina.ai", timeout_seconds=1, max_retries=0
        ),
        newsletter=SimpleNamespace(output_dir=output_dir, log_level="INFO"),
    )


def test_cli_writes_markdown(tmp_path, monkeypatch) -> None:
    settings = _prepare_settings(tmp_path / "output")
    monkeypatch.setattr("newsletter.cli.get_settings", lambda: settings)
    monkeypatch.setattr("newsletter.cli.JinaClient", lambda *args, **kwargs: DummyContext())
    monkeypatch.setattr("newsletter.cli.OpenRouterClient", lambda *args, **kwargs: DummyContext())
    monkeypatch.setattr("newsletter.cli.NewsletterPipeline", DummyPipeline)
    monkeypatch.setattr("newsletter.cli.MarkdownRenderer", DummyRenderer)

    manifest = tmp_path / "input.txt"
    manifest.write_text("https://example.com", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli, [str(manifest)])

    assert result.exit_code == 0
    output_file = settings.newsletter.output_dir / "newsletter.md"
    assert output_file.exists()
    assert "Processed entries: 1" in result.output


def test_cli_dry_run_prints_markdown(tmp_path, monkeypatch) -> None:
    settings = _prepare_settings(tmp_path / "output")
    monkeypatch.setattr("newsletter.cli.get_settings", lambda: settings)
    monkeypatch.setattr("newsletter.cli.JinaClient", lambda *args, **kwargs: DummyContext())
    monkeypatch.setattr("newsletter.cli.OpenRouterClient", lambda *args, **kwargs: DummyContext())
    monkeypatch.setattr("newsletter.cli.NewsletterPipeline", DummyPipeline)

    class RendererWithSpy(DummyRenderer):
        def write(self, entries, destination):  # type: ignore[override]
            raise AssertionError("write should not be called in dry-run mode")

    monkeypatch.setattr("newsletter.cli.MarkdownRenderer", RendererWithSpy)

    manifest = tmp_path / "input.txt"
    manifest.write_text("https://example.com", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli, [str(manifest), "--dry-run"])

    assert result.exit_code == 0
    assert "MARKDOWN" in result.output
