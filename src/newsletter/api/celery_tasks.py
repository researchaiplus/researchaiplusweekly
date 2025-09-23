"""Celery task definitions for newsletter processing."""

from __future__ import annotations

from newsletter.api.celery_app import celery_app
from newsletter.api.dependencies import get_pipeline_executor, get_task_store
from newsletter.api.service import execute_pipeline_task


@celery_app.task(name="newsletter.generate_newsletter")
def generate_newsletter_task(task_id: str, urls: list[str]) -> None:
    """Entry point executed by Celery workers."""

    task_store = get_task_store()
    executor = get_pipeline_executor()
    execute_pipeline_task(task_id=task_id, urls=urls, task_store=task_store, executor=executor)


__all__ = ["generate_newsletter_task"]
