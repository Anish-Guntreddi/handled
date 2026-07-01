"""Best-effort website fetcher (FR-CB-2). Stdlib HTML→text so there is no heavy parser
dependency. Network failures degrade gracefully to empty text (the source URL still stands
as a citation target)."""

from __future__ import annotations

import contextlib
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import anyio
import httpx

from captureos.logging import get_logger

logger = get_logger(__name__)


async def _is_safe_public_url(url: str) -> bool:
    """SSRF guard: only http(s) to a public IP. Blocks localhost, link-local
    (169.254.169.254 metadata), private, and reserved ranges. Residual DNS-rebinding
    risk remains without IP pinning, which httpx does not expose simply (NFR-2)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = await anyio.to_thread.run_sync(
            lambda: socket.getaddrinfo(parsed.hostname, port, proto=socket.IPPROTO_TCP)
        )
    except Exception:  # noqa: BLE001 - DNS failure → treat as unreachable, degrade gracefully
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


# Bound on manually-followed redirect hops (each one is re-validated by the SSRF guard).
_MAX_REDIRECTS = 5

_SKIP_TAGS = {"script", "style", "noscript", "svg", "head"}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _SKIP_TAGS:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip == 0:
            text = data.strip()
            if text:
                self.parts.append(text)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    with contextlib.suppress(Exception):  # malformed HTML should not crash ingestion
        parser.feed(html)
    return "\n".join(parser.parts)


async def fetch_website_text(
    url: str,
    *,
    max_chars: int = 20_000,
    timeout: float = 10.0,  # noqa: ASYNC109 - httpx uses its own timeout, not asyncio.timeout
) -> str:
    if not await _is_safe_public_url(url):
        logger.info("website.blocked_url", url=url, reason="ssrf_guard")
        return ""
    try:
        # SSRF hardening (NFR-2): do NOT let httpx auto-follow redirects — a public homepage that
        # 302s to an internal address (169.254.169.254 metadata, 10.x, 127.0.0.1, link-local) would
        # be fetched unguarded. Follow manually in a bounded loop, re-running _is_safe_public_url on
        # every hop's resolved Location and refusing (graceful empty) the first hop that fails.
        async with httpx.AsyncClient(
            follow_redirects=False,
            timeout=timeout,
            headers={"User-Agent": "CaptureOS/0.1 (+https://captureos.app)"},
        ) as client:
            current = url
            for _hop in range(_MAX_REDIRECTS + 1):  # initial request + up to _MAX_REDIRECTS hops
                resp = await client.get(current)
                if not resp.is_redirect:  # 2xx/other: raise on 4xx/5xx, else return the body
                    resp.raise_for_status()
                    return html_to_text(resp.text)[:max_chars]
                # ``is_redirect`` guarantees a Location header; resolve relative → absolute.
                next_url = str(httpx.URL(current).join(resp.headers["location"]))
                if not await _is_safe_public_url(next_url):
                    logger.info(
                        "website.blocked_redirect",
                        from_url=current,
                        to_url=next_url,
                        reason="ssrf_guard",
                    )
                    return ""  # never fetch the unvalidated host — degrade like the guard-refusal
                current = next_url
            logger.info("website.too_many_redirects", url=url, max_redirects=_MAX_REDIRECTS)
            return ""
    except Exception as exc:  # noqa: BLE001 - graceful degradation (NFR-7/8)
        logger.info("website.fetch_failed", url=url, error=str(exc))
        return ""
