# Self-Hosted Open Models for CaptureOS Filing/Extraction Subagents — Architect Recommendation

**Status:** Decision proposal (lead architect)
**Date:** 2026-06-22
**Scope:** Whether and how CaptureOS should use self-hosted open-source models for the filing/extraction subagents, vs. frontier Claude APIs.
**TL;DR:** Hybrid, tiered. Keep frontier Claude for high-stakes reasoning now. Build a self-hosted/open lane only for high-volume, privacy-sensitive **extraction** + deterministic form-fill, behind the existing provider seam. Add a fully self-hosted **Sovereign** premium tier for the small set of customers who legally require it. **Do not self-host at MVP volume** — the "near-0 cost" claim is false below break-even.

---

## 1. The decision in one paragraph

The founder's instinct ("self-host open models, near-0 cost except hosting, more private, personalizable") is **half right and half a trap**. It is right that document **extraction / OCR / field-mapping** is a near-perfect fit for cheap open models, and that privacy is a real, sometimes deal-deciding driver. It is wrong that this is a cost win at our stage: self-hosting trades *variable* per-call API cost for a *fixed* 24/7 GPU + ops cost that only beats the cheapest frontier API past a high volume break-even. And it is dangerous to extend "cheap open model" to the **high-stakes reasoning agents** (bid/no-bid recommendation, requirement interpretation, narrative generation) — those are exactly where frontier quality lowers compliance/legal risk, and where at our volume frontier is *also cheaper* once you price idle GPU and MLOps labor. The right answer is a **tiered design** that the codebase is already structured to support with near-zero architecture change.

---

## 2. Be honest about "near-0 cost"

This claim does not survive contact with the numbers.

- Self-hosting is a **fixed 24/7 cost** (730 hr/mo) regardless of how many filings you run. A frontier API is **pay-per-call** with zero idle burn. These are different cost *shapes*, not just different cost *levels*.
- Govcon/grants filing traffic is **bursty and low-duty-cycle** (deadlines cluster; nights/weekends are dead). A reserved GPU pays for all the idle hours; the API charges only for work done. The API's shape is strictly better for our actual traffic pattern until volume is both high *and* sustained.
- "Near-0 except hosting" also silently omits the **3–5x hidden multiplier** over raw GPU rent: MLOps/eng time (vLLM + quant tuning, model eval, drift monitoring, on-call), redundancy for SLA (a single spot GPU preempted mid-filing is a real failure mode for a *compliance* product), and cold-start/warm-pool waste. Loaded MLOps is easily **$5–15k/mo of eng time** on top of the GPU.
- **Conclusion:** At MVP volume, frontier API is cheaper **all-in** AND better on quality. "Near-0 cost" only becomes real for the extraction lane, only at high sustained volume, and only after you've absorbed the ops function. Price self-hosting as a **privacy/compliance feature**, never as a cost win, until the meters say otherwise.

---

## 3. Split the problem: three lanes, not one

The single most important architectural fact: in this repo these are **three independent seams** (`captureos/providers/`), each configurable separately. The "self-host vs frontier" question has a *different answer per lane*.

| Lane | What it is | Today in code | Recommended backend |
|---|---|---|---|
| **(0) Raw parse** | PDF/DOCX text + page extraction | `LocalDocparse` (pypdf/python-docx, free) / `DocAIDocparse` (Google DocAI) | Keep as-is. **No LLM, ~$0.** Add a local OCR/VLM provider for scanned forms. |
| **(1) Extraction / field-mapping** | Structured field → value, requirement extraction, calendar/obligation derivation (the `flash` / extractive work) | `flash` tier (calendar) + the rule-based mock in `requirements.py` | **Open / self-hosted** *once volume justifies it.* Frontier-flash (Gemini Flash / Haiku-batch) now. |
| **(2) High-stakes reasoning** | bid/no-bid (`recommendation`), requirement interpretation (`requirements`), evidence matching (`matching`), narrative (`narrative`), grant eligibility (`grant`), opportunity research (`opportunity`), company brain (`company_brain`) | all `ModelTier.pro` → Claude Opus 4.8 | **Keep frontier Claude.** Quality + CON-2 citation faithfulness drive customer/legal outcomes; cheaper than self-host at our volume. |
| **(3) Deterministic** | PDF/DOCX/MD render, AcroForm form-fill, citation stitching | `services/export.py` (fpdf2 only — verified **0 LLM references**) | **No model at all. Literally $0.** |

