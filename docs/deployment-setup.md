# Deployment setup — Render + Netlify + Neon (manual, one-time)

Everything code/CI-side is already done (see the `dev` branch and `.github/workflows/ci.yml`).
The three steps below need your own account sign-in / OAuth, which can't be done from here —
follow them in order, since Render's URL feeds into Netlify's env vars and CORS.

## 0. Neon (database) — do this first

The Neon MCP connection was reset to a stray third-party account and needs reconnecting under
**your own** Neon account before anything else touches it:

1. `claude mcp add --transport http Neon https://mcp.neon.tech/mcp`
2. Next Claude Code session that uses a Neon tool will prompt an OAuth login in your browser — sign
   in with your own account.
3. Ask Claude to provision: one project, a `production` branch and a `dev`/staging branch, run
   `CREATE EXTENSION IF NOT EXISTS vector;` on both, and get the pooled (`-pooler`) + direct
   connection strings for each branch. Claude will run `list_projects` first to confirm it resolved
   to your account, not a stray one, before creating anything.
4. `alembic upgrade head` against each branch's direct connection string builds the schema.

You'll end up with 4 connection strings total (pooled + direct × prod + staging) — save them for
step 2.

## 1. Render (backend) — 2 Web Services

1. Sign up / log in at render.com, connect your GitHub account, grant access to this repo.
2. **New → Web Service**, connect the repo, twice:
   - `captureos-api-staging` — branch `dev`, Dockerfile path `apps/api/Dockerfile`, **Free** instance type.
   - `captureos-api-production` — branch `main`, same Dockerfile, **Free** instance type (upgrade to Starter, $7/mo, later if cold starts become a problem).
3. On **each** service, set environment variables (staging service uses the staging Neon branch's URLs, production uses the production branch's):

   | Key | Staging value | Production value |
   |---|---|---|
   | `CAPTUREOS_ENV` | `staging` | `production` |
   | `JWT_SECRET` | a random ≥32-char string | a **different** random ≥32-char string |
   | `DATABASE_URL` | staging Neon pooled URL (`postgresql+asyncpg://...`) | production Neon pooled URL |
   | `DATABASE_URL_SYNC` | staging Neon direct URL (`postgresql+psycopg://...`) | production Neon direct URL |
   | `LLM_PROVIDER` | `gemini` (or `anthropic`) | same |
   | `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` | your key | your key (can reuse the same key across environments) |
   | `EMBEDDINGS_PROVIDER` | `gemini` | `gemini` |
   | `BILLING_PROVIDER` | `stripe` | `stripe` |
   | `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` / `STRIPE_PRICE_*` | test-mode keys | live-mode keys (whenever you're ready to take real payments — test-mode is fine to start) |
   | `WORKFLOW_INLINE_WORKER` | `true` | `true` |
   | `CORS_ALLOW_ORIGINS` | *(set after step 2 — the Netlify `dev` branch-deploy URL)* | *(set after step 2 — the Netlify production URL)* |

   Note: `DATABASE_URL` needs `+asyncpg` and `DATABASE_URL_SYNC` needs `+psycopg` swapped into
   Neon's connection string scheme — Neon gives you plain `postgresql://`.
4. Deploy. `config.py`'s fail-fast validator means a missing/wrong secret shows up as a boot
   failure in Render's logs, not a silent bad deploy — check there if a service won't come up.
5. Once both are live, note their URLs (`https://captureos-api-staging.onrender.com` and
   `https://captureos-api-production.onrender.com`, or whatever Render assigns).

## 2. Netlify (frontend)

1. Sign up / log in at netlify.com, connect GitHub, "Add new site" → pick this repo.
2. Netlify should auto-detect the monorepo via the committed `netlify.toml` (`base = "apps/web"`)
   — confirm the build settings show package/base directory `apps/web` and build command `pnpm build`.
3. Set `main` as the **Production** branch context (should be the default).
4. Continuous Deployment → **Branches and deploy contexts** → add `dev` as a branch deploy (gives
   it a persistent `dev--<sitename>.netlify.app` URL). Leave Deploy Previews on (default).
5. Site → **Environment variables** → add `NEXT_PUBLIC_API_BASE_URL` with **different values per
   context**: Production → your Render production URL, Branch deploy (`dev`) + Deploy Preview →
   your Render staging URL.
6. Trigger a deploy (push to `dev` or `main`, or "Trigger deploy" in the UI).

## 3. Close the loop — CORS

Once you have both Netlify URLs, go back to Render and set `CORS_ALLOW_ORIGINS` on each service to
the matching Netlify URL (staging service → the `dev--...netlify.app` URL, production → the
production URL), then redeploy each Render service so the new env var takes effect.

## Verify

- `curl https://<render-staging-url>/health` → `200`
- Open the Netlify `dev` branch-deploy URL, confirm it loads and can reach the API (check Network
  tab for the `NEXT_PUBLIC_API_BASE_URL` requests succeeding, not CORS-blocked)
- Repeat both checks for production
- `cd apps/web && PLAYWRIGHT_BASE_URL=<netlify-dev-url> pnpm test:e2e` — run the e2e suite against
  the live staging deploy once `make seed`-equivalent demo data exists there (see `docs/RUNNING.md`
  for the seed script; Render doesn't run `make seed` automatically)

## Ongoing

From here, the loop is: work on `dev` (or a feature branch → PR into `dev`) → push → Render/Netlify
auto-deploy staging → PR `dev` into `main` when ready → merge → Render/Netlify auto-deploy
production. `ci.yml`'s 4 checks are required on `main` (branch-protected); `dev` has the same
required checks but allows direct pushes.
