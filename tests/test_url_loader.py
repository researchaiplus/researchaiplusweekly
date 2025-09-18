from pathlib import Path

import pytest

from newsletter.io.url_loader import UrlLoadError, load_urls, normalize_url


def test_load_urls_happy_path(tmp_path: Path) -> None:
    manifest = tmp_path / "urls.txt"
    manifest.write_text(
        """
        https://example.com/article
        https://example.com/article#fragment
        # comment line
        https://another.com/path?utm_source=newsletter&ref=123
        """.strip(),
        encoding="utf-8",
    )

    result = load_urls(manifest)

    assert result.valid_count == 2
    normalized_urls = {entry.normalized_url for entry in result.entries}
    assert "https://example.com/article" in normalized_urls
    assert "https://another.com/path" in normalized_urls
    assert result.duplicate_urls == ["https://example.com/article"]
    assert result.invalid_count == 0


def test_load_urls_invalid_entries(tmp_path: Path) -> None:
    manifest = tmp_path / "urls.txt"
    manifest.write_text("example.com\nftp://unsupported.com", encoding="utf-8")

    result = load_urls(manifest)

    assert result.valid_count == 0
    assert result.invalid_count == 2
    reasons = {entry.reason for entry in result.invalid_entries}
    assert "URL must include scheme and host" in reasons
    assert any("URL scheme" in reason for reason in reasons)


def test_load_urls_missing_file() -> None:
    with pytest.raises(UrlLoadError):
        load_urls("/nonexistent/path/urls.txt")


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://Example.com/some/path/", "https://example.com/some/path"),
        ("https://example.com?a=1&utm_source=foo&b=2", "https://example.com/?a=1&b=2"),
    ],
)
def test_normalize_url(raw: str, expected: str) -> None:
    assert normalize_url(raw) == expected
