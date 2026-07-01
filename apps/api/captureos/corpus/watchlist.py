"""Discovery watchlist — the authorities/topics a future discovery agent monitors for change.

WS2's autonomous discovery agent watches these SMB-compliance areas (set-asides, SBIR/STTR, tax
credits, industry compliance) for newly-published/changed regulation, then proposes concrete fetch
targets that flow into the EXISTING ``adapters -> ingest_corpus_item`` pipeline. This module only
declares *what to watch* (data, not behavior) so the watchlist is unit-testable and config-driven
before the agent that consumes it lands. Federal-first: every default topic is ``jurisdiction=
'federal'``; state/local topics are added later (per-source ``jurisdiction`` already exists).

Nothing here is org-scoped — the corpus is shared across all tenants by design.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from captureos.config import Settings
from captureos.models.enums import CorpusAuthority


@dataclass(slots=True, frozen=True)
class WatchTopic:
    """One tracked SMB-compliance area the discovery agent sweeps for change.

    ``key`` is a stable id (dedupe/telemetry). ``authorities`` are the sources most likely to
    publish a change in this area (Federal Register for new rules, eCFR for the codified text,
    IRS/SBA for pubs). ``cfr_hints`` are ``title:part`` pairs the agent can propose as eCFR fetch
    targets; ``query_terms`` seed the Federal Register / signal triage. All advisory — the agent
    still dedupes proposals against the corpus before anything is fetched.
    """

    key: str
    label: str
    authorities: tuple[str, ...]
    query_terms: tuple[str, ...] = ()
    cfr_hints: tuple[str, ...] = ()
    jurisdiction: str = "federal"


# Federal-first defaults covering the four SMB wedges the product sells on. Operators extend the
# watch surface with CORPUS_DISCOVERY_EXTRA_TOPICS (free-text topics) without a code change.
DEFAULT_WATCHLIST: tuple[WatchTopic, ...] = (
    WatchTopic(
        key="set_asides",
        label="Small-business set-asides & socioeconomic programs",
        authorities=(
            CorpusAuthority.federal_register.value,
            CorpusAuthority.ecfr.value,
            CorpusAuthority.sba.value,
        ),
        query_terms=("small business set-aside", "8(a)", "WOSB", "HUBZone", "SDVOSB"),
        cfr_hints=("48:19", "13:121", "13:124", "13:125", "13:126", "13:127"),
    ),
    WatchTopic(
        key="sbir_sttr",
        label="SBIR/STTR programs & policy directives",
        authorities=(
            CorpusAuthority.federal_register.value,
            CorpusAuthority.sba.value,
        ),
        query_terms=("SBIR", "STTR", "small business innovation research", "policy directive"),
    ),
    WatchTopic(
        key="tax_credits",
        label="SMB tax credits (R&D / §41, energy, hiring)",
        authorities=(
            CorpusAuthority.federal_register.value,
            CorpusAuthority.irs.value,
        ),
        query_terms=("research credit", "section 41", "small business tax credit", "Form 6765"),
    ),
    WatchTopic(
        key="industry_compliance",
        label="Industry compliance (NIST/CMMC, grants Uniform Guidance, SAM registration)",
        authorities=(
            CorpusAuthority.federal_register.value,
            CorpusAuthority.ecfr.value,
            CorpusAuthority.gsa.value,
        ),
        query_terms=(
            "CMMC",
            "NIST SP 800-171",
            "uniform guidance",
            "SAM registration",
            "suspension and debarment",
        ),
        cfr_hints=("2:200", "2:25", "2:170", "2:180", "48:52"),
    ),
)


@dataclass(slots=True)
class Watchlist:
    """The resolved watch surface for a discovery run: built-in topics + operator extras."""

    topics: list[WatchTopic] = field(default_factory=list)

    @property
    def keys(self) -> list[str]:
        return [t.key for t in self.topics]


def _extra_topics(settings: Settings) -> list[WatchTopic]:
    """Operator-added free-text topics → generic Federal Register watch topics (no CFR hints)."""
    out: list[WatchTopic] = []
    for raw in settings.corpus_discovery_extra_topic_list:
        slug = raw.lower().replace(" ", "_")[:64]
        out.append(
            WatchTopic(
                key=f"extra:{slug}",
                label=raw,
                authorities=(CorpusAuthority.federal_register.value,),
                query_terms=(raw,),
            )
        )
    return out


def active_watchlist(settings: Settings) -> Watchlist:
    """The full watch surface for a run: defaults + operator extras (deduped by key)."""
    seen: set[str] = set()
    topics: list[WatchTopic] = []
    for topic in (*DEFAULT_WATCHLIST, *_extra_topics(settings)):
        if topic.key in seen:
            continue
        seen.add(topic.key)
        topics.append(topic)
    return Watchlist(topics=topics)
