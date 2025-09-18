"""Lightweight client for issuing chat-completion requests via OpenRouter."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

import httpx

from newsletter.config import OpenRouterSettings

LOGGER = logging.getLogger(__name__)


class OpenRouterError(RuntimeError):
    """Raised when an OpenRouter request fails."""


class OpenRouterClient:
    """Synchronous chat-completions client with optional caching upstream."""

    def __init__(
        self,
        settings: OpenRouterSettings,
        transport: httpx.BaseTransport | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        headers = {
            "Authorization": f"Bearer {settings.api_key}",
            "Content-Type": "application/json",
        }
        self._client = client or httpx.Client(
            base_url=str(settings.base_url),
            timeout=settings.timeout_seconds,
            headers=headers,
            transport=transport,
        )
        self._model = settings.model

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OpenRouterClient:
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def complete(
        self,
        messages: Iterable[dict[str, str]],
        *,
        temperature: float = 0.0,
        response_format: dict[str, str] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self._model,
            "temperature": temperature,
            "messages": list(messages),
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            response = self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network failure guard
            LOGGER.error("OpenRouter request failed: %s", exc)
            raise OpenRouterError(str(exc)) from exc

        data = response.json()
        try:
            choice = data["choices"][0]
            message = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenRouterError("OpenRouter response missing completion text") from exc

        if not isinstance(message, str):
            raise OpenRouterError("OpenRouter completion payload is not textual")

        return message


__all__ = ["OpenRouterClient", "OpenRouterError"]
