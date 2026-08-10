# CLI tools for service orchestration

This repo talks to a lot of external services (see `.env.example` for the full provider list).
Installing these CLIs locally lets Claude Code (and you) configure, inspect, and deploy those
services directly from the terminal instead of hopping into each web console. Grouped by how soon
you'll actually need them.

> **Current deploy target (confirmed):** Netlify (frontend) + Render (backend, free tier) + Neon
> (Postgres+pgvector, free tier) — see the deployment plan. GCP/Cloud Run remains the documented
> long-term target in `.planning/PROJECT.md` but is explicitly deferred: it has a real architectural
> mismatch with this app's always-on in-process worker (Cloud Run only allocates CPU during active
> requests) that made it the wrong choice for getting to a testable MVP quickly and cheaply. The
> `gcloud`/Terraform section below still applies once real usage justifies that cost/complexity.

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
| **gitleaks** | Secret-scanning CLI used by the repo's pre-commit hook (`.githooks/pre-commit`) **and** the CI `secrets-scan` job (`.github/workflows/ci.yml`) — catches an accidentally-staged key before it reaches a commit. Config: `.gitleaks.toml` (allowlists one known-fake test fixture secret) | `brew install gitleaks` | `winget install -e --id Gitleaks.Gitleaks` |
| **netlify-cli** (`netlify`) | Link the local repo to the Netlify site, pull/push per-context env vars, trigger manual deploys, `netlify dev` for local SSR parity checks | `brew install netlify-cli && netlify login` | `npm install -g netlify-cli` (needs Node ≥22) then `netlify login` |
| **Render CLI** (`render`) | Interactive service management, tailing logs, `render psql` against the managed DB, non-interactive/scriptable mode for CI. Most day-to-day setup (creating the two Web Services, wiring env vars) happens in Render's dashboard the first time — the CLI is for ongoing operations after that | `brew tap render-oss/render && brew install render && render login` | No confirmed winget package — download the Windows binary from the [render-oss/cli releases page](https://github.com/render-oss/cli/releases) |
| **neonctl** (Neon CLI) | Scripted access to the Postgres+pgvector database (branches, connection strings, migrations) from a plain shell. Note: **the Neon MCP server can also be connected directly in a Claude Code session** (`claude mcp add --transport http Neon https://mcp.neon.tech/mcp`, then complete the OAuth login under **your own** Neon account) — verify with a `list_projects`-equivalent call that it resolves to your account, not a stray one, before provisioning anything for real | `brew install neonctl && neonctl auth` | `npm install -g neonctl` then `neonctl auth` |

## Deferred: production GCP migration (target stack, not current)

Per `.planning/PROJECT.md`, GCP remains the intended long-term production architecture — Cloud Run
(API/worker + Cloud Run Jobs for the corpus cron), Cloud SQL/AlloyDB, Cloud Storage, Pub/Sub,
BigQuery, Document AI, and Secret Manager. The `captureos-prod` GCP project exists but runs $0 (see
`docs/prd/production-hardening-followups.md`) — revisit this migration once real usage justifies
Cloud Run's always-on-worker cost (~$65/mo just for that) and Cloud SQL's always-on floor (~$50+/mo)
over the current Render+Neon free-tier setup. Today's Dockerfiles make it a redeploy, not a rewrite,
when that time comes.

| Tool | Why | Install (macOS) | Install (Windows) |
|---|---|---|---|
| **gcloud** (Google Cloud SDK) | Cloud Run deploy, Cloud SQL, Secret Manager, Pub/Sub, BigQuery, Document AI, IAM/ADC | `brew install --cask google-cloud-sdk && gcloud init` | `winget install -e --id Google.CloudSDK` then `gcloud init` |
| **terraform** | Infra-as-code for the Cloud Run Job + Cloud Scheduler pairing that runs `corpus.sync`/`corpus.embed` on a cadence (`docs/prd/ws2-corpus-autoupdate.md`) | `brew install terraform` | `winget install -e --id Hashicorp.Terraform` |

## Optional / situational

| Tool | Why | Install (macOS) | Install (Windows) |
|---|---|---|---|
| **firebase-tools** | Only if `AUTH_PROVIDER` flips from `local` to `firebase` (`FIREBASE_PROJECT_ID` in config) | `brew install node && npm install -g firebase-tools && firebase login` | `npm install -g firebase-tools` (needs Node.js above) then `firebase login` |
| **twilio-cli** | Only needed once SMS decline alerts (`NOTIFICATIONS_PROVIDER=twilio`) move off mock | `brew tap twilio/brew && brew install twilio && twilio login` | Twilio recommends Scoop over winget: `scoop bucket add twilio-cli https://github.com/twilio/scoop-twilio-cli.git && scoop install twilio-cli` (or `npm install -g twilio-cli`, no auto-update) then `twilio login` |

## Not CLI-driven

**Firecrawl**, **SAM.gov**, **Grants.gov**, and **USAspending** are plain API-key services with no
meaningful CLI — configure them by dropping the key into `.env` (see `.env.example`). **Anthropic**
and Gemini's **AI Studio** key likewise have no separate provisioning CLI beyond the console; Gemini
*Vertex* access goes through `gcloud` above.
