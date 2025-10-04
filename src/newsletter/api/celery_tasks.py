"""Celery task definitions for newsletter processing."""

from __future__ import annotations

import logging

from newsletter.api.celery_app import celery_app
from newsletter.api.dependencies import get_pipeline_executor, get_task_store
from newsletter.api.service import execute_pipeline_task

LOGGER = logging.getLogger(__name__)


@celery_app.task(name="newsletter.generate_newsletter")
def generate_newsletter_task(task_id: str, urls: list[str]) -> None:
    """Entry point executed by Celery workers."""
    
    LOGGER.info("Starting newsletter generation task %s with %d URLs", task_id, len(urls))
    
    task_store = get_task_store()
    executor = get_pipeline_executor()
    execute_pipeline_task(task_id=task_id, urls=urls, task_store=task_store, executor=executor)
    
    LOGGER.info("Completed newsletter generation task %s", task_id)


__all__ = ["generate_newsletter_task"]
