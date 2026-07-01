"""End-to-end verification of the CaptureOS Gemini-native test setup.

Loads the repo-root .env, then exercises the REAL provider seam:
  1. config sanity (providers selected, key present — never printed)
  2. a live Gemini LLM call (flash tier)
  3. a live Gemini embeddings call (dimension check)

Run:  cd apps/api && uv run python captureos/scripts/verify_setup.py

Secret values are never printed — only presence + non-secret results.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
API_DIR = Path(__file__).resolve().parents[2]  # apps/api — make `captureos` importable
sys.path.insert(0, str(API_DIR))


def _load_env() -> None:
    env = ROOT / ".env"
    if not env.exists():
        sys.exit(f"no .env at {env}")
    for raw in env.read_text().splitlines():
        s = raw.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key, val = s.split("=", 1)
        if " #" in val:  # strip trailing inline comment (space-hash)
            val = val.split(" #", 1)[0]
        os.environ.setdefault(key.strip(), val.strip())


def ok(label: str, msg: str = "") -> None:
    print(f"  PASS  {label}" + (f"  —  {msg}" if msg else ""))


def bad(label: str, msg: str = "") -> None:
    print(f"  FAIL  {label}" + (f"  —  {msg}" if msg else ""))


async def main() -> int:
    _load_env()
    failures = 0

    from captureos.config import get_settings

    s = get_settings()
    print("=== Config ===")
    print(f"  LLM_PROVIDER        = {s.llm_provider}")
    print(f"  EMBEDDINGS_PROVIDER = {s.embeddings_provider}")
    print(f"  GEMINI_API_KEY      = {'present' if s.gemini_api_key else 'MISSING'}")
    print(f"  gemini models       = pro:{s.gemini_model_pro}  flash:{s.gemini_model_flash}")
    print(f"  embedding model/dim = {s.embedding_model} / {s.embedding_dim}")
    print(f"  BILLING_PROVIDER    = {s.billing_provider}")

    if str(s.llm_provider) != "gemini" or str(s.embeddings_provider) != "gemini":
        bad("providers not both 'gemini'")
        failures += 1
    if not s.gemini_api_key:
        bad("GEMINI_API_KEY missing — paste it into .env")
        return 1

    from captureos.providers import get_embeddings, get_llm, reset_providers
    from captureos.providers.base import ModelTier

    reset_providers()

    print("\n=== Live Gemini LLM call (flash tier) ===")
    try:
        llm = get_llm(ModelTier.flash)  # no Settings arg — lru_cache needs hashable args
        resp = await llm.generate(
            "Reply with exactly one word: READY",
            tier=ModelTier.flash,
            max_output_tokens=2048,  # 2.5 models reserve budget for thinking tokens
            temperature=0.0,
        )
        text = (resp.text or "").strip()
        detail = f"model={resp.model} text={text!r} in/out={resp.input_tokens}/{resp.output_tokens}"
        ok("LLM responded", detail)
    except Exception as exc:  # noqa: BLE001
        failures += 1
        bad("LLM call failed", f"{type(exc).__name__}: {exc}")

    print("\n=== Live Gemini embeddings call ===")
    try:
        emb = get_embeddings()
        res = await emb.embed(["small business government compliance"])
        dim = len(res.vectors[0])
        if dim == s.embedding_dim:
            ok("embeddings responded", f"model={res.model} dim={dim}")
        else:
            failures += 1
            bad("embedding dimension mismatch", f"got {dim}, expected {s.embedding_dim}")
    except Exception as exc:  # noqa: BLE001
        failures += 1
        bad("embeddings call failed", f"{type(exc).__name__}: {exc}")

    print()
    if failures == 0:
        print("ALL CHECKS PASSED — Gemini-native setup is live and working.")
    else:
        print(f"{failures} check(s) FAILED — see above.")
    return failures


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
