"""FastAPI application exposing newsletter generation endpoints."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse
from pydantic import AnyHttpUrl, TypeAdapter

from newsletter.api.models import (
    GenerateRequest,
    GenerateResponse,
    ResultMetadata,
    ResultResponse,
    StatusProgress,
    StatusResponse,
    TaskStatus,
    UploadResponse,
    TaskRecord,
)
from newsletter.api.dependencies import get_task_dispatcher, get_task_store
from newsletter.api.service import is_terminal_status
from newsletter.api.task_dispatcher import TaskDispatcher
from newsletter.api.task_store import TaskStore
from newsletter.io.url_loader import normalize_url


STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024

_url_adapter = TypeAdapter(AnyHttpUrl)

app = FastAPI(title="AI Newsletter Generator API", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=FileResponse)
async def read_index() -> FileResponse:
    """Serve the root HTML page for the web client."""

    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Index not found")
    return FileResponse(index_path)


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    """Lightweight health check used for uptime monitoring."""

    return {"status": "ok"}


@app.post(
    "/api/v1/newsletter/generate",
    response_model=GenerateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_newsletter(
    request: GenerateRequest,
    task_store: TaskStore = Depends(get_task_store),
    dispatcher: TaskDispatcher = Depends(get_task_dispatcher),
) -> GenerateResponse:
    """Accept a batch of URLs and schedule newsletter generation."""

    payload = request.model_dump(mode='json')
    record = task_store.create(url_count=len(request.urls), payload=payload)
    dispatcher.dispatch(record.task_id, [str(url) for url in request.urls])
    return GenerateResponse(task_id=record.task_id, status=record.status)


@app.get(
    "/api/v1/newsletter/status/{task_id}",
    response_model=StatusResponse,
)
async def get_task_status(task_id: str, task_store: TaskStore = Depends(get_task_store)) -> StatusResponse:
    """Fetch the status of a previously submitted task."""

    stored = task_store.get(task_id)
    if stored is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return _to_status_response(stored)


@app.get(
    "/api/v1/newsletter/result/{task_id}",
    response_model=ResultResponse,
)
async def get_task_result(task_id: str, task_store: TaskStore = Depends(get_task_store)) -> ResultResponse:
    """Retrieve the rendered Markdown output for a completed task."""

    stored = task_store.get(task_id)
    if stored is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if stored.status is not TaskStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task not completed")

    if stored.markdown_content is None or stored.metadata is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Task result missing")

    return ResultResponse(
        task_id=stored.task_id,
        status=stored.status,
        markdown_content=stored.markdown_content,
        metadata=stored.metadata,
    )


@app.get("/api/v1/newsletter/events/{task_id}")
async def stream_task_events(task_id: str, task_store: TaskStore = Depends(get_task_store)) -> EventSourceResponse:
    """Stream task updates to clients using Server-Sent Events."""

    if task_store.get(task_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    async def event_generator():
        last_payload = ""
        while True:
            record = task_store.get(task_id)
            if record is None:
                break
            payload = _status_payload(record)
            if payload != last_payload:
                yield {"event": "status", "data": payload}
                last_payload = payload
            if is_terminal_status(record.status):
                break
            await asyncio.sleep(1.0)
        if last_payload:
            yield {"event": "end", "data": last_payload}

    return EventSourceResponse(event_generator(), headers={"Cache-Control": "no-store"})


@app.post(
    "/api/v1/newsletter/upload",
    response_model=UploadResponse,
)
async def upload_manifest(file: UploadFile = File(...)) -> UploadResponse:
    """Parse a text file containing URLs and return validated entries."""

    if file.content_type not in {"text/plain", "application/octet-stream", "application/text"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 5 MB limit")
    try:
        text = contents.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File must be UTF-8 encoded") from exc

    urls, invalid = _parse_urls(text)
    return UploadResponse(urls=urls, invalid_urls=invalid)


def _parse_urls(text: str) -> tuple[list[AnyHttpUrl], list[str]]:
    urls: list[AnyHttpUrl] = []
    invalid: list[str] = []
    seen: set[str] = set()

    for raw_line in text.splitlines():
        candidate = raw_line.strip()
        if not candidate or candidate.startswith("#"):
            continue
        try:
            normalized = normalize_url(candidate)
            parsed = _url_adapter.validate_python(normalized)
        except Exception:
            invalid.append(candidate)
            continue
        if str(parsed) in seen:
            continue
        seen.add(str(parsed))
        urls.append(parsed)
    return urls, invalid


def _to_status_response(record: TaskRecord) -> StatusResponse:
    progress = StatusProgress(**record.progress.model_dump())
    return StatusResponse(
        task_id=record.task_id,
        status=record.status,
        progress=progress,
        estimated_completion=None,
        error=record.error,
    )


def _status_payload(record: TaskRecord) -> str:
    response = _to_status_response(record)
    return json.dumps(response.model_dump())


__all__ = ["app"]
