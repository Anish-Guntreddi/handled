# CaptureOS developer entrypoints. Run `make help`.
SHELL := /bin/bash
API_DIR := apps/api
WEB_DIR := apps/web

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---------- Environment ----------
.PHONY: env
env: ## Create .env from .env.example if missing
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

.PHONY: setup
setup: env api-install web-install ## One-time local setup (env + deps)

# ---------- Infra ----------
.PHONY: db-up
db-up: env ## Start only Postgres+pgvector
	docker compose up -d db

.PHONY: up
up: env ## Start db + api + worker
	docker compose up -d db api worker

.PHONY: up-full
up-full: env ## Start the entire stack including web
	docker compose --profile full up -d

.PHONY: down
down: ## Stop the stack
	docker compose down

.PHONY: nuke
nuke: ## Stop and delete all volumes (DESTRUCTIVE)
	docker compose down -v

.PHONY: logs
logs: ## Tail logs
	docker compose logs -f --tail=100

# ---------- Backend (api) ----------
.PHONY: api-install
api-install: ## Install backend deps via uv
	cd $(API_DIR) && uv sync

.PHONY: migrate
migrate: ## Apply DB migrations
	cd $(API_DIR) && uv run alembic upgrade head

.PHONY: migration
migration: ## Autogenerate a migration: make migration m="message"
	cd $(API_DIR) && uv run alembic revision --autogenerate -m "$(m)"

.PHONY: api
api: ## Run the API locally (reload)
	cd $(API_DIR) && uv run uvicorn captureos.main:app --reload --port $${API_PORT:-8000}

.PHONY: worker
worker: ## Run the worker locally
	cd $(API_DIR) && uv run python -m captureos.worker.main

.PHONY: seed
seed: ## Seed demo data
	cd $(API_DIR) && uv run python -m captureos.scripts.seed

.PHONY: corpus-sync
corpus-sync: ## Run one corpus sync + embed pass (WS2 knowledge engine; a cron calls this on deploy)
	cd $(API_DIR) && uv run python -m captureos.corpus.sync && uv run python -m captureos.corpus.embed

.PHONY: corpus-discover
corpus-discover: ## Run one autonomous discovery sweep + embed (WS2; proposes deduped new targets)
	cd $(API_DIR) && uv run python -m captureos.corpus.discover && uv run python -m captureos.corpus.embed

.PHONY: corpus-schedule
corpus-schedule: ## Run the local tiered-cadence scheduler loop (WS2; localhost stand-in for Cloud Scheduler)
	cd $(API_DIR) && uv run python -m captureos.corpus.schedule

.PHONY: corpus-schedule-once
corpus-schedule-once: ## Run whatever corpus cadence tiers are due now, then exit (the cron unit of work)
	cd $(API_DIR) && uv run python -m captureos.corpus.schedule --once

# ---------- RAG eval (dev-only; isolated rag_eval schema, never deployed) ----------
.PHONY: rag-eval-init
rag-eval-init: ## Create the dev-only rag_eval schema + tables (create_all, not Alembic)
	cd $(API_DIR) && uv run --group rag-eval python -m captureos.rag_eval.cli init

.PHONY: rag-eval-seed
rag-eval-seed: ## Seed the synthetic-smoke golden set (idempotent)
	cd $(API_DIR) && uv run --group rag-eval python -m captureos.rag_eval.cli seed

.PHONY: rag-eval
rag-eval: ## Run the dense baseline over the synthetic-smoke dataset and persist a scored run
	cd $(API_DIR) && uv run --group rag-eval python -m captureos.rag_eval.cli run --dataset synthetic-smoke

.PHONY: rag-dashboard
rag-dashboard: ## Launch the Streamlit eval dashboard (runs + metric tiles)
	cd $(API_DIR) && uv run --group rag-eval streamlit run captureos/rag_eval/dashboard/app.py

# ---------- Frontend (web) ----------
.PHONY: web-install
web-install: ## Install frontend deps
	cd $(WEB_DIR) && pnpm install

.PHONY: web
web: ## Run the web app locally
	cd $(WEB_DIR) && pnpm dev

# ---------- Quality ----------
.PHONY: test
test: ## Run backend tests
	cd $(API_DIR) && uv run pytest -q

.PHONY: lint
lint: ## Lint + type-check backend
	cd $(API_DIR) && uv run ruff check . && uv run mypy captureos

.PHONY: fmt
fmt: ## Format backend
	cd $(API_DIR) && uv run ruff format . && uv run ruff check --fix .

.PHONY: web-check
web-check: ## Lint + type-check frontend
	cd $(WEB_DIR) && pnpm lint && pnpm typecheck

.PHONY: check
check: lint test ## Run all backend checks

# ---------- Phase gate (D9) ----------
.PHONY: codex-review
codex-review: ## Independent codex review of the working tree
	codex exec review

.PHONY: gate
gate: check ## Phase gate: tests+lint, then run codex + security + qa skills (skills invoked by the agent)
	@echo "Backend checks passed. Now run: codex review, /security-audit, /security-review, /qa"
