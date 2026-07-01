"""Best-effort website fetcher (FR-CB-2). Stdlib HTML→text so there is no heavy parser
dependency. Network failures degrade gracefully to empty text (the source URL still stands
as a citation target)."""

from __future__ import annotations

import contextlib
import ipaddress
import socket
from collections.abc import Iterable
from html.parser import HTMLParser
from urllib.parse import urlparse

import anyio
import httpcore
import httpx

from captureos.logging import get_logger

logger = get_logger(__name__)


def _ip_is_disallowed(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True for any address a server-side fetch must never reach (SSRF): loopback, private,
    link-local (169.254.169.254 cloud metadata), reserved, multicast, or unspecified."""
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


async def _is_safe_public_url(url: str) -> bool:
    """SSRF guard (per-hop verdict): only http(s) to a public IP. Blocks localhost, link-local
    (169.254.169.254 metadata), private, and reserved ranges.

    The DNS-rebinding TOCTOU window that used to remain here — httpx re-resolved the host
    independently at connect time, so a low-TTL attacker could pass this check then connect to an
    internal IP — is now closed by ``_PinnedResolvingBackend`` below, which re-resolves,
    re-validates, and connects to that exact validated IP at socket-connect time (NFR-2)."""
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
    return all(not _ip_is_disallowed(ipaddress.ip_address(info[4][0])) for info in infos)


class _PinnedResolvingBackend(httpcore.AnyIOBackend):
    """Network backend that resolves the host, refuses unless EVERY resolved address is a public IP,
    then connects to that validated IP — so the address the SSRF check approved is exactly the
    address the socket connects to. This closes the DNS-rebinding TOCTOU window: httpx/httpcore no
    longer re-resolve the host independently at connect time (the resolution and the connect use one
    ``getaddrinfo`` result, and we dial the literal IP, not the hostname).

    TLS is unaffected: httpcore derives the TLS ``server_hostname`` from the request origin (the
    hostname), NOT from the connect target, so SNI + certificate verification still validate against
    the original hostname for legitimate HTTPS fetches."""

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,  # noqa: ASYNC109 - override matches httpcore's backend API
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        try:
            infos = await anyio.to_thread.run_sync(
                lambda: socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
            )
        except Exception as exc:  # noqa: BLE001 - DNS failure → refuse (fetch degrades to empty)
            raise httpcore.ConnectError(f"DNS resolution failed for {host!r}") from exc
        pinned_ips: list[str] = []
        for info in infos:
            if _ip_is_disallowed(ipaddress.ip_address(info[4][0])):
                # A rebinding / private resolution at connect time → refuse before dialing (CON /
                # NFR-2 fail-closed). Never open a socket to an unvalidated address.
                raise httpcore.ConnectError(f"{host!r} resolved to a non-public address")
            pinned_ips.append(str(info[4][0]))
        if not pinned_ips:
            raise httpcore.ConnectError(f"no address for {host!r}")
        # Dial the validated IPs (not the hostname) in order, falling back across a multi-homed /
        # dual-stack host so a dead first address doesn't degrade a legitimate site to empty text.
        # Every candidate was checked public above, so the SSRF guarantee holds for whichever wins;
        # there is no second, unguarded hostname resolution.
        last_exc: Exception | None = None
        for ip in pinned_ips:
            try:
                return await super().connect_tcp(
                    ip,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except Exception as exc:  # noqa: BLE001 - try the next validated address, else re-raise
                last_exc = exc
        raise httpcore.ConnectError(f"could not connect to any address for {host!r}") from last_exc


class _PinnedTransport(httpx.AsyncHTTPTransport):
    """``AsyncHTTPTransport`` whose connection pool uses ``_PinnedResolvingBackend``. httpcore's
    ``AsyncConnectionPool`` accepts ``network_backend`` as a public argument but httpx's transport
    doesn't forward it, so swap it on the already-built pool (stable across httpx 0.28 / httpcore
    1.0). ``verify`` stays at its secure default (certificate verification stays ON)."""

    def __init__(self) -> None:
        super().__init__()
        self._pool._network_backend = _PinnedResolvingBackend()  # type: ignore[attr-defined]


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
        # every hop's resolved Location and refusing (graceful empty) the first hop that fails. The
        # _PinnedTransport additionally pins each connection to a re-validated public IP, so the
        # address checked here is the exact address dialed (closes the DNS-rebinding window).
        async with httpx.AsyncClient(
            transport=_PinnedTransport(),
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
