# CaptureOS

**We handle the paperwork. You keep the money.**

CaptureOS is an AI platform that handles government **compliance** for small businesses — so owners get their time back to build their business, and find the **money they're owed** along the way.

The US government gives hundreds of billions a year to small businesses (federal contracts, grants, SBA loans, SBIR/STTR, R&D & hiring tax credits, set-aside advantages) — but it's scattered across a dozen portals, buried in the FAR/CFR, and gated by paperwork most owners can't afford a consultant to navigate. CaptureOS turns that maze into a fast, friendly, **cited, human-approved** workflow.

> **Wedge vs. moat:** "find the money" is the acquisition hook; **automating the recurring compliance paperwork is the moat** — it's painful, perpetual, sticky, and defensible (a grounded regulatory corpus + structured, auditable workflows). Every recommendation is cited to its source, and **nothing is ever auto-submitted** — a human always approves.

## What it does

| Surface | What it does |
| --- | --- |
| **Onboarding wizard** | A few quick questions → builds the company profile and runs the first scan |
| **Find** | A unified, ranked, **cited** feed of the money & work you qualify for — with a "≈ $X you may qualify for" headline and *why* you qualify |
| **Copilot** | Grounded, cited Q&A over your profile + the government corpus — never fabricates a citation |
| **Pursue** | Each filing's pipeline: requirements → compliance matrix → recommendation (approve-gated) → auto-filled forms → export |
| **Stay eligible** | Renewals & deadlines (SAM registration, cert recerts, reports) with reminders |

## Architecture

**Local-first, cloud-ready.** Every external dependency sits behind a provider interface with a working mock, so the whole system runs with **no cloud credentials** — then swaps to real providers by changing env, no rewrite.

- **Backend** — FastAPI + async SQLAlchemy + Pydantic v2; Postgres + **pgvector** for the RAG corpus; a durable workflow/job engine; an `Agent` base with mock + LLM paths, schema-validated retries, and an audit trail.
- **Frontend** — Next.js (App Router) + TypeScript + Tailwind + TanStack Query.
- **Provider seam** — `get_llm(tier)` / `get_embeddings()` are swappable by env with **zero agent-code change**. Tier-aware routing (a strong model for judgment, a cheap one for bulk) keeps cost low. Defaults: Anthropic Claude (reasoning) + Gemini embeddings; deterministic mocks with no key.
- **Grounding** — a version-aware government corpus (eCFR/FAR, Federal Register, IRS/SBA pubs) embedded into pgvector; agents cite retrieved snippets, and the citation invariant is **enforced in code**, not just the prompt.

```
apps/api/   FastAPI backend — agents, workflows, corpus/RAG, endpoints, tests
apps/web/   Next.js frontend — the CaptureOS app
docs/       CLI tooling and deployment setup guides
```

## Run it locally (no API key required)

CaptureOS runs end-to-end on **deterministic mock** with no keys — perfect for a first test.

```bash
make db-up && make migrate     # Postgres + pgvector, schema to head
make api                       # terminal A → http://localhost:8000  (docs at /docs)
make web                       # terminal B → http://localhost:3000
```

Then register a fresh account → walk the wizard → watch the money appear in **Find** → ask the **Copilot** → start a filing in **Pursue** → check **Stay eligible**.

## Turn on real AI (optional)

Add keys to `.env` (see `.env.example`) and embed the corpus:

```bash
LLM_PROVIDER=anthropic       ANTHROPIC_API_KEY=sk-ant-...
EMBEDDINGS_PROVIDER=gemini   GEMINI_API_KEY=...
```
```bash
cd apps/api && uv run python -m captureos.corpus.embed   # embeds the collected corpus
```
Now the Copilot and grounding cite real regulation text. Check `GET /corpus/status` for readiness.

## Guarantees (non-negotiable)

- **Never auto-submit** — CaptureOS prepares packages; a human files them.
- **Every claim cited** — answers and recommendations are grounded in retrieved sources.
- **Everything audited** — a complete, exportable audit trail.
- **Secrets server-side only** · **strict org isolation** (multi-tenant data never crosses orgs; the shared corpus carries no tenant data).

## Status

MVP — all surfaces built, wired to real endpoints, and **green** (API test suite passing, web build clean). Runs on mock today; add keys for live reasoning and cited regulation text.

## License

[MIT](LICENSE)

---
*CaptureOS prepares every filing. A human decides if and when it's submitted.*
