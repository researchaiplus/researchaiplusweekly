"""Abstractions for dispatching background tasks."""

from __future__ import annotations

from typing import Protocol, Sequence

from newsletter.config import AppSettings


class TaskDispatcher(Protocol):
    """Interface responsible for scheduling background work."""

    def dispatch(self, task_id: str, urls: Sequence[str]) -> None:
        ...


class CeleryTaskDispatcher:
    """Dispatch newsletter processing tasks via Celery."""

    def __init__(self, settings: AppSettings) -> None:
        from newsletter.api.celery_tasks import generate_newsletter_task

        self._celery_task = generate_newsletter_task
        # Honour eager mode for local development/testing without a worker.
        if settings.celery.task_always_eager:
            self._celery_task.app.conf.task_always_eager = True

    def dispatch(self, task_id: str, urls: Sequence[str]) -> None:
        self._celery_task.delay(task_id=task_id, urls=list(urls))


__all__ = ["CeleryTaskDispatcher", "TaskDispatcher"]
