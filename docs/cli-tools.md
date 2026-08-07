# CLI tools for service orchestration

This repo talks to a lot of external services (see `.env.example` for the full provider list).
Installing these CLIs locally lets Claude Code (and you) configure, inspect, and deploy those
services directly from the terminal instead of hopping into each web console. Grouped by how soon
you'll actually need them.

> Correction on the ask: **Netlify isn't part of this stack** — nothing in the codebase or docs
> references it. The documented frontend deploy targets are **Cloud Run** or **Vercel**
> (`docs/prd/production-hardening-followups.md`), so Vercel's CLI is listed below instead.

Two install columns are given: **macOS** (Homebrew) and **Windows** (`winget`, built into Windows
10 21H2+/11 — or `npm` for the pure-Node CLIs, which installs identically on both). If you're on
Windows, note the repo's `.githooks/pre-commit` hook is a bash script — it runs fine from **Git
Bash** (bundled with Git for Windows) but not from plain `cmd`/PowerShell.

## Already required for local dev

| Tool | Why | Install (macOS) | Install (Windows) |
|---|---|---|---|
| **Docker Desktop / Compose** | Runs Postgres+pgvector (`make db-up`) and the full stack (`make up-full`) | `brew install --cask docker` | `winget install -e --id Docker.DockerDesktop` |
| **uv** | Backend Python env, deps, lint, test, migrations (`apps/api`) | `brew install uv` | `winget install -e --id astral-sh.uv` |
| **pnpm** | Frontend deps/build (`apps/web`) | `corepack enable && corepack prepare pnpm@10.22.0 --activate` | `corepack enable; corepack prepare pnpm@10.22.0 --activate` (PowerShell, needs Node.js: `winget install -e --id OpenJS.NodeJS.LTS`) |
| **gh** (GitHub CLI) | PRs, issues, Actions runs, repo secrets | `brew install gh && gh auth login` | `winget install -e --id GitHub.cli` then `gh auth login` |

## Needed now for service configuration

| Tool | Why | Install (macOS) | Install (Windows) |
|---|---|---|---|
| **Stripe CLI** (`stripe`) | `stripe listen --forward-to localhost:8000/api/v1/billing/webhook` to get a local `STRIPE_WEBHOOK_SECRET` (see `docs/prd/ws4-billing.md`); `stripe trigger <event>` to test handlers; pairs with `apps/api/captureos/scripts/setup_stripe.py` which creates the `STRIPE_PRICE_*` products | `brew install stripe/stripe-cli/stripe && stripe login` | `winget install -e --id Stripe.StripeCli` then `stripe login` |
| **psql** | Direct Postgres queries against the pgvector DB (port **5433** locally) without going through `docker exec` | `brew install libpq && brew link --force libpq` | `winget install -e --id PostgreSQL.PostgreSQL.17` (installs the full client tools incl. `psql`; add `C:\Program Files\PostgreSQL\17\bin` to `PATH`) |
| **gitleaks** | Secret-scanning CLI used by the repo's pre-commit hook (`.githooks/pre-commit`) — catches an accidentally-staged key before it reaches a commit | `brew install gitleaks` | `winget install -e --id Gitleaks.Gitleaks` |

## Needed for production deploy (target stack is GCP)

Per `.planning/PROJECT.md` and `docs/prd/production-hardening-followups.md`, the target production
architecture is GCP: Cloud Run (API/worker + Cloud Run Jobs for the corpus cron), Cloud SQL/AlloyDB
or Neon for Postgres, Cloud Storage, Pub/Sub, BigQuery, Document AI, and Secret Manager. None of
this is provisioned yet — the `captureos-prod` GCP project exists but runs $0 (see the same doc) —
so these only matter once you start the real deploy.

| Tool | Why | Install (macOS) | Install (Windows) |
|---|---|---|---|
| **gcloud** (Google Cloud SDK) | Cloud Run deploy, Cloud SQL, Secret Manager, Pub/Sub, BigQuery, Document AI, IAM/ADC | `brew install --cask google-cloud-sdk && gcloud init` | `winget install -e --id Google.CloudSDK` then `gcloud init` |
| **terraform** | Infra-as-code for the Cloud Run Job + Cloud Scheduler pairing that runs `corpus.sync`/`corpus.embed` on a cadence (`docs/prd/ws2-corpus-autoupdate.md`) | `brew install terraform` | `winget install -e --id Hashicorp.Terraform` |
| **firebase-tools** | Only if `AUTH_PROVIDER` flips from `local` to `firebase` (`FIREBASE_PROJECT_ID` in config) | `brew install node && npm install -g firebase-tools && firebase login` | `npm install -g firebase-tools` (needs Node.js above) then `firebase login` |

## Optional / situational

| Tool | Why | Install (macOS) | Install (Windows) |
|---|---|---|---|
| **neonctl** (Neon CLI) | Alternative to Cloud SQL for Postgres — cheaper at low/spiky traffic, scales to zero. Note: **the Neon MCP server is already connected in this Claude Code session** (see the `mcp__Neon__*` tools), so most Neon operations (branches, connection strings, migrations) can go through Claude directly without installing the CLI — install it only if you want to script Neon from a plain shell. | `brew install neonctl && neonctl auth` | `npm install -g neonctl` then `neonctl auth` |
| **vercel** (Vercel CLI) | Alternate frontend deploy target to Cloud Run (`docs/prd/production-hardening-followups.md`) | `brew install vercel-cli && vercel login` | `npm install -g vercel` then `vercel login` |
| **twilio-cli** | Only needed once SMS decline alerts (`NOTIFICATIONS_PROVIDER=twilio`) move off mock | `brew tap twilio/brew && brew install twilio && twilio login` | Twilio recommends Scoop over winget: `scoop bucket add twilio-cli https://github.com/twilio/scoop-twilio-cli.git && scoop install twilio-cli` (or `npm install -g twilio-cli`, no auto-update) then `twilio login` |

## Not CLI-driven

**Firecrawl**, **SAM.gov**, **Grants.gov**, and **USAspending** are plain API-key services with no
meaningful CLI — configure them by dropping the key into `.env` (see `.env.example`). **Anthropic**
and Gemini's **AI Studio** key likewise have no separate provisioning CLI beyond the console; Gemini
*Vertex* access goes through `gcloud` above.
