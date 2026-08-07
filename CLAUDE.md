# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

CaptureOS — an AI platform that handles government compliance paperwork for small businesses (federal contracts, grants, tax credits). Monorepo: `apps/api` (FastAPI backend) + `apps/web` (Next.js frontend). Product guarantees that are **enforced in code, not just prompts**: nothing is ever auto-submitted (human approves), every AI claim is cited to a retrieved source, everything is audited, and multi-tenant org isolation is strict.

## Commands

All common entrypoints are `make` targets from the repo root (`make help` lists them):

```bash
make db-up          # start Postgres+pgvector in Docker (port 5433 — 5432 is taken on this machine)
make migrate        # alembic upgrade head
make api            # run FastAPI locally with reload → http://localhost:8000 (/docs)
make web            # run Next.js locally → http://localhost:3000
make seed           # demo login: demo@captureos.dev / demo-password-123

make test           # backend: pytest -q
make lint           # backend: ruff check + mypy
make fmt            # backend: ruff format + ruff check --fix
make check          # lint + test
make web-check      # frontend: eslint + tsc --noEmit

make migration m="msg"   # autogenerate an alembic migration
make corpus-sync         # one corpus ingest + embed pass (needed before real cited answers)
```

Single test: `cd apps/api && uv run pytest tests/test_billing.py -q` (or `-k name`). Backend tooling is `uv` (Python 3.12+); frontend is `pnpm` (Node 20+).

The API drains the workflow queue **in-process** by default (`WORKFLOW_INLINE_WORKER=true`), so `make api` alone runs every workflow — no separate worker needed locally. If workflows stay "queued", that flag is the first thing to check.

## Architecture

**The provider seam is the core design.** Every external dependency (LLM, embeddings, storage, queue, docparse, audit sink, secrets, billing, notifications, issuing) sits behind an interface in `apps/api/captureos/providers/`, selected by env var in `captureos/config.py`, each with a working local/mock implementation. The whole system runs end-to-end with zero cloud credentials; flipping an env var swaps in the real provider with no code change. When adding an external dependency, follow this pattern — never call a cloud SDK directly from feature code.

- `captureos/config.py` — single typed `Settings` (pydantic-settings) loading the **repo-root `.env`** regardless of CWD. In `local`/`ci` envs missing keys degrade gracefully; in `staging`/`production` a `model_validator` **fails boot** on any half-configured provider (e.g. `BILLING_PROVIDER=mock`, default JWT secret, provider selected without its key).
- `captureos/agents/` — each AI task is an `Agent` subclass (`base.py`) with a mock path and an LLM path, schema-validated output with retries, and an audit trail. Agents pick a model *tier* (`pro` = reasoning, `flash` = extraction, `bulk` = cheap long-context triage); tier→provider/model routing is env-driven (`LLM_PROVIDER`, per-tier overrides `LLM_PROVIDER_PRO/FLASH/BULK`), so agent code never names a model.
- `captureos/workflows/` — durable DB-backed workflow/job engine (`engine.py`, `queue.py`, `runner.py`); multi-step pipelines in `pipelines.py`. Steps are retried (`worker_max_attempts`) and budget-guarded (`WORKFLOW_TOKEN_BUDGET`).
- `captureos/corpus/` — the RAG grounding layer: version-aware government corpus (eCFR/FAR, Federal Register, IRS/SBA pubs) chunked and embedded into pgvector. `sync.py` / `embed.py` / `discover.py` / `schedule.py` are cron-style modules run via make targets, never in a user-request path. `EMBEDDING_DIM=768` is pinned to the pgvector column — changing it post-ingest requires a migration plus re-embedding everything.
- `captureos/api/` — FastAPI routers; org-scoped routes take `OrgViewer`/`OrgOwner` deps from `core/deps.py` which enforce membership. Webhooks (`billing.py`, `spend_webhooks.py`) are unauthenticated routes trusted **only** via signature verification and fail closed (unverifiable → rejected).
- `captureos/services/` — business logic between routers and models/providers.
- Tests (`apps/api/tests/`) run against mock providers with no credentials; `pytest.ini` sets `asyncio_mode = "auto"`.

**Frontend** (`apps/web`): Next.js 16 App Router + TypeScript + Tailwind v4 + TanStack Query. All API access goes through `src/lib/api.ts` against `NEXT_PUBLIC_API_BASE_URL`; auth state in `src/lib/auth.tsx` + `tokenStore.ts`. Only `NEXT_PUBLIC_*` vars reach the browser. Note `apps/web/AGENTS.md`: this Next.js version has breaking changes — read the relevant guide in `node_modules/next/dist/docs/` before writing Next-specific code.

## Conventions

- Backend style is enforced by ruff (line length 100, py312, `S` security rules on) and mypy with the pydantic plugin — run `make fmt` before committing.
- Migrations: alembic autogenerate from models (`make migration m="..."`), then review; `migrations/versions` is excluded from lint.
- Secrets are server-side only; never log them, never put them in frontend code.
- `uv` has a supply-chain cooldown (`exclude-newer` in `pyproject.toml`) — new package versions <~7 days old won't resolve.
- Optional dependency extras: `uv sync --extra billing` for the Stripe SDK, `--extra gcp` for GCP SDKs. `BILLING_PROVIDER=stripe` without the extra installed raises at first billing call.

## Configuration

`.env` at the repo root is the single config contract; `.env.example` documents every knob. Key local facts: DB runs on port **5433**; mock providers need no keys; real mode is a two-provider flip (`LLM_PROVIDER` + key, `EMBEDDINGS_PROVIDER=gemini` + `GEMINI_API_KEY`), then `make corpus-sync` to embed the corpus (check `GET /corpus/status`). Stripe billing needs `STRIPE_WEBHOOK_SECRET` (from `stripe listen` locally) or checkout completes but entitlements never fulfill — webhooks without a verifiable signature are rejected by design.

See `docs/cli-tools.md` for the CLIs (Stripe, gcloud, Terraform, etc.) used to configure and deploy these services directly from the terminal.

## Version control security

`.env` is gitignored at the root and per-app (`apps/web/.gitignore`) and has never been committed. A pre-commit hook at `.githooks/pre-commit` blocks staging any secret-shaped file (`.env*`, `*.pem`, `*.key`, `service-account*.json`) and scans the staged diff for credential patterns (via `gitleaks` if installed, grep fallback otherwise) — enable it once per clone with `git config core.hooksPath .githooks`.
