"""Autonomous corpus research/discovery agents (WS2 Knowledge Engine, batch/cron only).

Two cooperating ``Agent`` subclasses, split by cost lane (per docs/prd/ws0-agent-inventory.md):

* ``CorpusTriageAgent`` (``ModelTier.bulk`` — the cheapest long-context lane): scans the recent
  Federal Register feed against the watchlist and flags which entries are *relevant signals*.
  This is the high-volume pass, so it runs on the cheap triage model.
* ``CorpusDiscoveryAgent`` (``ModelTier.flash`` — the judgment lane): takes the triaged signals +
  the current corpus index and proposes concrete, schema-validated **fetch targets** (Federal
  Register doc id, CFR ``title:part``, PDF URL), each carrying a reason, a confidence, and a
  **dedupe verdict** (``new`` / ``update`` / ``duplicate``) against the corpus.

Neither agent fetches anything or writes to the corpus — they only decide *what* to fetch. The
service (``services/corpus_discovery.py``) resolves accepted targets through the SSRF guard and
hands them to the EXISTING adapters → ``ingest_corpus_item`` (which still decides created/updated/
unchanged). Anti-fabrication: a proposal whose URL is not an allowlisted, resolvable https gov
source is dropped by the service before any fetch.

Both agents are org-less (``AgentContext(org_id=None)``): discovery is a platform operation over
public-domain gov sources, never a per-tenant action. A deterministic ``mock_output`` path keeps
the whole sweep runnable offline (``LLM_PROVIDER=mock``).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from captureos.agents.base import Agent, AgentContext
from captureos.providers import ModelTier

# Dedupe verdicts a proposal can carry (before the ingest diff engine has the final say).
VERDICT_NEW = "new"  # nothing in the corpus for this (authority, external_id) → fetch
VERDICT_UPDATE = "update"  # corpus has related material; re-fetch so the diff can detect a change
VERDICT_DUPLICATE = "duplicate"  # already current in the corpus → do NOT fetch (dedupe skip)

# Target kinds map 1:1 to the existing adapters the service dispatches to.
KIND_FEDERAL_REGISTER = "federal_register"
KIND_ECFR = "ecfr"
KIND_PDF = "pdf"


# --------------------------------------------------------------------------------------
# Shared input views (serialized, so the agents stay pure over plain data)
# --------------------------------------------------------------------------------------
class FederalRegisterSignal(BaseModel):
    """One recent Federal Register entry, normalized from the existing adapter's ``CorpusItem``."""

    external_id: str  # FR document_number (immutable id)
    citation: str = ""
    title: str = ""
    abstract: str = ""
    source_url: str | None = None
    effective_date: str | None = None


class WatchTopicView(BaseModel):
    """A watchlist topic flattened for prompting/triage (from ``corpus/watchlist.py``)."""

    key: str
    label: str
    authorities: list[str] = Field(default_factory=list)
    query_terms: list[str] = Field(default_factory=list)
    cfr_hints: list[str] = Field(default_factory=list)


class CorpusIndexEntry(BaseModel):
    """One current corpus document, projected to the fields dedupe needs."""

    authority: str
    external_id: str
    citation: str = ""
    as_of: str | None = None


class TriagedSignal(FederalRegisterSignal):
    """A Federal Register signal the triage pass judged relevant, tagged with its topic."""

    matched_topic_key: str = ""
    triage_reason: str = ""


# --------------------------------------------------------------------------------------
# Triage agent (bulk tier)
# --------------------------------------------------------------------------------------
class TriageInput(BaseModel):
    entries: list[FederalRegisterSignal] = Field(default_factory=list)
    topics: list[WatchTopicView] = Field(default_factory=list)


class TriageHit(BaseModel):
    external_id: str
    matched_topic_key: str
    reason: str
    confidence: float  # 0-1


class TriageOutput(BaseModel):
    hits: list[TriageHit] = Field(default_factory=list)


