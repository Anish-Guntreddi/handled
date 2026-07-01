"""WS2 Knowledge Engine: discovery watchlist, run tracking, and the autonomous discovery agent
(org-less, cost-bounded, SSRF-guarded, dedupe-correct)."""

from __future__ import annotations

from captureos.agents.corpus_discovery import (
    KIND_ECFR,
    KIND_FEDERAL_REGISTER,
    VERDICT_DUPLICATE,
    VERDICT_NEW,
    CorpusIndexEntry,
    DiscoveryProposals,
    FederalRegisterSignal,
    ProposedTarget,
)
from captureos.config import Settings
from captureos.corpus.ingest import CorpusItem, ingest_corpus_item
from captureos.corpus.watchlist import DEFAULT_WATCHLIST, active_watchlist
from captureos.db.session import session_scope
from captureos.models.corpus_discovery import CorpusDiscoveryRun
from captureos.models.enums import CorpusDiscoveryRunStatus, CorpusDiscoveryTrigger
from captureos.providers import ModelTier
from captureos.providers.llm import MockLLM
from captureos.services.corpus_discovery import (
    DiscoveryOutcome,
    finalize_discovery_run,
    gather_corpus_index,
    is_allowlisted_https,
    open_discovery_run,
    plan_discovery,
    select_fetchable_targets,
)


def test_discovery_run_table_has_no_org_id_column() -> None:
    # Same isolation invariant as the corpus content tables: discovery is a platform op, so an
    # org-scoped query physically cannot reach these rows (no org_id column exists at all).
    assert "org_id" not in CorpusDiscoveryRun.__table__.columns


def test_default_watchlist_covers_the_four_smb_wedges() -> None:
    keys = {t.key for t in DEFAULT_WATCHLIST}
    assert {"set_asides", "sbir_sttr", "tax_credits", "industry_compliance"} <= keys
    # Federal-first rollout: every default topic is federal jurisdiction.
    assert all(t.jurisdiction == "federal" for t in DEFAULT_WATCHLIST)
    # Every topic names at least one authority + one query term to drive the sweep.
    assert all(t.authorities and t.query_terms for t in DEFAULT_WATCHLIST)


def test_watchlist_merges_operator_extras_deduped() -> None:
    settings = Settings(corpus_discovery_extra_topics="Davis-Bacon wages, SBIR")
    wl = active_watchlist(settings)
    assert len(wl.topics) == len(DEFAULT_WATCHLIST) + 2
    assert "extra:davis-bacon_wages" in wl.keys
    # Keys are unique even with overlapping labels.
    assert len(wl.keys) == len(set(wl.keys))


async def test_open_and_finalize_records_a_bounded_sweep() -> None:
    settings = Settings(corpus_discovery_token_budget=1234)
    async with session_scope() as session:
        run = await open_discovery_run(
            session, settings=settings, trigger=CorpusDiscoveryTrigger.manual
        )
        run_id = run.id
        assert run.status == CorpusDiscoveryRunStatus.running.value
        assert run.trigger == CorpusDiscoveryTrigger.manual.value
        assert run.watchlist_size == len(DEFAULT_WATCHLIST)
        assert run.token_budget == 1234

        outcome = DiscoveryOutcome(
            proposals_total=5,
            proposals_deduped=2,
            targets_fetched=3,
            created_count=1,
            updated_count=1,
            unchanged_count=1,
            tokens_used=900,
            skipped_count=1,
            skipped_reason="token_budget_exhausted",
        )
        await finalize_discovery_run(session, run, outcome)

    async with session_scope() as session:
        stored = await session.get(CorpusDiscoveryRun, run_id)
        assert stored is not None
        assert stored.status == CorpusDiscoveryRunStatus.succeeded.value
        assert stored.finished_at is not None
        assert stored.created_count == 1
        assert stored.updated_count == 1
        assert stored.unchanged_count == 1
        # Cost guard: what a bounded sweep skipped is recorded, never silently dropped.
        assert stored.skipped_count == 1
        assert stored.skipped_reason == "token_budget_exhausted"
        assert stored.tokens_used == 900


async def test_finalize_can_mark_a_failed_run() -> None:
    settings = Settings()
    async with session_scope() as session:
        run = await open_discovery_run(session, settings=settings)
        await finalize_discovery_run(
            session,
            run,
            DiscoveryOutcome(),
            status=CorpusDiscoveryRunStatus.failed,
            error="federal register unreachable",
        )
        assert run.status == CorpusDiscoveryRunStatus.failed.value
        assert run.error == "federal register unreachable"


# --- Tier: the cheap high-volume `bulk` lane exists and maps to the cheap model ---------------


async def test_bulk_tier_maps_to_a_distinct_cheap_model() -> None:
    settings = Settings()
    assert ModelTier.bulk.value == "bulk"
    # bulk resolves to the flash-lite lane, distinct from flash/pro (so triage cost tunes alone).
    assert settings.gemini_model_bulk == "gemini-2.5-flash-lite"
    assert settings.gemini_model_bulk != settings.gemini_model_flash
    resp = await MockLLM(settings).generate("triage this", tier=ModelTier.bulk)
    assert resp.model.endswith(settings.gemini_model_bulk)


# --- Discovery agent: triage + deduped, schema-valid fetch-target proposals -------------------


def _fr_signal(external_id: str, title: str, abstract: str = "") -> FederalRegisterSignal:
    return FederalRegisterSignal(
        external_id=external_id,
        citation=external_id,
        title=title,
        abstract=abstract,
        source_url=f"https://www.federalregister.gov/documents/{external_id}",
    )


