"""Utilities for calculating task progress."""

from __future__ import annotations

from typing import Sequence

from newsletter.api.models import TaskProgress
from newsletter.io.models import PipelineResult


def build_progress(urls: Sequence[str], result: PipelineResult) -> TaskProgress:
    total = len(urls)
    skipped = len(result.skipped_urls)
    invalid = len(result.invalid_urls)
    processed = min(result.success_count + skipped, total)
    remaining = max(total - processed, 0)
    failed = min(len(result.failed_urls) + invalid, remaining)
    return TaskProgress(total_urls=total, processed=processed, failed=failed)


__all__ = ["build_progress"]