def _haystack(sig: FederalRegisterSignal) -> str:
    return f"{sig.title}\n{sig.abstract}\n{sig.citation}".lower()


class CorpusTriageAgent(Agent[TriageInput, TriageOutput]):
    """Cheap high-volume pass: which recent FR entries touch a tracked SMB-compliance area?"""

    name = "corpus_triage"
    tier = ModelTier.bulk
    output_model = TriageOutput
    system_prompt = (
        "You triage the recent US Federal Register feed for a small-business compliance corpus. "
        "Given recent entries and a watchlist of tracked topics (each with query terms), flag the "
        "entries that plausibly change a tracked area (new/amended rule, reauthorization, new "
        "program). For each flagged entry return the single best-matching topic key, a one-line "
        "reason, and a 0-1 confidence. Be inclusive but not reckless — omit clearly unrelated "
        "entries. JSON only."
    )

    def build_prompt(self, data: TriageInput) -> str:
        topics = "\n".join(
            f"- {t.key} ({t.label}): terms={', '.join(t.query_terms)}" for t in data.topics
        )
        entries = "\n".join(
            f"- {e.external_id}: {e.title} | {e.abstract[:280]}" for e in data.entries
        )
        return (
            f"Watchlist topics:\n{topics}\n\nRecent Federal Register entries:\n{entries}\n\n"
            "Return hits[]: {external_id, matched_topic_key, reason, confidence (0-1)}. "
            "Only include entries that match a topic."
        )

    async def mock_output(self, ctx: AgentContext, data: TriageInput) -> TriageOutput:
        hits: list[TriageHit] = []
        for entry in data.entries:
            hay = _haystack(entry)
            best: tuple[float, WatchTopicView, list[str]] | None = None
            for topic in data.topics:
                matched = [term for term in topic.query_terms if term.lower() in hay]
                if not matched:
                    continue
                # Confidence scales with the number of distinct term hits (capped at 0.95).
                conf = min(0.95, 0.5 + 0.15 * len(matched))
                if best is None or conf > best[0]:
                    best = (conf, topic, matched)
            if best is not None:
                conf, topic, matched = best
                hits.append(
                    TriageHit(
                        external_id=entry.external_id,
                        matched_topic_key=topic.key,
                        reason=f"matches {topic.key} on: {', '.join(matched[:4])}",
                        confidence=round(conf, 2),
                    )
                )
        return TriageOutput(hits=hits)


# --------------------------------------------------------------------------------------
# Discovery agent (flash tier) — the judgment step that emits deduped fetch targets
# --------------------------------------------------------------------------------------
class DiscoveryAgentInput(BaseModel):
    signals: list[TriagedSignal] = Field(default_factory=list)
    topics: list[WatchTopicView] = Field(default_factory=list)
    corpus_index: list[CorpusIndexEntry] = Field(default_factory=list)


class ProposedTarget(BaseModel):
    kind: str  # federal_register | ecfr | pdf
    authority: str
    external_id: str
    citation: str = ""
    title: str = ""
    url: str | None = None
    reason: str
    confidence: float  # 0-1
    watch_topic_key: str = ""
    dedupe_verdict: str  # new | update | duplicate


class DiscoveryProposals(BaseModel):
    targets: list[ProposedTarget] = Field(default_factory=list)


def _ecfr_url(title: str, part: str) -> str:
    base = f"https://www.ecfr.gov/current/title-{title}"
    return f"{base}/part-{part}" if part else base


