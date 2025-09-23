"""Dependency helpers shared between FastAPI routes and Celery tasks."""

from __future__ import annotations

from functools import lru_cache
from typing import Callable

from newsletter.api.pipeline_executor import DefaultPipelineExecutor, PipelineExecutor
from newsletter.api.task_dispatcher import CeleryTaskDispatcher, TaskDispatcher
from newsletter.api.task_store import SQLiteTaskStore, TaskStore
from newsletter.config import AppSettings, get_settings


@lru_cache(maxsize=1)
def _get_settings() -> AppSettings:
    return get_settings()


@lru_cache(maxsize=1)
def get_task_store() -> TaskStore:
    settings = _get_settings()
    return SQLiteTaskStore(settings.database.path)


@lru_cache(maxsize=1)
def get_pipeline_executor() -> PipelineExecutor:
    settings = _get_settings()
    return DefaultPipelineExecutor(settings)


@lru_cache(maxsize=1)
def get_task_dispatcher() -> TaskDispatcher:
    settings = _get_settings()
    dispatcher_factory: Callable[[], TaskDispatcher] = lambda: CeleryTaskDispatcher(settings)
    return dispatcher_factory()


__all__ = [
    "get_pipeline_executor",
    "get_task_dispatcher",
    "get_task_store",
]
