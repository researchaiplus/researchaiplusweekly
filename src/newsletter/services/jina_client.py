"""HTTP client wrapper around the Jina Reader service."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

import httpx

from newsletter.config import JinaReaderSettings
from newsletter.io.models import ArticleContent

LOGGER = logging.getLogger(__name__)


class JinaClientError(RuntimeError):
    """Raised when the Jina Reader request fails."""


class JinaClient:
    """Small wrapper that adds retries, auth, and response parsing."""

    def __init__(
        self,
        settings: JinaReaderSettings,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._settings = settings
        self._max_retries = settings.max_retries
        self._client = client or httpx.Client(
            timeout=settings.timeout_seconds,
            headers=self._build_headers(settings),
            follow_redirects=True,
            transport=transport,
        )

    @staticmethod
    def _build_headers(settings: JinaReaderSettings) -> dict[str, str]:
        headers: dict[str, str] = {}
        if settings.api_key:
            headers["Authorization"] = f"Bearer {settings.api_key}"
        headers["Accept"] = "application/json, text/plain"
        return headers

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> JinaClient:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def _build_request_url(self, target_url: str) -> str:
        base = str(self._settings.base_url).rstrip("/")
        # Jina Reader expects the upstream URL appended after the base path.
        encoded_target = quote(target_url, safe=":/&?=%#")
        return f"{base}/{encoded_target}"

    def fetch(self, target_url: str) -> ArticleContent:
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.get(self._build_request_url(target_url))
                response.raise_for_status()
                return self._parse_response(target_url, response)
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_error = exc
                LOGGER.warning(
                    "Jina Reader request failed (attempt %s/%s): %s",
                    attempt + 1,
                    self._max_retries + 1,
                    exc,
                )
        message = "Failed to retrieve content from Jina Reader"
        if last_error:
            message = f"{message}: {last_error}"
        raise JinaClientError(message)

    @staticmethod
    def _parse_response(target_url: str, response: httpx.Response) -> ArticleContent:
        content_type = response.headers.get("content-type", "").lower()
        raw_payload: dict[str, Any] = {}
        title: str | None = None
        summary: str | None = None
        text: str | None = None

        if "application/json" in content_type:
            data = response.json()
            raw_payload = data if isinstance(data, dict) else {"data": data}
            text = _extract_text_field(data)
            title = _extract_title_field(data)
            summary = _extract_summary_field(data)
        else:
            text = response.text
            raw_payload = {"content": text}

        if not text:
            raise JinaClientError("Jina Reader response did not contain textual content")

        return ArticleContent(
            url=target_url, title=title, text=text, summary=summary, raw_payload=raw_payload
        )


def _extract_text_field(data: Any) -> str | None:
    if isinstance(data, dict):
        for key in ("data", "text", "content"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None


def _extract_title_field(data: Any) -> str | None:
    if isinstance(data, dict):
        title = data.get("title") or data.get("heading")
        if isinstance(title, str) and title.strip():
            return title.strip()
    return None


def _extract_summary_field(data: Any) -> str | None:
    if isinstance(data, dict):
        summary = data.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
    return None


__all__ = ["JinaClient", "JinaClientError"]
