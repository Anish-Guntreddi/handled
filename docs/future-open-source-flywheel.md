# Future: Open-Source Model Flywheel (DEFERRED — post-revenue)

**Status: NOT for the MVP / revenue window.** Captured so the long-term vision isn't lost.
The MVP ships on frontier APIs (Claude reasoning + Gemini embeddings/flash extraction) behind the
existing provider seam. This document is the post-revenue roadmap.

## The vision

A **distillation flywheel** that moves CaptureOS toward a private, personalized model stack over
time — *funded by revenue, not built before it*:

1. **Operate on frontier** (Claude reasoning, frontier-flash extraction). Ship, sell, run filings.
2. **Capture the data for free.** Every agent call already records `(input, output, model)` in
   `AgentRun`; approval gates record the human accept/reject verdict; override mechanisms record
   human corrections. That triple — *model output + human verdict + human correction* — is a
   gold-labeled, govcon-specific training set that accrues as a byproduct of the compliance audit
   trail. **No new collection system needed — just don't discard it.**
3. **Fine-tune open models** (LoRA) on the *human-approved/corrected* data to take over the
   **bounded** tasks (OCR, field extraction, field→value mapping, narrow classification).
4. **Route the proven lanes to the local models** behind the seam (eval-gated), cutting cost and
   increasing privacy. Keep high-stakes reasoning on frontier.
5. **Personalize** per high-value client with per-tenant LoRA adapters trained on their filings/voice.
6. **Offer a "Sovereign" fully self-hosted/air-gapped tier** for ITAR / no-third-party-AI / CUI
   clients — priced on the compliance it unlocks, not on cost.

## Why it fits CaptureOS specifically

The compliance **audit trail is the training corpus**, and the data moat compounds: every customer
filing produces more labeled examples on real govcon documents — a dataset no competitor or frontier
lab has. That is the durable long-term advantage.

## Honest caveats (decide before investing)

- **Provider terms.** Frontier providers restrict using outputs to train *competing* models.
  Fine-tuning a small model to extract form fields for our product is almost certainly fine;
  wholesale-distilling Claude's reasoning to *replace* it is the gray zone. **Safer path: train on
  our own human-approved/corrected data (unambiguously ours, and the higher-quality signal).**
  Review the actual terms / get legal input before building the pipeline.
- **Distillation privatizes the *bounded* tasks, not the *judgment*.** A 4–8B fine-tune can match
  frontier on extraction/classification; it will **not** match Opus on bid/no-bid judgment or
  nuanced compliance interpretation. So high-stakes reasoning likely stays frontier indefinitely
  (except the Sovereign tier). Set expectations accordingly.
- **Cost is not the trigger; privacy and scale are.** Against cheap Gemini Flash, the self-host
  break-even for extraction is ~tens-of-thousands to ~150K extractions/month (see
  `selfhosted-models-analysis.md` / `codex-selfhosted-models.md`). Below that, frontier is cheaper
  *and* better. So self-host on a **customer privacy requirement** or a **proven volume trigger** —
  not for "near-0 cost," which is a misframe until large scale.

## Triggers to start (none are now)

- A customer contractually requires no-third-party-AI / air-gapped → build local-OCR + Sovereign tier.
- Sustained extraction volume crosses the break-even → distill the extraction lane.
- A high-value enterprise client wants personalized output → per-tenant LoRA.

## What the MVP does now to keep this option open (near-zero cost)

- Keep the provider seam tier-aware (extraction vs reasoning independently pluggable) — done.
- Keep recording `AgentRun` input/output + approvals/corrections cleanly — already shipped.
- That's it. No fine-tuning infra, no GPUs, no eval harness until a trigger fires.

Related: `model-data-strategy-decisions.md`, `selfhosted-models-analysis.md`, `mvp-architecture.md`.
