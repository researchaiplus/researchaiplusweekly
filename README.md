# Newsletter Workflow

Automation pipeline that ingests research and product links, enriches them with LLM generated metadata, and renders a weekly AI newsletter.

## Prerequisites

- Python 3.10+
- `pip` or `pipx`
- Redis 6+ (for Celery broker/result backend)
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

6. Run the CLI workflow directly when you just need Markdown output:

   ```bash
   python -m newsletter.cli path/to/urls.txt --output-dir ./output
   # Add --dry-run to preview markdown without writing to disk.
   ```

## Running the web experience

1. Ensure Redis is available locally:

   ```bash
   redis-server
   ```

2. In a separate terminal, start the Celery worker:

   ```bash
   CELERY_BROKER_URL=redis://localhost:6379/0 \\
   CELERY_RESULT_BACKEND=redis://localhost:6379/0 \\
   DATABASE_PATH=./data/newsletter_tasks.db \\
   celery -A newsletter.api.celery_app.celery_app worker --loglevel=info
   ```

3. Launch the FastAPI application (served on <http://127.0.0.1:8000/> by default):

   ```bash
   DATABASE_PATH=./data/newsletter_tasks.db \\
   uvicorn newsletter.api.app:app --reload
   ```

4. Open the root page to access the single-page interface. Paste or upload URLs, tweak options, and watch the Server-Sent Events (SSE) status stream render live progress and Markdown previews.

### Environment variables

Key variables recognised by the web stack:

- `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`: Redis connection strings used by Celery.
- `DATABASE_PATH`: Absolute path to the SQLite database that persists task metadata.
- `CELERY_TASK_ALWAYS_EAGER`: Set to `true` to run Celery tasks synchronously (handy for tests/demo).
- Existing `.env` settings (`OPENROUTER_*`, `JINA_READER_*`, `NEWSLETTER_*`) continue to configure the LLM pipeline.

## Render deployment quickstart

`render.yaml` provisions three services: the FastAPI web app, a Celery worker, and a managed Redis instance. The web and worker services share a persistent disk mounted at `/var/data` for the SQLite task store. Deploy via:

```bash
render deploy --from render.yaml
```

Update the synced environment variables in Render's dashboard with your API keys before triggering the first deploy.

## Developer Tooling

- Run `make lint`, `make format`, `make typecheck`, or `make test` for focused commands.
- Run `make check` to execute linting, mypy, and pytest in one pass.
- Direct commands are still available if you prefer:
  - Ruff lint: `ruff check src tests`
  - Ruff format: `ruff format src tests`
  - Type checks: `mypy src`
- Tests: `pytest`

> **Note:** The test suite and runtime require Python 3.10+ because the codebase uses modern typing features (`bool | None`, etc.). Running the tests under 3.9 will fail during import-time validation.

## Status

Implementation is ongoing; consult `tasks/Task-PRD-supplement.md` for the active task list.
