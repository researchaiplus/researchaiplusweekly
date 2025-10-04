"""Celery application instance shared across worker processes."""

from __future__ import annotations

from functools import lru_cache

from celery import Celery

from newsletter.config import AppSettings, get_settings, setup_logging


@lru_cache(maxsize=1)
def _load_settings() -> AppSettings:
    return get_settings()


@lru_cache(maxsize=1)
def create_celery_app() -> Celery:
    settings = _load_settings()
    
    # Configure logging for Celery workers
    setup_logging()
    
    app = Celery(
        "newsletter",
        broker=settings.celery.broker_url,
        backend=settings.celery.result_backend,
    )
    app.conf.update(
        task_always_eager=settings.celery.task_always_eager,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
    )
    app.autodiscover_tasks(["newsletter.api"])
    return app


celery_app = create_celery_app()


__all__ = ["celery_app", "create_celery_app"]

# Ensure Celery tasks are registered when the application module is imported.
import newsletter.api.celery_tasks  # noqa: E402  pylint: disable=wrong-import-position
