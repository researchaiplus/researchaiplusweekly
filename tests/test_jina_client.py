from collections.abc import Iterator

import httpx
import pytest

from newsletter.config import JinaReaderSettings
from newsletter.services.jina_client import JinaClient, JinaClientError


def _make_settings(**overrides: object) -> JinaReaderSettings:
    defaults = {
        "base_url": "https://r.jina.ai",
        "api_key": "test",
        "timeout_seconds": 1.0,
        "max_retries": 1,
    }
    defaults.update(overrides)
    return JinaReaderSettings(**defaults)


def test_fetch_success_json_payload() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"data": "body", "title": "T"})
    )
    settings = _make_settings()

    client = JinaClient(settings=settings, transport=transport)
    article = client.fetch("https://example.com")

    assert article.text == "body"
    assert article.title == "T"
    assert article.url == "https://example.com"


def test_fetch_retries_and_succeeds() -> None:
    attempts: Iterator[httpx.Response] = iter(
        [httpx.Response(500), httpx.Response(200, text="plain response")]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        try:
            return next(attempts)
        except StopIteration:  # pragma: no cover - defensive guard
            return httpx.Response(200, text="plain response")

    transport = httpx.MockTransport(handler)
    settings = _make_settings(max_retries=2)
    client = JinaClient(settings=settings, transport=transport)

    article = client.fetch("https://example.com/page")

    assert "plain response" in article.text


def test_fetch_failure_raises() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    settings = _make_settings(max_retries=0)
    client = JinaClient(settings=settings, transport=transport)

    with pytest.raises(JinaClientError):
        client.fetch("https://example.com")


def test_fetch_missing_text_raises() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"title": "t"}))
    settings = _make_settings()
    client = JinaClient(settings=settings, transport=transport)

    with pytest.raises(JinaClientError):
        client.fetch("https://example.com")