**Tier mapping verified in code** (`grep` of `captureos/agents/*.py`): only `calendar.py` is `ModelTier.flash`; `requirements`, `matching`, `company_brain`, `grant`, `opportunity` (×2), `narrative`, `recommendation` are all `ModelTier.pro`. So the cheap-open-model bet cleanly applies to the *flash/extraction* lane only — the `pro` lane is precisely the high-stakes reasoning the founder should NOT move down-tier.

> **Nuance on `requirements.py`:** it is the one `pro` agent that is a *candidate* to demote to a self-hosted flash extractor — but only the **raw text/field extraction** half. Requirement *interpretation* nuance feeds downstream matching and bid/no-bid, so validate recall/precision against the existing rule-based mock and a Claude baseline before flipping. Default: keep interpretation on Claude, move only the extractive shell.

---

## 4. Cost model & the break-even number

**Token shape modeled** (ESTIMATE, anchored to this repo's schemas): 6,000 input + 1,500 output = **7,500 tok/extraction** (a parsed solicitation chunk + JSON schema → structured fields). Recompute with measured tokens before committing capital.

**API $/extraction (June 2026 list prices):**

| Model | $/extraction | Notes |
|---|---|---|
| Gemini 2.5 Flash | **$0.0056** | cheapest sensible extractor |
| Claude Haiku 4.5 | $0.0135 | $0.0068 with Batch API (−50%) |
| Claude Sonnet 4.6 | $0.0405 | reasoning tier — overkill for extraction |
| Claude Opus 4.8 | $0.0675 | reasoning tier — 12x the cost for ~0 extraction-quality gain |

Frontier *reasoning* models are **5–12x more expensive** on structured extraction for little/no quality gain. Extraction is a near-perfect fit for the cheapest tier.

**GPU $/mo, 24/7 (730h), ESTIMATES:** L4/A10 8B rig ~$575–942; 1×A100 (32B-AWQ) ~$780–1,015 (spot ~$440); 1×H100 (70B) ~$1,450–1,965 (spot ~$750). Spot is 40–60% cheaper but **preemptible — not plannable for a compliance SLA**.

**Single-GPU capacity @ 50% util (so capacity is NOT the binding constraint at our scale):** L4/A10 8B ≈ **438k extractions/mo**; 1×A100 32B ≈ 263k/mo; 1×H100 70B ≈ 315k/mo. A single hobby-scale GPU covers the entire realistic SMB-govcon extraction volume — the only question is whether you're paying for idle.

### Break-even (the headline number)

Versus the **cheapest sensible API** (Gemini 2.5 Flash / Haiku-batch), on-demand GPU at ~50% util:

> **Self-hosting an open extractor breaks even at roughly ~150k extractions/month** (L4/A10 8B ≈ 140k–170k; 1×A100 32B ≈ 129k–157k). On **spot** GPUs this drops to **~55k–80k/mo** (L4/A10 ≈ 54k–66k; 1×A100 ≈ 65k–79k) — best-case, not plannable as an SLA.

For context only (a **category error** — do not actually do this): a self-hosted 8B/32B rig beats **Sonnet 4.6 at ~21k–23k/mo** and **Opus 4.8 at ~13k–14k/mo**, because those reasoning calls are expensive. This is *not* a reason to run bid/no-bid on an 8B model — quality risk dominates the dollar savings on a filing decision.

### Who wins at what scale (extraction lane)

| Volume (extractions/mo) | Winner |
|---|---|
| **< ~50k** | **FRONTIER API.** Gemini Flash ~$0.006/call, no GPU to babysit, no idle burn. |
| **~50k–150k** | **TOSS-UP.** Spot self-hosting starts to win *if* you tolerate preemption and run an autoscaler + warm pool. |
| **> ~150k–200k sustained** | **SELF-HOSTED OPEN MODEL** wins decisively. A single L4/A10 (~$940/mo) serves 400k+ extractions/mo → **< $0.0025/extraction**, and the "near-0 except hosting" goal is finally real. |

> Note the **3–5x hidden-cost multiplier** and ~$5–15k/mo loaded MLOps. Once those are counted, the *all-in* break-even sits **higher** than the raw-GPU crossover — below high scale, the API is cheaper end-to-end. An alternate framing from the survey: frontier-API break-even is ~**100–256M tokens/month** (~2–5M tokens/day) once ops labor is priced in.

---

## 5. Concrete open-model picks

### (a) OCR / layout extraction — the strongest near-free win available
`LocalDocparse` today only does text-layer extraction (`pypdf.extract_text`) and returns **empty/garbage on scanned PDFs, image-based forms, and many gov forms** (SF-1449, SF-33, flattened AcroForms). A local OCR/VLM provider closes exactly that gap.

- **PaddleOCR / PP-StructureV3** — **Apache-2.0**, no revenue cap, strong layout + table analysis, runs on CPU or a cheap GPU, highest pages/min for batch. **Best default traditional engine.**
- **PaddleOCR-VL ~0.9B** (ERNIE-4.5-0.3B + NaViT) — **Apache-2.0**, ~2.5–4GB VRAM, 109 languages, ~94–96 OmniDocBench v1.5/1.6, beats GPT-4o on doc parsing per Baidu. **The standout "small + permissive + SOTA" VLM pick** for scanned/image gov forms; CPU-tolerable.
- **dots.ocr ~2.7B** (MIT), **DeepSeek-OCR ~3B** (MIT) / **DeepSeek-OCR-2** (Apache-2.0, ~91 OmniDocBench) — strong, permissive alternates.
- **Tesseract** (Apache-2.0) — fastest bulk CPU, weakest on complex layout/tables; fine as a cheap fallback.
- **GPU-class VLMs (need ~16–24GB):** Qwen2.5-VL-7B (Apache-2.0); olmOCR-2-7B (finetune of it, purpose-built PDF→markdown incl. tables/equations, ~82 olmOCR-bench).

### (b) Small LLMs for structured field → value mapping
- **Qwen3-4B/8B** — **Apache-2.0**, the recommended structured-output workhorse.
- **Phi-4 ~14B** — **MIT**, fully permissive, strong extraction.
- **Critical technique:** pair *any* small model with **constrained / guided JSON-schema decoding** (vLLM `guided_json` / `response_format` json_schema, Outlines, or Ollama `format=json`) at **temperature 0**. This makes a 4B model reliable for field→value mapping and removes regex post-processing. Keep schemas shallow.

### (c) Serving stack
- **vLLM** in prod (PagedAttention + continuous batching; 2–3x typical, up to 16–29x at >10 concurrent users vs Ollama; supports tensor parallelism, prefix caching, guided decoding; serves both LLMs and VLMs).
- **Ollama** in dev (best DX, one-command, `format=json`).
- **llama.cpp** for CPU/edge (GGUF quant).

### License landmines (load-bearing — confirm the actual `LICENSE` file at adoption)
- **Surya** — code is Apache-2.0 but **model weights are restricted** (modified OpenRail-M; commercial waiver only for orgs under ~$5M revenue, else paid dual license from datalab-to). **Do not adopt for a SaaS without dual-licensing.**
- **Gemma 3** — Google's **custom (non-OSI) license**, commercial-OK after accepting terms but with redistribution restrictions (Gemma 4+ moved to Apache-2.0 — check the exact version).
- **InternVL3** — "MIT" code but the language tower is often a Qwen2.5 base carrying the **Qwen license**; "MIT" is not the whole story.
- **TGI** — **archived / maintenance-only as of ~March 2026.** Do NOT start new projects on it; use vLLM (or SGLang/LMDeploy) instead.

---

## 6. Routing design — via the existing seam, near-zero architecture change

### Seam reality (verified)
`get_llm()` in `captureos/providers/__init__.py` (line 71) is a single `@lru_cache`'d factory returning **one** `LLMProvider` for the whole app (mock/gemini/anthropic). `ModelTier` (flash/pro) is declared per-agent (`Agent.tier`, `agents/base.py:75`) and passed into `provider.generate(tier=...)`, but **both tiers resolve to the same provider instance** — today tier picks a **model**, not a **provider**. `base.py:_invoke_llm` (line 107–109) does `llm = get_llm()` then `generate(prompt, tier=self.tier, ...)` (line 137). `export.py` is fpdf2-only (0 LLM refs). These facts are the entire design surface.

### The change set (tiny)
1. **New LLM provider — `self_hosted`.** Add `LLMProviderName.self_hosted` to `config.py` and a `SelfHostedLLM(LLMProvider)` in `providers/llm.py` that calls an **OpenAI-compatible** `/v1/chat/completions` endpoint (vLLM or Ollama). Config: `SELF_HOSTED_BASE_URL`, `SELF_HOSTED_API_KEY` (optional), `SELF_HOSTED_MODEL_FLASH` (e.g. `qwen2.5-14b-instruct`), `SELF_HOSTED_MODEL_PRO` (optional). It honors the **same `generate()` signature**: map `json_schema → response_format json_schema` (vLLM guided decoding) so the base-class schema-retry still works, and **return real `input_tokens`/`output_tokens` from the `usage` block** so the cost guard (`workflow_token_budget`, `base.py:117–143`) and audit (CON-3, FR-AU-1) keep functioning.

2. **The one structural touch — make `get_llm()` tier-aware.** Change `get_llm()` to accept the tier and dispatch via a tiny env policy map, e.g. `LLM_ROUTING='flash=self_hosted,pro=anthropic'`. `get_llm(tier)` → `ROUTING[tier]` → provider name → cached provider. The only edit in `base.py` is `get_llm(self.tier)`. **Cache key must include tier** (and agent_name if used), and `reset_providers()` must clear the new entries or tests will see stale providers. With the default policy, flash agents → self-hosted, pro agents → Claude Opus. Flipping any task between local and frontier becomes a **pure env change** — "zero architecture change" for ops.
   - **Optional per-agent override (still config-only):** `LLM_ROUTING='requirement_extraction=self_hosted,default_pro=anthropic,default_flash=self_hosted'`; `get_llm(tier, agent_name)` checks agent_name first, then tier. Lets the founder pin `narrative` to frontier while moving a future bulk-extraction agent local, no code change. (Couples ops config to `agent.name` strings — document them.)

3. **New docparse provider — local OCR.** Add `DocparseProviderName.local_ocr` and a `LocalOCRDocparse(DocparseProvider)` in `providers/docparse.py` (PaddleOCR/PP-StructureV3 + optional PaddleOCR-VL) returning the same `ParsedDocument`. `LocalDocparse` stays default for native-text PDFs/DOCX. Selected by `DOCPARSE_PROVIDER=local_ocr`; **no `ingestion/service.py` change** (it already calls `get_docparse().parse()`). Keeps client documents in-VPC — the privacy win.

4. **No model at all where deterministic.** Native-text parse (pypdf), PDF/DOCX/MD render + AcroForm form-fill (fpdf2 / pypdf widget set — values come from already-extracted structured data, a dict→widget mapping), and citation stitching/`validate_citations`. Keep these out of any model.

### Counts (design surface)
- Provider classes to add: **2** (`SelfHostedLLM`, `LocalOCRDocparse`).
- Enum values to add: **2** (`LLMProviderName.self_hosted`, `DocparseProviderName.local_ocr`).
- Structural code touch points: **1** (`get_llm` becomes tier/agent-aware; one-line `_invoke_llm` edit).
- Protocol changes: **0.** Call-site / pipeline changes: **0** (`workflows/pipelines.py`, `ingestion/service.py`, all `services/*.py` untouched).

### Watch-outs
- `SelfHostedLLM` MUST report real token counts or the cost guard silently stops bounding spend and audit cost-attribution breaks. vLLM/Ollama both report `usage` — verify it's populated.
- JSON-schema enforcement differs by backend (Anthropic `output_config`, Gemini `response_schema`, vLLM `guided_json`, Ollama `format=json` is weaker). Small local models will hit the schema-retry more often — budget higher `llm_max_retries` and validate small models honor the schemas before demoting any `pro` agent.
- Add `is_production_like` startup guards for the new providers (e.g. require `SELF_HOSTED_BASE_URL`) so a misconfigured prod deploy fails fast, not mid-workflow.

---

## 7. Privacy / compliance positioning — a three-tier ladder

`.planning/PROJECT.md` lists "self-hosted models" explicitly under **Out (MVP)**. So this is a deliberate **post-MVP / enterprise-tier** item, not a default — which aligns perfectly with selling self-hosting as a **premium tier**.

**When frontier-enterprise SUFFICES (the majority, including most CUI/FCI):** NIST SP 800-171 / CMMC L2 are about **access control, encryption, audit, and flow-down** — *not* "no cloud AI." Satisfiable by a FedRAMP/GovCloud-path deployment of Claude on **AWS Bedrock** or **Google Vertex** with zero-data-retention, no-train commitments, US data-residency, and the existing CON-3 audit trail. "We handle CUI" is **not** by itself a reason to self-host.

**When self-hosting is GENUINELY required (the only cases that justify Sovereign):**
1. **ITAR / EAR export-controlled technical data** — must stay on US-person-controlled infra; a multi-tenant API is a potential export violation regardless of vendor security. Strongest forcing function.
2. **Contract clauses** mandating "no third-party AI / data may not leave our VPC" — common in primes' subcontract flow-downs; no zero-retention promise satisfies them.
3. **Air-gapped / on-prem-only** customers.

(IL5+/classified is out of scope for a SaaS.)

**Pricing ladder** (current `services/billing.py`: audit $99, sprint $299, autopilot $999/mo):
- **Standard** — Anthropic/Gemini API as today.
- **Enterprise** (new middle tier) — Claude on Bedrock/Vertex, zero-retention, US-region, BAA/FedRAMP path. Captures CUI/FCI customers **without paying for GPU**.
- **Sovereign** (new top SKU) — fully self-hosted / in-customer-VPC, priced as an **annual enterprise contract (5-figure+/yr)** sized to cover dedicated GPU + MLOps. Sold on **compliance-unlock** ("lets you bid ITAR-touching / no-third-party-AI work you legally can't run on shared APIs") and privacy — **never on "it's cheaper."**

All three tiers run the same codebase via config (`llm_provider` / `docparse_provider` / `embeddings_provider`) — the seam is the reason this ladder is cheap to ship.

**Personalization:** per-client **LoRA adapters** (hot-swapped per org, trained on a client's winning proposals/voice) are the *real* differentiator a frontier zero-retention API structurally can't match — but they carry a real MLOps function (dataset curation, training/re-training on drift, an org-keyed adapter registry, per-request adapter mounting, GPU capacity, citation-faithfulness evals). **Defer this**; get the same effect first from prompt/template/RAG personalization over the existing pgvector store. Per-client model finetuning is the *weakest* of the founder's three rationales today.

---

## 8. Phased plan

**Phase 0 — Now (MVP, frontier).**
- Keep `pro` reasoning agents on Claude Opus 4.8 (frontier, via Anthropic API).
- For the **extraction/flash lane**, switch to the cheapest frontier extractor: **Gemini 2.5 Flash (~$0.006/extraction)** or **Haiku 4.5 + Batch API (−50%)**. Below ~50k extractions/mo this is cheaper than any 24/7 GPU AND zero ops burden.
- Keep raw parse + export deterministic ($0).
- Instrument: the cost guard already meters tokens per filing (`workflow_token_budget`). Use it to publish a real per-filing cost number.

**Phase 1 — Privacy/OCR win (volume-independent, ship when a customer needs it).**
- Build `LocalOCRDocparse` (PaddleOCR/PP-StructureV3 + PaddleOCR-VL 0.9B) behind the docparse seam. This is the genuine near-free win (closes the scanned-form gap `LocalDocparse` can't read today) and gives a real in-VPC privacy story — independent of LLM cost break-even.

**Phase 2 — Self-host the extraction LLM (trigger-gated).**
- Build `SelfHostedLLM` + the tier-aware `get_llm()` router, shipped behind defaults that **preserve today's behavior** (`LLM_ROUTING` defaulting to current providers).
- **Trigger to flip `flash → self_hosted`:** sustained extraction volume crosses **~150k/mo on-demand** (or ~60–80k/mo if comfortable on spot + autoscaler + warm pool). Before flipping, benchmark the local box against the rule-based mock and Claude-flash outputs on **real** gov/grant forms.

**Phase 3 — Sovereign tier + Enterprise (Bedrock/Vertex) tier.**
- Stand up the in-VPC Sovereign deployment for ITAR / no-third-party-AI / air-gapped customers, priced to cover GPU + MLOps. Add the Bedrock/Vertex Enterprise middle tier for CUI customers. Consider LoRA personalization only after this is stable and demanded.

**Never:** move the `pro` reasoning agents (bid/no-bid, requirement interpretation, narrative) to an 8B/32B self-hosted model purely to save money. Their per-call API cost is small relative to the dollar value of a filing decision; frontier quality materially lowers compliance/quality risk; submission is human-gated (CON-1) but the recommendation still drives expensive human effort. Re-evaluate only past ~100M+ tokens/mo of reasoning traffic.

---

## 9. Caveats (read before spending capital)

- **Token shape (6k in / 1.5k out) and tok/s figures are ESTIMATES** anchored to public vLLM benchmarks and this repo's schemas. Real numbers depend on solicitation size, chunking (`ingestion/chunking.py`), JSON-schema verbosity, and quant/batch settings. **Recompute with measured tokens before committing capital.**
- **GPU prices vary 20%+** across providers/regions and over time; **spot break-evens are best-case, not plannable SLA** (preemption mid-filing is a real failure for a compliance product).
- **Break-even excludes ops** (eng/eval/on-call/redundancy, ~$5–15k/mo loaded) — include it and the all-in break-even rises substantially; below high scale the API is cheaper end-to-end even past the raw-GPU crossover.
- **Open-model quality parity is asserted for STRUCTURED EXTRACTION ONLY**, and from vendor/blog benchmarks (PaddleOCR-VL ~94–96, DeepSeek-OCR-2 ~91, olmOCR-2 ~82) **not run on CaptureOS's own forms**. Validate numerics (dollar amounts, dates, NAICS/CAGE, checkbox states) on a held-out set of **real** solicitations — a single wrong digit in a compliance field is high-cost.
- **License nuances are load-bearing and read from secondary sources** (Surya ~$5M revenue cap; Gemma custom license; InternVL3 MIT-code-but-Qwen-base; TGI archived). **Confirm against the actual `LICENSE` files before commercial deployment.**
- **FedRAMP / zero-retention specifics** for Claude-on-Bedrock/Vertex change over time and were not verified live — confirm exact authorizations (FedRAMP High in GovCloud, DoD IL levels) and contractual terms with the vendors before making compliance claims. **ITAR/export-control is a legal determination — involve counsel.**
- Embeddings (Gemini) and the non-LLM parse layer are **out of scope** of this break-even and have their own (small) cost profiles.

---

## 10. Decision summary

1. **Keep frontier Claude for the `pro` reasoning lane.** Highest quality, lowest compliance risk, and *cheaper* than self-host at our volume.
2. **Use the cheapest frontier API (Gemini Flash / Haiku-batch) for the extraction/`flash` lane now** — below ~50k extractions/mo it beats any 24/7 GPU with zero ops.
3. **Build the self-hosted extraction + local-OCR lane behind the existing seam** (`SelfHostedLLM` + `LocalOCRDocparse` + tier-aware `get_llm()`), shipped inert behind defaults.
4. **Flip `flash → self_hosted` only past ~150k extractions/mo sustained** (or ~60–80k on spot) — that is where "near-0 except hosting" becomes real.
5. **Sell a Sovereign (fully self-hosted, in-VPC) premium tier** for ITAR / no-third-party-AI / air-gapped customers — priced on compliance-unlock and privacy, never on cost. Add a Bedrock/Vertex Enterprise tier for the CUI majority.
6. **Defer per-client model finetuning;** get personalization from prompts/templates/RAG first.

**Headline:** Hybrid + tiered. Frontier now; self-host the extraction lane later, gated on a **~150k extractions/month** break-even (≈60–80k on spot); reasoning stays on Claude; a fully self-hosted premium tier exists only for customers who legally require it.
