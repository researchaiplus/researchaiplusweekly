from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from newsletter.api import app as fastapi_app
from newsletter.api.dependencies import (
    get_task_dispatcher,
    get_pipeline_executor,
    get_task_store,
)
from newsletter.api.pipeline_executor import PipelineExecutor
from newsletter.api.task_store import InMemoryTaskStore
from newsletter.api.service import execute_pipeline_task
from newsletter.api.task_dispatcher import TaskDispatcher
from newsletter.io.models import MetadataRecord, NewsletterEntry, PipelineResult, PrimaryTopic


class StubPipelineExecutor(PipelineExecutor):
    def __init__(self) -> None:
        metadata = MetadataRecord(
            topic=PrimaryTopic.PAPERS,
            title="Test Paper",
            authors=["Author"],
            organizations=["Org"],
            recommendation="Check it out",
        )
        entry = NewsletterEntry(
            source_url="https://example.com/paper",
            metadata=metadata,
            topic=PrimaryTopic.PAPERS,
            subtopics=["ML"],
        )
        self.result = PipelineResult(entries=[entry])

    def execute(self, urls) -> PipelineResult:  # type: ignore[override]
        return self.result


class SynchronousDispatcher(TaskDispatcher):
    def __init__(self, store: InMemoryTaskStore, executor: PipelineExecutor) -> None:
        self._store = store
        self._executor = executor

    def dispatch(self, task_id: str, urls) -> None:  # type: ignore[override]
        execute_pipeline_task(
            task_id=task_id,
            urls=list(urls),
            task_store=self._store,
            executor=self._executor,
        )


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    store = InMemoryTaskStore()
    executor = StubPipelineExecutor()
    dispatcher = SynchronousDispatcher(store, executor)

    overrides = {
        get_task_store: lambda: store,
        get_pipeline_executor: lambda: executor,
        get_task_dispatcher: lambda: dispatcher,
    }

    original_overrides = fastapi_app.dependency_overrides.copy()
    fastapi_app.dependency_overrides.update(overrides)

    with TestClient(fastapi_app) as test_client:
        yield test_client

    fastapi_app.dependency_overrides = original_overrides


def test_index_served(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "AI Newsletter Generator" in response.text


def test_generate_status_and_result_flow(client: TestClient) -> None:
    response = client.post(
        "/api/v1/newsletter/generate",
        json={"urls": ["https://example.com/paper"]},
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "pending"
    task_id = payload["task_id"]

    status_response = client.get(f"/api/v1/newsletter/status/{task_id}")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "completed"
    assert status_payload["progress"]["total_urls"] == 1

    result_response = client.get(f"/api/v1/newsletter/result/{task_id}")
    assert result_response.status_code == 200
    result_payload = result_response.json()
    assert result_payload["metadata"]["total_processed"] == 1
    assert "Test Paper" in result_payload["markdown_content"]


def test_upload_manifest_endpoint(client: TestClient) -> None:
    files = {
        "file": ("sample.txt", "https://example.com\nnotes\nhttps://example.com"),
    }
    response = client.post("/api/v1/newsletter/upload", files=files)
    assert response.status_code == 200
    payload = response.json()
    assert payload["urls"] == ["https://example.com"]
    assert payload["invalid_urls"] == ["notes"]


def test_sse_events_stream(client: TestClient) -> None:
    response = client.post(
        "/api/v1/newsletter/generate",
        json={"urls": ["https://example.com/paper"]},
    )
    task_id = response.json()["task_id"]

    events: list[str] = []
    with client.stream("GET", f"/api/v1/newsletter/events/{task_id}") as stream:
        for line in stream.iter_lines():
            decoded = line.decode()
            if decoded:
                events.append(decoded)
            if decoded.startswith("event: end"):
                break

    payload_lines = [line for line in events if line.startswith("data:")]
    assert payload_lines, "Expected SSE data payloads"
    combined = "\n".join(payload_lines)
    assert '"status": "completed"' in combined
