#!/usr/bin/env bash
# Daily top-up for the corpus embedding backfill.
#
# The Gemini free tier caps embed requests at ~1000/day, so a full backfill of a large corpus
# takes several days. This script re-runs `captureos.corpus.embed` once a day; it's always safe
# to re-run since `embed_pending` only embeds chunks whose vector is still NULL (see
# captureos/corpus/ingest.py).
#
# Scheduled via the in-session CronCreate tool (not a system crontab entry) — it re-fires a
# prompt daily that runs this script and checks the "remaining unembedded chunks" line it logs;
# once that hits 0 the prompt cancels its own recurring job. Not part of the deployed app — a
# local dev convenience only.
#
# Run manually to check on / drive progress without waiting for the next scheduled run:
#   apps/api/captureos/scripts/embed_daily_topup.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$API_DIR/.data"
LOG="$LOG_DIR/embed_topup.log"

mkdir -p "$LOG_DIR"

{
  echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') — embed top-up starting ==="
  cd "$API_DIR" || exit 1

  if ! uv run python -m captureos.corpus.embed; then
    echo "embed pass exited with an error (likely the daily free-tier quota) — will retry tomorrow."
  fi

  remaining="$(uv run python -c '
import asyncio
from sqlalchemy import func, select
from captureos.db.session import session_scope
from captureos.models.corpus import CorpusChunk


async def main() -> None:
    async with session_scope() as session:
        total = (await session.execute(select(func.count(CorpusChunk.id)))).scalar_one()
        embedded = (
            await session.execute(
                select(func.count(CorpusChunk.id)).where(CorpusChunk.embedding.is_not(None))
            )
        ).scalar_one()
        print(total - embedded)


asyncio.run(main())
' 2>>"$LOG")"

  echo "remaining unembedded chunks: ${remaining:-unknown}"
  echo "=== $(date '+%Y-%m-%d %H:%M:%S %Z') — embed top-up finished ==="
} >> "$LOG" 2>&1

# Also echo the summary to stdout (outside the log redirect) so a caller — e.g. the scheduled
# CronCreate prompt — can read "remaining unembedded chunks: N" straight from this run's output
# without tailing the log file.
tail -n 3 "$LOG"
