# Production-Hardening Follow-ups

> Tracked, **non-blocking** items surfaced by the adversarial/security gates during the WS1/WS2/WS3/WS4 build. All are latent (uncovered live path) or defense-in-depth — none block localhost/sandbox use. Address before real-money / real-traffic production go-live. Blocking issues found during the build were already fixed on `main`.

## Money (WS1 + WS4)
- **[low] checkout-path idempotency parity** — `services/billing.py` `apply_webhook` (checkout path) doesn't wrap its `flush` in the `IntegrityError` guard the subscription path uses. A rare concurrent double-delivery of `checkout.session.completed` → one request 500s and Stripe retries (no double grant — the unique constraint holds). Tighten for parity.
- **[ops] mis-configured price → retains tier** — ✅ **observability added.** A subscription for a Stripe price not in the configured map still yields `tier=None` and keeps the org's existing tier (fail-safe unchanged, fails toward not-granting), but `providers/billing.py::_tier_from_subscription` now emits a `billing.unmapped_subscription_price` warning naming the unmapped price id(s) — the only layer that sees the price id — so a blank/mis-configured `STRIPE_PRICE_*` env is no longer silent. (A Stripe `price_...` id is a public catalog identifier, not a secret.)

## Onboarding (WS3)
- **[low/theoretical] DNS-rebinding residual** — ✅ **closed.** `ingestion/website.py` now fetches through a `_PinnedResolvingBackend` (an `httpcore.AnyIOBackend` swapped onto httpx's pool) that re-resolves the host, refuses unless every address is a public IP, and dials that exact validated IP at socket-connect time — so the address the SSRF check approved is the address the socket connects to (no independent httpx re-resolution). TLS is unaffected: httpcore derives the TLS `server_hostname` from the request origin (hostname), not the connect target, so SNI + cert verification still validate against the hostname for legitimate HTTPS fetches (verified against the httpcore 1.0 source). The per-hop `_is_safe_public_url` verdict is retained as defense-in-depth. Hermetic tests cover both the fail-closed rebind refusal and connect-to-pinned-IP with Host/SNI preservation.
- **[low] production-LLM prompt-injection coverage** — the hard invariant holds (eligibility-critical fields are `user_overrides`-locked; agent output is a strict schema with no tool/exfil channel; untrusted excerpts are fenced). The fence is now locked by a hermetic regression test (`test_build_prompt_fences_untrusted_excerpts`) so the `<untrusted_source_excerpt>` wrapper + ignore-instructions directive can't silently regress. Residual: non-locked inferred fields that drive matching (`naics_guesses`, `funding_categories`, `capability_statement`) remain steerable by crafted "facts" in production Gemini mode (RAG data-poisoning, not escalation/exfil). Add a real-LLM injection eval when WS5 RAG lands.

## From the WS0 agent-fleet inventory (deferred by design)
- ✅ **done** — `ComplianceCalendarAgent` converted to a deterministic service (`services/obligations.py::derive_compliance_obligations`); the LLM agent + `agents/calendar.py` are gone. Same output shape, `obligation_sync` behavior unchanged, no token spend / provider dependency.
- ✅ **done** — `OpportunityResearchAgent` downgraded to **flash** (bulk agency/prior-award research); `FitScoringAgent` in the same module stays **pro** for the bid/no-bid judgment.
- **Vertex provider swap** — deferred with deployment; flip `GEMINI_BACKEND=vertex` (ADC on `captureos-prod`) before production. (`ModelTier.bulk` was added in WS2.)

## Deployment topology (deferred — localhost-first, keep it FREE until deploy)

**Cost guardrail — nothing bills during local testing.** Everything runs on free/local tiers: local Docker Postgres (`pgvector/pgvector:pg16`), Gemini AI Studio free key, Stripe **sandbox**, local/mock providers. The GCP project `captureos-prod` is provisioned but **incurs $0** — enabled APIs + ADC are free; no paid resource is running. **Do NOT provision paid GCP resources (AlloyDB instance, Cloud Run, etc.) until an actual deploy.**

**Local → production is an env swap, not a rewrite** (the provider-seam / local-first, cloud-ready design). The Postgres Docker container is a dev convenience — it is **not** shipped; production uses a **managed Postgres**.

| Piece | Local (free) | Production |
|---|---|---|
| Database | Docker `pgvector/pgvector:pg16` | **managed Postgres** — swap `DATABASE_URL` (cost note below) |
| API + worker | `make api` / worker | containerize → **Cloud Run** (the prod container is the *app*, not the DB) |
| Frontend | `make web` | Cloud Run or Vercel |
| Gemini | AI Studio free key | Vertex AI (`GEMINI_BACKEND=vertex`, ADC) |
| Storage / queue / cron | local providers | GCS / Pub/Sub / Cloud Scheduler → Run Job |
| Secrets | `.env` | Secret Manager |

**Managed-Postgres cost tradeoff (decide at deploy — all pgvector-capable):**
- **Cloud SQL for Postgres** — cheapest simple managed Postgres on GCP. Best lean start.
- **Neon** — serverless Postgres, scales to zero; cheapest at low/spiky traffic (Neon MCP already connected).
- **AlloyDB** — vector-optimized (pgvector + ScaNN), premium price. Move here when RAG/vector scale demands it.
- **Recommendation: launch lean on Cloud SQL or Neon, upgrade to AlloyDB later** — just a `DATABASE_URL` swap + `alembic upgrade head` + `corpus.sync`/`embed`.

**Deploy checklist (later):** provision managed Postgres → point `DATABASE_URL` → migrate → containerize API/worker → Cloud Run → Cloud Scheduler for the corpus cron → Vertex + Secret Manager + GCS/Pub/Sub → Stripe live + business entity for Issuing → Twilio prod number.

## Not yet built
- **WS5 — Custom RAG** (hybrid retrieval, structure-aware chunking, temporal, re-rank, eval harness). Deferred/research-gated; opens with the embedding-analysis spike. See `docs/prd/ws5-custom-rag.md`.
