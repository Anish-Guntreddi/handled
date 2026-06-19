# CaptureOS API + worker image. Uses uv for fast, reproducible installs.
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_PROJECT_ENVIRONMENT=/usr/local

# uv from the official distroless image (pinned by tag).
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /usr/local/bin/

WORKDIR /app

# System deps for psycopg/asyncpg builds are not needed (binary wheels), keep slim.
# Install dependencies first for layer caching.
COPY pyproject.toml ./
COPY uv.lock* ./
RUN uv sync --no-dev --no-install-project || uv pip install --system -e . 2>/dev/null || true

# App source
COPY . .
RUN uv sync --no-dev || true

EXPOSE 8000

# Default command runs the API; compose overrides for the worker.
CMD ["uvicorn", "captureos.main:app", "--host", "0.0.0.0", "--port", "8000"]
