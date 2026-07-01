"""SSRF guard on server-side website fetch (NFR-2).

Covers the two server-side fetch surfaces that take a URL:
* company-brain website ingestion (``ingestion/website.py``), and
* WS2 corpus-discovery agent-proposed fetch targets (``services/corpus_discovery.py``) — whose
  URLs are UNTRUSTED model output and so must pass the same guard, https-only + allowlisted host.
"""

from __future__ import annotations

import pytest

from captureos.ingestion.website import _is_safe_public_url
from captureos.services import corpus_discovery as svc
from captureos.services.corpus_discovery import is_allowlisted_https, resolve_fetch_url

_UNSAFE_URLS = [
    "http://localhost:8000",
    "http://127.0.0.1/",
    "http://169.254.169.254/latest/meta-data/",  # cloud metadata
    "http://10.0.0.5/internal",
    "ftp://example.com/file",
    "file:///etc/passwd",
    "http://[::1]/",
    "not-a-url",
]


@pytest.mark.parametrize("url", _UNSAFE_URLS)
async def test_blocks_unsafe_urls(url: str) -> None:
    assert await _is_safe_public_url(url) is False


# --- WS2 discovery: agent-proposed URLs go through the SSRF guard (https + allowlisted host) ---


@pytest.mark.parametrize("url", _UNSAFE_URLS)
async def test_discovery_urls_go_through_ssrf_guard(url: str) -> None:
    """Every unsafe URL the website guard blocks is ALSO refused for a discovery fetch target."""
    assert await resolve_fetch_url(url) is False


def test_discovery_url_gate_requires_https_and_allowlisted_gov_host() -> None:
    # Allowlisted gov hosts over https pass the pure gate.
    assert is_allowlisted_https("https://www.federalregister.gov/documents/2024-1") is True
    assert is_allowlisted_https("https://www.ecfr.gov/current/title-48/part-19") is True
    assert is_allowlisted_https("https://www.irs.gov/pub/irs-pdf/f6765.pdf") is True
    # Non-https, non-allowlisted host, cloud metadata, junk, and None are all rejected.
    assert is_allowlisted_https("http://www.federalregister.gov/x") is False  # not https
    assert is_allowlisted_https("https://evil.example.com/x") is False  # not allowlisted
    assert is_allowlisted_https("https://federalregister.gov.evil.com/x") is False  # look-alike
    assert is_allowlisted_https("https://169.254.169.254/latest/meta-data/") is False
    assert is_allowlisted_https("ftp://www.sba.gov/f") is False
    assert is_allowlisted_https(None) is False


async def test_resolve_fetch_url_invokes_public_ip_guard_for_allowlisted_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An allowlisted https gov host still MUST pass the shared public-IP SSRF check — resolve
    delegates to ``_is_safe_public_url`` (patched here for a hermetic, network-free assertion)."""
    seen: list[str] = []

    async def _guard(url: str, *, allow: bool) -> bool:
        seen.append(url)
        return allow

    good = "https://www.ecfr.gov/current/title-13/part-121"

    monkeypatch.setattr(svc, "_is_safe_public_url", lambda u: _guard(u, allow=True))
    assert await resolve_fetch_url(good) is True

    seen.clear()
    monkeypatch.setattr(svc, "_is_safe_public_url", lambda u: _guard(u, allow=False))
    assert await resolve_fetch_url(good) is False
    assert seen == [good]  # the guard was actually consulted (not short-circuited)