class CorpusDiscoveryAgent(Agent[DiscoveryAgentInput, DiscoveryProposals]):
    """Judgment step: turn triaged signals into concrete, deduped, fetchable corpus targets."""

    name = "corpus_discovery"
    tier = ModelTier.flash
    output_model = DiscoveryProposals
    system_prompt = (
        "You expand a small-business compliance corpus. Given Federal Register signals that a "
        "tracked area changed, the watchlist, and the CURRENT corpus index, propose concrete fetch "
        "targets: the Federal Register document itself, and the codified CFR title:part(s) the "
        "change most likely touches. DEDUPE every proposal against the corpus index by "
        "(authority, external_id): mark it 'duplicate' if the corpus already has that exact "
        "current document (do not re-fetch), 'update' if the corpus has related material that "
        "should be re-checked for amendment, else 'new'. Never invent a document id or URL. "
        "JSON only."
    )

    def build_prompt(self, data: DiscoveryAgentInput) -> str:
        signals = "\n".join(
            f"- {s.external_id} [{s.matched_topic_key}]: {s.title} ({s.source_url})"
            for s in data.signals
        )
        index = "\n".join(
            f"- {c.authority}:{c.external_id} ({c.citation}) as_of={c.as_of}"
            for c in data.corpus_index[:200]
        )
        return (
            f"Triaged Federal Register signals:\n{signals}\n\n"
            f"Current corpus index (deduplicate against this):\n{index}\n\n"
            "Return targets[]: {kind (federal_register|ecfr|pdf), authority, external_id, "
            "citation, title, url, reason, confidence (0-1), watch_topic_key, dedupe_verdict "
            "(new|update|duplicate)}."
        )

    async def mock_output(
        self, ctx: AgentContext, data: DiscoveryAgentInput
    ) -> DiscoveryProposals:
        # Index of what the corpus already has, for dedupe.
        have_fr = {
            c.external_id for c in data.corpus_index if c.authority == KIND_FEDERAL_REGISTER
        }
        # eCFR docs are stored per-section (external_id like "48-19.502"); a title:part target is
        # deduped by whether the corpus already holds ANY current section under that title.
        have_ecfr_titles = {
            c.external_id.split("-", 1)[0]
            for c in data.corpus_index
            if c.authority == KIND_ECFR and "-" in c.external_id
        }
        topics_by_key = {t.key: t for t in data.topics}

        targets: list[ProposedTarget] = []
        seen_ecfr: set[str] = set()
        for sig in data.signals:
            # 1) The Federal Register document itself.
            verdict = VERDICT_DUPLICATE if sig.external_id in have_fr else VERDICT_NEW
            targets.append(
                ProposedTarget(
                    kind=KIND_FEDERAL_REGISTER,
                    authority=KIND_FEDERAL_REGISTER,
                    external_id=sig.external_id,
                    citation=sig.citation or sig.external_id,
                    title=sig.title,
                    url=sig.source_url,
                    reason=sig.triage_reason or f"new/changed rule under {sig.matched_topic_key}",
                    confidence=0.8,
                    watch_topic_key=sig.matched_topic_key,
                    dedupe_verdict=verdict,
                )
            )
            # 2) The codified CFR parts the matched topic points at (expanding beyond the hardcoded
            #    adapter list). Deduped by title presence; the ingest diff still decides unchanged.
            topic = topics_by_key.get(sig.matched_topic_key)
            if topic is None:
                continue
            for hint in topic.cfr_hints:
                title, _, part = hint.partition(":")
                title, part = title.strip(), part.strip()
                if not title or hint in seen_ecfr:
                    continue
                seen_ecfr.add(hint)
                ecfr_verdict = (
                    VERDICT_UPDATE if title in have_ecfr_titles else VERDICT_NEW
                )
                targets.append(
                    ProposedTarget(
                        kind=KIND_ECFR,
                        authority=KIND_ECFR,
                        external_id=f"{title}:{part}",
                        citation=f"{title} CFR part {part}".strip(),
                        title=f"{topic.label} — {title} CFR {part}".strip(),
                        url=_ecfr_url(title, part),
                        reason=f"{sig.matched_topic_key} change may touch {title} CFR {part}",
                        confidence=0.55,
                        watch_topic_key=topic.key,
                        dedupe_verdict=ecfr_verdict,
                    )
                )
        return DiscoveryProposals(targets=targets)
