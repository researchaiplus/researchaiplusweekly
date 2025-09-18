# Newsletter Workflow

Automation pipeline that ingests research and product links, enriches them with LLM generated metadata, and renders a weekly AI newsletter.

## Prerequisites

- Python 3.10+
- `pip` or `pipx`
- OpenRouter API access (key + model configuration)
- Jina Reader API key

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install the project in editable mode with development dependencies:
   ```bash
   pip install -e .[dev]
   ```
3. Duplicate the example environment file and populate secrets:
   ```bash
   cp .env.example .env
   ```
4. Edit `.env` with your credentials and configuration:
   - `OPENROUTER_BASE_URL`: Base URL for the OpenRouter gateway (default `https://openrouter.ai/api/v1`).
   - `OPENROUTER_KEY`: API key used to authenticate with OpenRouter.
   - `OPENROUTER_MODEL`: Default model identifier (e.g., `anthropic/claude-3.5-sonnet`).
   - `JINA_READER_BASE_URL`: Base URL for the Jina Reader fetch service (default `https://r.jina.ai`).
   - `JINA_READER_API_KEY`: API token for the Jina Reader API.
   - `NEWSLETTER_OUTPUT_DIR`: Directory path for rendered newsletter artifacts (default `./output`).
   - `NEWSLETTER_LOG_LEVEL`: Logging verbosity (`DEBUG`, `INFO`, `WARNING`, etc.).

5. Load environment variables during development:
   ```bash
   export $(grep -v '^#' .env | xargs)
   ```

6. run:
```
python -m newsletter.cli path/to/urls.txt --output-dir ./output     #（或加 --dry-run 预览 Markdown）。
```

## Developer Tooling

- Run `make lint`, `make format`, `make typecheck`, or `make test` for focused commands.
- Run `make check` to execute linting, mypy, and pytest in one pass.
- Direct commands are still available if you prefer:
  - Ruff lint: `ruff check src tests`
  - Ruff format: `ruff format src tests`
  - Type checks: `mypy src`
  - Tests: `pytest`

## Status

Implementation is ongoing; consult `tasks/tasks-prd-newsletter.md` for the active task list.
