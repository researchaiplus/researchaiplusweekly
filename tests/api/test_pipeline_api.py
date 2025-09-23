from __future__ import annotations

from collections.abc import Generator, Sequence

import pytest
from fastapi.testclient import TestClient

from newsletter.api import app as fastapi_app
from newsletter.api.dependencies import (
    get_task_dispatcher,
    get_pipeline_executor,
    get_task_store,
)
from newsletter.api.pipeline_executor import PipelineExecutor
from newsletter.api.task_dispatcher import TaskDispatcher
from newsletter.api.task_store import InMemoryTaskStore
from newsletter.io.models import PipelineResult


class NoopDispatcher(TaskDispatcher):
    def dispatch(self, task_id: str, urls: Sequence[str]) -> None:  # type: ignore[override]
        return None


class NullExecutor(PipelineExecutor):
    def execute(self, urls):  # type: ignore[override]
        return PipelineResult()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    store = InMemoryTaskStore()
    dispatcher = NoopDispatcher()
    executor = NullExecutor()

    overrides = {
        get_task_store: lambda: store,
        get_task_dispatcher: lambda: dispatcher,
        get_pipeline_executor: lambda: executor,
    }

    original_overrides = fastapi_app.dependency_overrides.copy()
    fastapi_app.dependency_overrides.update(overrides)

    with TestClient(fastapi_app) as test_client:
        test_client.task_store = store  # type: ignore[attr-defined]
        yield test_client

    fastapi_app.dependency_overrides = original_overrides


def test_generate_requires_urls(client: TestClient) -> None:
    response = client.post("/api/v1/newsletter/generate", json={"urls": []})
    assert response.status_code == 422


def test_status_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/newsletter/status/unknown-task")
    assert response.status_code == 404


def test_result_conflict_when_task_not_ready(client: TestClient) -> None:
    store: InMemoryTaskStore = client.task_store  # type: ignore[attr-defined]
    record = store.create(url_count=1, payload={"urls": ["https://example.com"]})

    response = client.get(f"/api/v1/newsletter/result/{record.task_id}")
    assert response.status_code == 409
