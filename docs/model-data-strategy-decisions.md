# Model & Data Strategy — Decision Page

One place to make the open calls, each with the consensus recommendation. Backed by:
`govdata-kb-design.md`, `selfhosted-models-analysis.md`, `codex-selfhosted-models.md`,
`govdata-architecture-research.md`. Reconciled across Claude + a design/research workflow + Codex.

---

## Already settled (no decision needed — locked by consensus)

- **Knowledge base:** org-less `CorpusDocument`/`CorpusChunk` tables (isolation = schema fact);
  two-query retrieval merged in Python; lazy org-scoped `Source` at citation time; hybrid
  collection (APIs direct, Firecrawl for the HTML long tail). See `govdata-kb-design.md`.
- **Model routing principle:** frontier Claude for high-stakes reasoning (`ModelTier.pro` agents —
  bid/no-bid, requirement interpretation, narrative); cheap models for extraction; deterministic
  tooling (no LLM) for PDF/form-fill. The provider seam supports adding local backends with **zero
  architecture change**.
- **Self-host economics:** break-even is **tens-of-thousands to ~150K extractions/month** (driven
  by which API you compare against) — **far above current volume**, so **cost never justifies
  self-hosting now**. Self-hosting is a *privacy/compliance capability*, not a cost lever.

---

## Decision 1 — 🔴 Regulation citation: point-in-time vs. latest  *(blocks KB Phase 1)*

When an agent cites a regulation, does it cite the version **in force when the filing was
submitted** (point-in-time) or **always the latest**?

- **Recommendation: keep all historical versions; default retrieval to current; support "as-of"
  retrieval for citing past filings.**
- Why: active work wants current law (default), but a filing complied with the rules in force
  *then* — if audited later you must cite *that* version, and discarding superseded versions makes
  it unrecoverable. Storage cost is trivial (text); the `WHERE is_current` partial index keeps the
  hot path fast regardless of version count.
- **This must be decided before Phase-1 ingest** (it determines whether you retain versions from
  day one). Coupled sub-decision: retention = keep-all (enables point-in-time) vs current + last-N.

**Your call:** ☐ point-in-time + keep-all (recommended)  ☐ latest-only

---

## Decision 2 — Self-host routing & timing

How to split work across local/open vs. frontier, and when to build each piece.

**Recommended tiered design (all behind the existing seam):**

| Lane | Run on | When to build |
|---|---|---|
| PDF parse + **form-fill** | **Deterministic tooling, no LLM** | Already $0 — build as normal product work |
| **OCR** of scanned forms `LocalDocparse` can't read | **Self-hosted open** (PaddleOCR / PaddleOCR-VL 0.9B, Apache-2.0) | **Volume-independent** — build when a customer wants the privacy guarantee |
| **Extraction / field-mapping** | **Frontier flash** (Gemini Flash / Haiku) now | Move to self-hosted (Qwen3-4B/Phi-4 + constrained JSON via vLLM) only past the ~tens-of-thousands/mo break-even |
| **High-stakes reasoning** (bid/no-bid, requirements, narrative) | **Frontier Claude (`pro`)** | Keep on frontier — quality lowers legal risk and is cheaper at your volume |
| **"Sovereign" fully self-hosted** | open LLM + local OCR, air-gapped | **Premium tier** for ITAR / no-third-party-AI / air-gapped customers, priced on compliance-unlock |

- The **privacy win (local OCR) is decoupled from the cost math** — ship it on a customer trigger,
  not a volume trigger.
- Mid-ground for the CUI majority: a **Bedrock/Vertex Enterprise** tier (zero-retention + data
  residency) without running your own GPUs.
- Routing change is near-zero: add `SelfHostedLLM` + `LocalOCRDocparse` providers; make `get_llm()`
  tier-aware (one touch in `agents/base.py`). Flipping a lane = an env change.

**Your call:**
- ☐ Adopt the tiered design (recommended)  ☐ other
- Build the **local-OCR provider** now (a privacy selling point for govcon) or defer? ☐ now ☐ later
- Offer the **Sovereign** self-hosted tier as a premium SKU? ☐ yes ☐ later

---

## Decision 3 — Firecrawl budget *(minor)*

Free tier for the Phase-1 pilot (measure page counts); **Standard ($83/mo)** as the production
baseline (one full GSA-forms crawl exhausts the free 1,000 credits).

**Your call:** ☐ confirm Standard for production  ☐ other

---

## What unblocks once you decide

Decision 1 unblocks **KB Phase 1** (corpus tables + migration + `corpus_retrieve()` + isolation
test suite + one grounded agent). Decisions 2–3 shape the model/collection providers but don't
block Phase 1 (the seam stays provider-agnostic). Recommended next build after these calls:
**KB Phase 1**, then the local-OCR provider if Decision 2 says "now."
