"""Shared task processing logic reusable by HTTP handlers and Celery workers."""

from __future__ import annotations

from datetime import datetime

from newsletter.api.models import ResultMetadata, TaskProgress, TaskStatus
from newsletter.api.progress import build_progress
from newsletter.api.pipeline_executor import PipelineExecutor
from newsletter.api.task_store import TaskStore
from newsletter.io.models import PipelineResult
from newsletter.pipeline.markdown_renderer import MarkdownRenderer


def process_pipeline_result(
    *,
    task_id: str,
    urls: list[str],
    task_store: TaskStore,
    pipeline_result: PipelineResult,
) -> None:
    """Persist a successful pipeline execution to the task store."""
    progress = build_progress(urls, pipeline_result)
    markdown = MarkdownRenderer().render(pipeline_result.entries)
    metadata = ResultMetadata(
        generated_at=datetime.utcnow(),
        total_processed=pipeline_result.success_count,
        topics=sorted({entry.topic.value for entry in pipeline_result.entries}),
    )
    task_store.mark_completed(
        task_id,
        markdown_content=markdown,
        metadata=metadata,
        progress=progress,
    )


def process_pipeline_failure(
    *,
    task_id: str,
    urls: list[str],
    task_store: TaskStore,
    error: Exception,
) -> None:
    """Record a pipeline failure to the task store."""

    progress = TaskProgress(total_urls=len(urls), processed=0, failed=len(urls))
    task_store.mark_failed(task_id, error=str(error), progress=progress)


def is_terminal_status(status: TaskStatus) -> bool:
    return status in {TaskStatus.COMPLETED, TaskStatus.FAILED}


def execute_pipeline_task(
    *,
    task_id: str,
    urls: list[str],
    task_store: TaskStore,
    executor: PipelineExecutor,
) -> None:
    """Run the newsletter pipeline and persist its outcome."""

    task_store.mark_processing(task_id)
    try:
        result = executor.execute(urls)
    except Exception as exc:  # pragma: no cover - defensive guard for unexpected failures
        process_pipeline_failure(task_id=task_id, urls=urls, task_store=task_store, error=exc)
        return

    try:
        process_pipeline_result(
            task_id=task_id,
            urls=urls,
            task_store=task_store,
            pipeline_result=result,
        )
    except Exception as exc:  # pragma: no cover - ensure we record any persistence failures
        process_pipeline_failure(task_id=task_id, urls=urls, task_store=task_store, error=exc)


__all__ = [
    "is_terminal_status",
    "process_pipeline_failure",
    "process_pipeline_result",
]
