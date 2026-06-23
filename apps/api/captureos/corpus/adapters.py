"""Corpus source adapters — each yields normalized ``CorpusItem``s for ingestion.

Free .gov APIs carry the bulk (eCFR for CFR/FAR, Federal Register for rule changes); Firecrawl
handles the HTML/scrape-only long tail (forms/guidance libraries). The network methods are the
live integration layer (``# pragma: no cover`` — validated against the real services in prod);
the ingestion framework that consumes their output is unit-tested.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

import httpx

from captureos.config import Settings
from captureos.corpus.ingest import CorpusItem
from captureos.logging import get_logger
from captureos.models.enums import CorpusAuthority, CorpusDocType

logger = get_logger(__name__)


@runtime_checkable
class CorpusAdapter(Protocol):
    name: str

    async def fetch(self) -> list[CorpusItem]: ...


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


class FederalRegisterAdapter:
    """Recent final rules from the Federal Register API (free, no key, clean JSON)."""

    name = CorpusAuthority.federal_register.value

    def __init__(self, per_page: int = 20) -> None:
        self._per_page = per_page

    async def fetch(self) -> list[CorpusItem]:  # pragma: no cover - live network
        url = "https://www.federalregister.gov/api/v1/documents.json"
        params: dict[str, str | int] = {
            "per_page": self._per_page,
            "order": "newest",
            "conditions[type][]": "RULE",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        items: list[CorpusItem] = []
        for d in data.get("results", []):
            text = (d.get("abstract") or d.get("title") or "").strip()
            doc_num = d.get("document_number")
            if not text or not doc_num:
                continue
            items.append(
                CorpusItem(
                    authority=self.name,
                    doc_type=CorpusDocType.regulation.value,
                    citation_label=d.get("citation") or doc_num,
                    title=(d.get("title") or "")[:1000],
                    external_id=doc_num,
                    text=text,
                    source_url=d.get("html_url"),
                    effective_date=_parse_date(d.get("effective_on")),
                )
            )
        return items


class EcfrAdapter:
    """CFR/FAR text from the eCFR versioner API (free, no key).

    Targets are (title, part) pairs so fetches stay bounded and relevant — e.g. ('48', '19')
    is FAR small-business programs. An empty part fetches the whole title (large)."""

    name = CorpusAuthority.ecfr.value

    def __init__(self, targets: list[tuple[str, str]]) -> None:
        self._targets = targets

    async def fetch(self) -> list[CorpusItem]:  # pragma: no cover - live network
        items: list[CorpusItem] = []
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Use each title's actual latest published date (not "today" — eCFR has no future data).
            meta = (await client.get("https://www.ecfr.gov/api/versioner/v1/titles.json")).json()
            latest = {
                str(t.get("number")): t.get("up_to_date_as_of") or t.get("latest_amended_on")
                for t in meta.get("titles", [])
            }
            for title, part in self._targets:
                as_of = latest.get(title)
                if not as_of:
                    logger.warning("corpus.ecfr_no_date", title=title)
                    continue
                url = f"https://www.ecfr.gov/api/versioner/v1/full/{as_of}/title-{title}.xml"
                params = {"part": part} if part else None
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning(
                        "corpus.ecfr_skip", title=title, part=part, code=resp.status_code
                    )
                    continue  # one unavailable part must not abort the rest
                items.extend(_parse_ecfr_sections(resp.text, title))
        return items


def _parse_ecfr_sections(xml_text: str, title: str) -> list[CorpusItem]:  # pragma: no cover
    # defusedxml hardens against XXE / billion-laughs — never parse XML with stdlib ElementTree,
    # even from a trusted source (MITM / compromised endpoint / redirect are still possible).
    from defusedxml.ElementTree import fromstring  # type: ignore[import-untyped]

    items: list[CorpusItem] = []
    root = fromstring(xml_text)
    for div in root.iter("DIV8"):  # DIV8 = a CFR section
        section = div.get("N", "")
        head = (div.findtext("HEAD") or "").strip()
        text = " ".join(t.strip() for t in div.itertext() if t and t.strip())
        if not text:
            continue
        items.append(
            CorpusItem(
                authority=CorpusAuthority.ecfr.value,
                doc_type=CorpusDocType.regulation.value,
                citation_label=f"{title} CFR {section}".strip(),
                title=(head or f"{title} CFR {section}")[:1000],
                external_id=f"{title}-{section}",
                text=text[:50_000],
                source_url=f"https://www.ecfr.gov/current/title-{title}",
            )
        )
    return items


class FirecrawlAdapter:
    """Scrape HTML/JS form & guidance pages to clean markdown via the Firecrawl API."""

    name = CorpusAuthority.firecrawl.value

    def __init__(self, api_key: str, urls: list[str]) -> None:
        self._api_key = api_key
        self._urls = urls

    async def fetch(self) -> list[CorpusItem]:  # pragma: no cover - live network
        items: list[CorpusItem] = []
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=90.0) as client:
            for url in self._urls:
                resp = await client.post(
                    "https://api.firecrawl.dev/v1/scrape",
                    headers=headers,
                    json={"url": url, "formats": ["markdown"]},
                )
                resp.raise_for_status()
                markdown = (resp.json().get("data") or {}).get("markdown", "").strip()
                if not markdown:
                    continue
                items.append(
                    CorpusItem(
                        authority=CorpusAuthority.firecrawl.value,
                        doc_type=CorpusDocType.form.value,
                        citation_label=url,
                        title=url,
                        external_id=url,
                        text=markdown,
                        source_url=url,
                    )
                )
        return items


@dataclass(slots=True)
class PdfSource:
    url: str
    authority: str
    citation_label: str
    title: str
    doc_type: str = CorpusDocType.publication.value


# Built-in small-business "get money" PDFs (stable IRS URLs). Operators add more (e.g. the current
# SBA SBIR/STTR Policy Directive, NIST SP 800-171) via CORPUS_PDF_EXTRA_URLS.
_DEFAULT_PDF_SOURCES: list[PdfSource] = [
    PdfSource(
        url="https://www.irs.gov/pub/irs-pdf/p334.pdf",
        authority=CorpusAuthority.irs.value,
        citation_label="IRS Pub 334",
        title="Tax Guide for Small Business",
    ),
    PdfSource(
        url="https://www.irs.gov/pub/irs-pdf/i6765.pdf",
        authority=CorpusAuthority.irs.value,
        citation_label="IRS Form 6765 Instructions",
        title="Credit for Increasing Research Activities (R&D tax credit)",
    ),
]


def extract_pdf_text(data: bytes) -> str:
    """Extract text from a PDF byte string (used by the PDF corpus adapter)."""
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


class PdfAdapter:
    """Download public-domain PDFs (IRS pubs, SBA SBIR/STTR directives, NIST SPs) and extract text.

    Unlocks the GET-MONEY pillar (tax credits, SBIR) and NIST/CMMC — none of which have an eCFR
    equivalent. Sources are OPERATOR-configured URLs (not user input), so this is not a user-facing
    SSRF surface; we still require https and isolate parse failures."""

    name = "pdf"

    def __init__(self, sources: list[PdfSource]) -> None:
        self._sources = sources

    async def fetch(self) -> list[CorpusItem]:  # pragma: no cover - live network
        items: list[CorpusItem] = []
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            for src in self._sources:
                if not src.url.lower().startswith("https://"):
                    logger.warning("corpus.pdf_skip_insecure", url=src.url)
                    continue
                resp = await client.get(src.url)
                if resp.status_code != 200:
                    logger.warning("corpus.pdf_skip", url=src.url, code=resp.status_code)
                    continue
                try:
                    text = extract_pdf_text(resp.content)
                except Exception as exc:  # noqa: BLE001 - a bad PDF must not abort the batch
                    logger.error("corpus.pdf_parse_failed", url=src.url, error=str(exc))
                    continue
                if not text:
                    continue
                items.append(
                    CorpusItem(
                        authority=src.authority,
                        doc_type=src.doc_type,
                        citation_label=src.citation_label,
                        title=src.title,
                        external_id=src.url,
                        text=text,
                        source_url=src.url,
                    )
                )
        return items


def enabled_adapters(settings: Settings) -> list[CorpusAdapter]:
    """The adapters to run, derived from config. Firecrawl only when a key + URLs are set."""
    adapters: list[CorpusAdapter] = []
    if settings.corpus_ecfr_target_list:
        adapters.append(EcfrAdapter(settings.corpus_ecfr_target_list))
    adapters.append(FederalRegisterAdapter())
    if settings.firecrawl_api_key and settings.corpus_firecrawl_url_list:
        adapters.append(
            FirecrawlAdapter(settings.firecrawl_api_key, settings.corpus_firecrawl_url_list)
        )
    # GET-MONEY pillar: built-in IRS pubs + any operator-added PDFs (SBIR directive, NIST).
    pdf_sources = list(_DEFAULT_PDF_SOURCES) + [
        PdfSource(url=url, authority=CorpusAuthority.manual.value, citation_label=url, title=url)
        for url in settings.corpus_pdf_extra_url_list
    ]
    if pdf_sources:
        adapters.append(PdfAdapter(pdf_sources))
    return adapters
