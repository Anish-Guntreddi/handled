#!/usr/bin/env bash
# Durable, OS-level cron entrypoint for the corpus embedding backfill.
#
# Supersedes the CronCreate-based approach in embed_daily_topup.sh's original comment: an
# in-session CronCreate job lives only in that Claude Code session's memory (fires only while
# the REPL is idle, dies when the session ends) — which is why the backfill stalled after two
# days back on 2026-07-14/15. A real `crontab` entry survives independent of any Claude session.
#
# This wrapper additionally brings up the infra embed_daily_topup.sh assumes is already running:
# starts colima (the Docker runtime) if it's down, starts the existing `captureos-db` container
# (never recreates it — the corpus data lives in its volume) if it's stopped, waits for health,
# then hands off to embed_daily_topup.sh.
#
# Installed via: crontab -e  (see docs/cli-tools.md / CLAUDE.md for the exact line)
# Safe to run anytime: embed_pending() only touches chunks with a NULL vector and commits
# per-batch, so overlapping/frequent invocations just no-op once nothing is pending.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
API_DIR="$REPO_ROOT/apps/api"
LOG="$API_DIR/.data/embed_cron_wrapper.log"
mkdir -p "$API_DIR/.data"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S %Z') $*" >> "$LOG"; }

# Bring up the Docker runtime (colima) if it's not already running.
if ! /opt/homebrew/bin/colima status >/dev/null 2>&1; then
  log "colima down — starting"
  /opt/homebrew/bin/colima start >> "$LOG" 2>&1 || { log "colima start FAILED — aborting this run"; exit 1; }
fi

# Start (never recreate) the existing DB container so its volume/data is untouched.
if ! /usr/local/bin/docker ps --filter "name=captureos-db" --filter "status=running" --format '{{.Names}}' | grep -q captureos-db; then
  log "captureos-db not running — starting existing container"
  /usr/local/bin/docker start captureos-db >> "$LOG" 2>&1 || { log "docker start captureos-db FAILED — aborting this run"; exit 1; }
fi

# Wait up to 30s for Postgres to accept connections.
for _ in $(seq 1 15); do
  /usr/local/bin/docker exec captureos-db pg_isready -U captureos -d captureos >/dev/null 2>&1 && break
  sleep 2
done

log "infra ready — handing off to embed_daily_topup.sh"
"$API_DIR/captureos/scripts/embed_daily_topup.sh"
log "wrapper run complete"