async def test_plan_discovery_proposes_new_dedupes_existing_and_ignores_unrelated() -> None:
    settings = Settings()
    # A set-aside rule already in the corpus (should dedupe), a genuinely new SBIR rule (propose),
    # and an off-topic entry (should be triaged out entirely).
    async with session_scope() as session:
        await ingest_corpus_item(
            session,
            CorpusItem(
                authority=KIND_FEDERAL_REGISTER,
                doc_type="regulation",
                citation_label="2024-EXISTING",
                title="WOSB set-aside amendment",
                external_id="2024-EXISTING",
                text="women-owned small business set-aside rule text " * 10,
            ),
            embed=False,
        )

    entries = [
        _fr_signal("2024-EXISTING", "WOSB set-aside program amendment", "8(a) WOSB HUBZone rule"),
        _fr_signal("2024-NEWSBIR", "SBIR reauthorization", "small business innovation research"),
        _fr_signal("2024-NOISE", "Fisheries quota for Atlantic herring", "marine fishery limits"),
    ]

    async with session_scope() as session:
        corpus_index = await gather_corpus_index(session)
        proposals, tokens = await plan_discovery(
            session, settings=settings, entries=entries, corpus_index=corpus_index
        )

    fr_targets = {
        t.external_id: t for t in proposals.targets if t.kind == KIND_FEDERAL_REGISTER
    }
    # The off-topic entry never becomes a proposal (triaged out).
    assert "2024-NOISE" not in fr_targets
    # The already-current doc is deduped, not re-fetched.
    assert fr_targets["2024-EXISTING"].dedupe_verdict == VERDICT_DUPLICATE
    # The genuinely new rule is proposed as new, with a resolvable gov URL (anti-fabrication).
    new_target = fr_targets["2024-NEWSBIR"]
    assert new_target.dedupe_verdict == VERDICT_NEW
    assert is_allowlisted_https(new_target.url)
    # Mock tokens are 0 (deterministic offline path), but the accounting seam is wired.
    assert tokens == 0
    # Discovery expands beyond FR into codified CFR parts for the matched set-aside topic.
    assert any(t.kind == KIND_ECFR for t in proposals.targets)


def test_select_fetchable_targets_dedupes_and_bounds_without_silent_truncation() -> None:
    targets = [
        ProposedTarget(
            kind=KIND_FEDERAL_REGISTER,
            authority=KIND_FEDERAL_REGISTER,
            external_id="dup",
            reason="already have it",
            confidence=0.8,
            dedupe_verdict=VERDICT_DUPLICATE,
        ),
        *[
            ProposedTarget(
                kind=KIND_FEDERAL_REGISTER,
                authority=KIND_FEDERAL_REGISTER,
                external_id=f"new-{i}",
                reason="new rule",
                confidence=0.8,
                dedupe_verdict=VERDICT_NEW,
            )
            for i in range(4)
        ],
    ]
    selection = select_fetchable_targets(DiscoveryProposals(targets=targets), max_targets=2)
    assert selection.duplicate_count == 1  # dedupe drops the duplicate before fetch
    assert len(selection.accepted) == 2  # bounded sweep
    assert selection.skipped_count == 2  # the remaining fetchable targets are recorded, not dropped
    assert selection.skipped_reason == "max_targets_budget"


def test_no_bound_no_skip() -> None:
    targets = [
        ProposedTarget(
            kind=KIND_FEDERAL_REGISTER,
            authority=KIND_FEDERAL_REGISTER,
            external_id="new-1",
            reason="new",
            confidence=0.8,
            dedupe_verdict=VERDICT_NEW,
        )
    ]
    selection = select_fetchable_targets(DiscoveryProposals(targets=targets), max_targets=25)
    assert selection.skipped_count == 0
    assert selection.skipped_reason is None


# --- SSRF + anti-fabrication: proposed URLs must be https to an allowlisted gov host -----------


def test_allowlist_blocks_non_gov_and_non_https_and_metadata() -> None:
    assert is_allowlisted_https("https://www.federalregister.gov/documents/2024-1") is True
    assert is_allowlisted_https("https://www.ecfr.gov/current/title-48/part-19") is True
    # Non-https, non-allowlisted host, cloud metadata, and junk are all rejected.
    assert is_allowlisted_https("http://www.federalregister.gov/x") is False  # not https
    assert is_allowlisted_https("https://evil.example.com/x") is False  # not allowlisted
    assert is_allowlisted_https("https://169.254.169.254/latest/meta-data/") is False
    assert is_allowlisted_https("ftp://www.sba.gov/f") is False
    assert is_allowlisted_https(None) is False


async def test_discovery_index_reflects_only_current_docs() -> None:
    # gather_corpus_index feeds dedupe; it must project the CURRENT corpus (is_current) faithfully.
    async with session_scope() as session:
        await ingest_corpus_item(
            session,
            CorpusItem(
                authority=KIND_FEDERAL_REGISTER,
                doc_type="regulation",
                citation_label="2023-IDX",
                title="Indexed rule",
                external_id="2023-IDX",
                text="indexed corpus rule text " * 10,
            ),
            embed=False,
        )
    async with session_scope() as session:
        index = await gather_corpus_index(session)
    assert any(
        e.authority == KIND_FEDERAL_REGISTER and e.external_id == "2023-IDX" for e in index
    )
    assert all(isinstance(e, CorpusIndexEntry) for e in index)
