## Relevant Files

- `pyproject.toml` - Declare project metadata, dependencies (requests, pydantic, httpx, click, python-dotenv) and tool configs.
- `.env.example` - Template listing OpenRouter, Jina Reader, and runtime configuration variables.
- `Makefile` - Convenience targets for linting, formatting, type checks, and tests.
- `src/newsletter/__init__.py` - Package marker for the newsletter pipeline.
- `src/newsletter/config.py` - Load configuration from env and provide typed settings objects.
- `src/newsletter/io/url_loader.py` - Read `.txt` URL lists, normalize, validate, deduplicate.
- `src/newsletter/io/models.py` - Pydantic models for URLs, entries, metadata payloads, and pipeline responses.
- `src/newsletter/services/jina_client.py` - Wrapper around Jina Reader API with retries and error reporting.
- `tests/test_jina_client.py` - Mocked HTTP tests covering Jina Reader success, retries, and failure paths.
- `src/newsletter/services/openrouter_client.py` - Shared LLM client abstraction handling prompts, rate limits, and fallbacks.
- `src/newsletter/classification/topic_classifier.py` - Implements rule-based topic detection with LLM fallback.
- `src/newsletter/classification/subtopic_classifier.py` - Handles paper subtopic classification, including dynamic labels.
- `tests/test_subtopic_classifier.py` - Exercise heuristic and LLM fallback subtopic classification.
- `src/newsletter/metadata/extractor.py` - Coordinates metadata + recommendation prompt/response parsing.
- `src/newsletter/pipeline/builder.py` - Orchestrates ingestion, retrieval, classification, and aggregation into structured entries.
- `src/newsletter/pipeline/markdown_renderer.py` - Generate final Markdown newsletter grouped by topic/subtopic.
- `src/newsletter/cli.py` - Command-line entrypoint to run the full workflow and handle logging/output paths.
- `tests/test_cli.py` - CLI integration tests using Click runner with service stubs.
- `tests/test_url_loader.py` - Unit tests for URL ingestion and deduplication rules.
- `tests/test_topic_classifier.py` - Tests for rule heuristics and fallback logic (mocking LLM client).
- `tests/test_metadata_extractor.py` - Validate prompt payload shaping and JSON parsing with mocked responses.
- `tests/test_pipeline_builder.py` - Integration-style tests for pipeline assembly with fixtures/mocks.
- `README.md` - Add project overview, setup steps, and usage instructions for the workflow.

### Notes

- Introduce fixtures/mocks for external services (Jina, OpenRouter) to keep tests deterministic.
- Capture all generated outputs under `/output/` with timestamped files to avoid overwriting runs.
- Consider dependency injection for services so that future model swaps require minimal changes.
- Ensure logging emits enough context for operators to troubleshoot skipped links.

## Tasks

- [x] 1.0 Establish project scaffolding and developer tooling
  - [x] 1.1 Create `pyproject.toml` with Python >=3.10, dependency list, and configure `ruff`/`mypy` (if chosen).
  - [x] 1.2 Add `src/` package layout, initialize `newsletter` package, and set up basic package exports.
  - [x] 1.3 Provide `.env.example` plus update `README.md` with setup instructions and environment variable descriptions.
  - [x] 1.4 Configure pre-commit or lint/test scripts (optional) and document how to run them.
- [x] 2.0 Implement URL ingestion workflow
  - [x] 2.1 Build loader to read `.txt` input, strip comments/blank lines, and validate URL format.
  - [x] 2.2 Normalize URLs (e.g., lowercase host, remove tracking params) and deduplicate entries.
  - [x] 2.3 Add error handling for unreadable files or invalid URLs and expose structured results via Pydantic models.
  - [x] 2.4 Write unit tests covering normal, empty, and malformed input scenarios.
- [x] 3.0 Integrate Jina Reader content retrieval
  - [x] 3.1 Implement `JinaClient` with configurable base URL, API key, timeout, and retry policy.
  - [x] 3.2 Map successful responses into structured article content; log and skip failures with error messages.
  - [x] 3.3 Add tests using mocked HTTP responses for success, timeout, and error cases.
- [x] 4.0 Build primary topic classification module
  - [x] 4.1 Define rule-based heuristics mapping domains/keywords to the four primary topics.
  - [x] 4.2 Implement LLM fallback prompt when heuristics return `unknown`, including caching to minimize duplicate calls.
  - [x] 4.3 Add tests for heuristic coverage and fallback invocation (mocking the LLM client).
- [x] 5.0 Implement metadata extraction and recommendation generation
  - [x] 5.1 Design prompt templates for extracting title, authors, organizations, and recommendation ≤100 words.
  - [x] 5.2 Parse LLM JSON output with validation (retry on malformed responses, truncate long fields).
  - [x] 5.3 Enrich entries with detected repos/datasets info and flag missing optional elements in logs.
  - [x] 5.4 Cover parsing logic with unit tests using canned LLM responses.
- [x] 6.0 Add paper subtopic classification workflow
  - [x] 6.1 Enumerate supported subtopics and implement rule overrides (e.g., keywords from abstract).
  - [x] 6.2 Call LLM classification for papers, allow new tags when confidence low, and record them in metadata.
  - [x] 6.3 Ensure non-paper items bypass this step gracefully and add tests for key pathways.
- [x] 7.0 Assemble final outputs
  - [x] 7.1 Aggregate processed entries into JSON-like structures grouped by topic/subtopic order.
  - [x] 7.2 Implement Markdown renderer aligning with PRD format, including emojis and consistent sections.
  - [x] 7.3 Write snapshot-style tests for Markdown output and ensure file writing honors `/output/` path convention.
- [x] 8.0 Deliver orchestration CLI and logging
  - [x] 8.1 Build CLI (e.g., Click/Typer) to accept input file path, optional output directory, and verbosity flag.
  - [x] 8.2 Wire ingestion, retrieval, classification, and rendering modules; collect metrics/statistics per run.
  - [x] 8.3 Integrate structured logging and summary reporting for skipped URLs/errors.
  - [x] 8.4 Add end-to-end test using fixtures/mocks to ensure CLI produces expected Markdown.
