# Running CaptureOS locally

CaptureOS is **local-first**: with the bundled `.env` it runs end-to-end on **mock providers** with
**no cloud credentials** (mock LLM + embeddings, local blob storage, DB-backed queue, mock billing).
Drop real keys into `.env` to switch any provider to its cloud implementation — no code change.

## What actually runs

Three processes + a database:

| Process | What it is | Local URL |
|---|---|---|
| **Postgres + pgvector** | data + vector store (Docker) | `localhost:5433` |
| **API** (`uvicorn captureos.main:app`) | FastAPI app **and** the workflow worker (inline by default) | `http://localhost:8000` (docs at `/docs`) |
| **Web** (`next dev`) | Next.js UI | `http://localhost:3000` |

> The API drains the durable workflow queue **in-process** (`WORKFLOW_INLINE_WORKER=true`, the
> default), so you do **not** need a separate worker locally — `make api` alone runs every workflow.
> Set it to `false` and run `make worker` only if you want the worker as its own process.

## Prerequisites

- **Docker** (for Postgres+pgvector) — already running as container `captureos-db` on port 5433.
- **uv** (Python 3.13 toolchain) — backend deps.
- **Node 20+ / pnpm** — frontend deps.

## Quickstart (recommended: DB in Docker, API + web local)

This gives hot-reload and is the fastest way to develop/test.

```bash
# 0) one-time: create .env (already present) + install deps
make setup                # = cp .env.example .env (if missing) + uv sync + pnpm install

# 1) start Postgres + pgvector
make db-up

# 2) apply the schema
make migrate

# 3) (optional) seed a demo login
make seed                 # creates demo@captureos.dev / demo-password-123 (org "Demo Co")

# 4) run the API  (terminal A)  ->  http://localhost:8000  (docs: /docs)
make api

# 5) run the web  (terminal B)  ->  http://localhost:3000
make web
```

Then open **http://localhost:3000** and log in (or register a new account).

## Alternative: full Docker stack

```bash
make up           # db + api + worker in Docker (api auto-migrates on start)
make web          # run the web UI locally with pnpm (see note)
```

> **Note:** the `web` container has no Dockerfile yet, so `make up-full` (web-in-Docker) will not
> build. Run the **web locally with `pnpm dev` / `make web`** and point it at the Dockerized API
> (the default `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` already does this).

## Demo account

```
email:    demo@captureos.dev
password: demo-password-123
```

(or click **Register** to create your own org — you become its owner.)

## A full test walkthrough (the whole product)

1. **Log in** → you land on the org workspace (**Company Brain**).
2. **Build the company profile** — enter a name + a short description (e.g. *"We provide technical
   proposal writing and past-performance reference compilation; we are registered in SAM.gov."*).
   Watch the workflow run and the profile fill in with sourced evidence.
3. **(optional) Ingest a document** — paste solicitation text or upload a PDF/DOCX.
4. **Scan opportunities** — run a **contract** scan and a **grant** scan; each opportunity gets a
   fit score + bid/no-bid (or apply/no-apply) rationale.
5. **Start a filing** from an opportunity → the filing page opens with a 4-step bar:
   1. **Extract requirements** — structured, source-located requirement list.
   2. **Match evidence** — builds the live **compliance matrix** (matched / partial / missing).
      Resolve a gap inline (type a value) → it flips to *user-provided*.
   3. **Recommend** — an AI pursue/no-pursue with for / against / key-gaps. **Approve** it.
   4. **Build package** — *premium*: requires a paid plan (see Billing). Builds the versioned,
      fully-cited package (compliance matrix, narrative, checklists, citation appendix).
6. **Approve the package**, then **export MD / PDF / DOCX** (downloads a real file; nothing is ever
   auto-submitted).
7. **Billing** (top-right) — Free plan blocks the package step with a 402. Click **Upgrade →
   Sprint** to unlock it (mock billing fulfills instantly), then go back and build/export.
8. **Audit** (top-right) — see every workflow run, time saved, est. cost-per-filing, and the audit
   event feed; export the audit trail as CSV/JSON.

You can also explore the API directly at **http://localhost:8000/docs**.

## Useful commands

```bash
make help          # list all targets
make test          # backend test suite (pytest)
make check         # lint + types + tests
make web-check     # frontend lint + typecheck
make logs          # tail Docker logs
make down          # stop the Docker stack
make nuke          # stop + delete volumes (DESTRUCTIVE — wipes the DB)
```

## Production / real mode — the two-key flip

The intended production setup is **Claude for the agents + Gemini for embeddings**. Both SDKs
(`anthropic`, `google-genai`) are **base dependencies**, so going live needs **no code, no extra
install, and no DB migration** — just four `.env` values (two providers + two keys):

```bash
LLM_PROVIDER=anthropic          # Claude runs the agents
ANTHROPIC_API_KEY=sk-ant-...

EMBEDDINGS_PROVIDER=gemini       # Gemini runs the RAG embeddings
GEMINI_API_KEY=...               # same key powers Gemini embeddings

EMBEDDING_DIM=768                # already set; matches the pgvector schema — do not change post-ingest
```

Then restart the API. Notes:
- **Embeddings and the LLM are independent.** Gemini embeddings decide which document chunks are
  retrieved; Claude only ever sees the retrieved *text*. Mixing the two is a standard, supported
  pairing — there is no compatibility constraint between them.
- **Cost.** Embeddings are a rounding error (~$0.02–0.15 /1M tokens, embedded once at ingest); the
  spend is the LLM, controlled per-agent by each agent's `tier` (`pro`→Opus, `flash`→Haiku).
- **Dimension is sticky.** `EMBEDDING_DIM=768` matches `text-embedding-004` and the schema. Changing
  it after ingesting real documents requires a migration **and** re-embedding every chunk — so pick
  the model/dimension before loading production data.
- **Fail-fast.** In a `staging`/`production` env the app refuses to boot if a selected provider is
  missing its key, so a half-configured flip surfaces at startup, not mid-request.

## Other providers

Edit `.env` and restart the API. Examples:

- **Gemini for the LLM too** (instead of Claude): `LLM_PROVIDER=gemini` (uses the same `GEMINI_API_KEY`).
- **Stripe billing:** `BILLING_PROVIDER=stripe`, set `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
  and the `STRIPE_PRICE_*` IDs. (Only then is the `POST /api/v1/billing/webhook` route mounted, and
  it is signature-verified. In production the app refuses to boot with `BILLING_PROVIDER=mock`.)
- **GCS / Pub/Sub / Document AI / BigQuery / Firebase / Secret Manager:** flip the matching
  `*_PROVIDER` / `*_BACKEND` var and provide credentials (`uv sync --extra gcp` for the GCP SDKs).

## Troubleshooting

- **Port 5433 already in use / DB not found:** the DB runs on **5433** (5432 is taken on this
  machine). `DATABASE_URL` in `.env` already points at 5433.
- **API up but workflows stay "queued":** ensure `WORKFLOW_INLINE_WORKER=true` (default) or run
  `make worker`.
- **Web can't reach the API:** confirm `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` and that
  `CORS_ALLOW_ORIGINS` includes `http://localhost:3000` (both already set).
