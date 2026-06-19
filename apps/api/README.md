# CaptureOS API

FastAPI service + agent worker for CaptureOS. SQLAlchemy 2 (async) + Alembic + pgvector.

```bash
uv sync                 # install
uv run alembic upgrade head
uv run uvicorn captureos.main:app --reload
uv run pytest -q
```

Provider selection (LLM, storage, queue, secrets, embeddings, docparse, audit, auth) is
config-driven — see the repo-root `.env.example`. Defaults are local/mock so this runs
with no cloud credentials.
