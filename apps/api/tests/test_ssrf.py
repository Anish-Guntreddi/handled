"""SSRF guard on server-side website fetch (NFR-2)."""

from __future__ import annotations

import pytest

from captureos.ingestion.website import _is_safe_public_url


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000",
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://10.0.0.5/internal",
        "ftp://example.com/file",
        "file:///etc/passwd",
        "http://[::1]/",
        "not-a-url",
    ],
)
async def test_blocks_unsafe_urls(url: str) -> None:
    assert await _is_safe_public_url(url) is False
