"""Utilities for loading and validating URL manifests."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import AnyHttpUrl, ValidationError

from .models import InvalidUrlEntry, UrlEntry, UrlLoadResult

TRACKING_PREFIXES = ("utm_", "utm-", "ref", "gclid", "fbclid")


class UrlLoadError(RuntimeError):
    """Raised when the input manifest cannot be read."""


def _strip_inline_comment(line: str) -> str:
    if "#" not in line:
        return line
    prefix, _hash, _comment = line.partition("#")
    return prefix.strip()


def normalize_url(raw: str) -> str:
    """Normalize a URL for consistent deduplication."""

    parsed = urlparse(raw.strip())
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("URL must include scheme and host")

    netloc = parsed.netloc.lower()
    path = parsed.path or "/"

    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if key and not key.lower().startswith(TRACKING_PREFIXES)
    ]
    query = urlencode(query_pairs)

    normalized = urlunparse((parsed.scheme.lower(), netloc, path.rstrip("/") or "/", "", query, ""))
    return normalized


def _iter_manifest_lines(raw_lines: Iterable[str]) -> Iterable[tuple[int, str]]:
    for index, line in enumerate(raw_lines, start=1):
        cleaned = _strip_inline_comment(line).strip()
        if not cleaned:
            continue
        yield index, cleaned


def load_urls(manifest_path: str | Path) -> UrlLoadResult:
    """Load and validate URLs from a text manifest."""

    path = Path(manifest_path)
    try:
        contents = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - error branch covered via tests raising exception
        raise UrlLoadError(f"Failed to read manifest: {exc}") from exc

    result = UrlLoadResult()
    seen: set[AnyHttpUrl] = set()

    for line_number, candidate in _iter_manifest_lines(contents.splitlines()):
        try:
            normalized = normalize_url(candidate)
        except ValueError as exc:
            result.invalid_entries.append(
                InvalidUrlEntry(raw_url=candidate, reason=str(exc), source_line=line_number)
            )
            continue

        try:
            validated = AnyHttpUrl(normalized)
        except ValidationError as exc:  # pragma: no cover - guard for unexpected parsing issues
            result.invalid_entries.append(
                InvalidUrlEntry(raw_url=candidate, reason=str(exc), source_line=line_number)
            )
            continue

        if validated in seen:
            result.duplicate_urls.append(validated)
            continue

        seen.add(validated)
        result.entries.append(
            UrlEntry(raw_url=candidate, normalized_url=validated, source_line=line_number)
        )

    return result


__all__ = ["UrlLoadError", "load_urls", "normalize_url"]
