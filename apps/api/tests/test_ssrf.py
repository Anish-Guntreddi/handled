"""SSRF guard on server-side website fetch (NFR-2).

Covers the two server-side fetch surfaces that take a URL:
* company-brain website ingestion (``ingestion/website.py``), and
* WS2 corpus-discovery agent-proposed fetch targets (``services/corpus_discovery.py``) — whose
  URLs are UNTRUSTED model output and so must pass the same guard, https-only + allowlisted host.
"""

from __future__ import annotations

import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import httpcore
import httpx
import pytest
from httpx import AsyncClient

from captureos.ingestion import website
from captureos.ingestion.website import _is_safe_public_url
from captureos.services import corpus_discovery as svc
from captureos.services.corpus_discovery import is_allowlisted_https, resolve_fetch_url
from tests.conftest import auth_headers, register

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


async def test_redirect_to_internal_metadata_is_not_followed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SSRF redirect-bypass regression: a PUBLIC homepage that ``302``-redirects to the cloud
    metadata address must NOT be followed. ``fetch_website_text`` re-validates every redirect hop
    through ``_is_safe_public_url`` and short-circuits to empty text, so the internal address is
    never requested and no internal body enters the result.

    Hermetic — ``httpx.MockTransport`` (no real network) plus a stub that keeps the metadata verdict
    REAL. Mutation note: the internal-host verdict delegates to the actual guard, so weakening
    ``_is_safe_public_url`` to allow link-local/private IPs would make the internal body leak and
    fail this test (the assertions are not satisfiable by a no-op guard)."""
    public = "http://public-homepage.test/"
    metadata = "http://169.254.169.254/latest/meta-data/"
    internal_secret = "AKIA_INTERNAL_ROOT_CREDENTIAL_LEAK"  # noqa: S105 - fake marker, not a secret
    requested: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        if request.url.host == "public-homepage.test":
            return httpx.Response(302, headers={"Location": metadata})
        # Only reachable if the guard wrongly let the redirect through — this body must never leak.
        return httpx.Response(200, text=f"<html><body>{internal_secret}</body></html>")

    transport = httpx.MockTransport(_handler)
    real_client = httpx.AsyncClient

    def _client_factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(website.httpx, "AsyncClient", _client_factory)

    # Force only the synthetic public host safe (so the fetch can start without real DNS); every
    # other host — including the metadata IP — keeps the REAL guard's verdict (link-local → False).
    real_guard = website._is_safe_public_url

    async def _guard(url: str) -> bool:
        if urlparse(url).hostname == "public-homepage.test":
            return True
        return await real_guard(url)

    monkeypatch.setattr(website, "_is_safe_public_url", _guard)

    result = await website.fetch_website_text(public)

    assert result == ""  # blocked redirect → graceful empty, identical to a first-hop guard refusal
    assert internal_secret not in result  # no internal body entered the result
    assert requested == [public]  # only the initial public GET; the metadata IP was never fetched
    assert not any("169.254.169.254" in u for u in requested)


# --- DNS-rebinding closure: the pinned network backend validates + dials at connect time ---


def _fake_getaddrinfo(ip: str):
    """A ``socket.getaddrinfo`` stub that resolves ANY host to ``ip`` on the requested port."""

    def _gai(host: str, port: int, *args: object, **kwargs: object) -> list:
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))]

    return _gai


async def test_pinned_backend_refuses_rebound_private_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DNS-rebinding closure (NFR-2): even a host that passed the per-hop guard is re-resolved by
    the pinned backend at CONNECT time and REFUSED (never dialed) when it now resolves to an
    internal address — so a low-TTL rebind to the cloud metadata IP can't be reached."""
    monkeypatch.setattr(website.socket, "getaddrinfo", _fake_getaddrinfo("169.254.169.254"))
    backend = website._PinnedResolvingBackend()
    with pytest.raises(httpcore.ConnectError):
        await backend.connect_tcp("rebound-to-metadata.test", 80)


async def test_pinned_backend_connects_to_resolved_ip_preserving_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The pin dials the exact resolved IP while httpx keeps the original ``Host`` header (the HTTP
    analog of the preserved TLS SNI/cert), so legitimate fetches still succeed through the pin."""
    received_hosts: list[str] = []

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - required BaseHTTPRequestHandler method name
            received_hosts.append(self.headers.get("Host", ""))
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:  # keep the test output quiet
            pass

    server = HTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        # Resolve the fake host to loopback and (only for this test) treat loopback as allowed, so
        # the pin exercises a real connect to a local server without the guard refusing it.
        monkeypatch.setattr(website.socket, "getaddrinfo", _fake_getaddrinfo("127.0.0.1"))
        monkeypatch.setattr(website, "_ip_is_disallowed", lambda ip: False)
        async with httpx.AsyncClient(
            transport=website._PinnedTransport(), follow_redirects=False
        ) as pinned_client:
            resp = await pinned_client.get(f"http://pinned-legit.test:{port}/")
        assert resp.status_code == 200 and resp.text == "ok"
        # Dialed 127.0.0.1 (the pin) but sent Host: pinned-legit.test — hostname preserved.
        assert received_hosts == [f"pinned-legit.test:{port}"]
    finally:
        server.shutdown()
        thread.join(timeout=2)


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


# --- WS3 onboarding: website enrichment stays behind the SSRF guard (D · Onboarding) ---


async def test_onboarding_website_enrichment_goes_through_ssrf_guard(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The wizard's ``websiteUrl`` reaches the brain ONLY via the guarded fetch. Submitting a cloud
    metadata URL must (a) be routed through ``_is_safe_public_url`` and (b) fetch nothing — the run
    still succeeds (graceful degrade), never crawling the internal address."""
    verdicts: dict[str, bool] = {}
    real_guard = website._is_safe_public_url

    async def _spy(url: str) -> bool:
        allowed = await real_guard(url)  # keep the real verdict (metadata URL → False)
        verdicts[url] = allowed
        return allowed

    monkeypatch.setattr(website, "_is_safe_public_url", _spy)

    tokens = await register(client, "ssrf-onb@example.com", org_name="Placeholder LLC")
    me = await client.get("/api/v1/auth/me", headers=auth_headers(tokens))
    org_id = me.json()["orgs"][0]["orgId"]

    metadata = "http://169.254.169.254/latest/meta-data/"
    resp = await client.post(
        f"/api/v1/orgs/{org_id}/onboarding",
        json={"companyName": "SSRF Co", "websiteUrl": metadata},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 202, resp.text
    run = await client.get(
        f"/api/v1/orgs/{org_id}/workflow-runs/{resp.json()['workflowRunId']}",
        headers=auth_headers(tokens),
    )
    assert run.json()["status"] == "succeeded", run.text  # degraded gracefully, did not crash
    # The onboarding path consulted the SSRF guard for this URL and the guard REFUSED it, so the
    # fetch short-circuited before any HTTP request to the internal metadata address.
    assert verdicts.get(metadata) is False


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
