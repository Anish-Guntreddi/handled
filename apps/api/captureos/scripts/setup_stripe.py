"""One-time, idempotent setup of CaptureOS Stripe subscription products + prices.

Creates the three subscription tiers the billing layer expects — consumed by
``captureos.providers.billing.StripeBilling`` via ``STRIPE_PRICE_AUDIT`` /
``STRIPE_PRICE_SPRINT`` / ``STRIPE_PRICE_AUTOPILOT`` in ``.env``. Re-running is safe:
products are keyed by ``metadata["tier"]`` and reused if they already exist, so prices
are never duplicated.

The amounts here are SANDBOX placeholders — real pricing is a business decision and can
change any time WITHOUT a code change, because the app references price IDs, not amounts.

Run (CWD-independent; reads the repo-root .env directly):

    cd apps/api && uv run python captureos/scripts/setup_stripe.py

The secret key never leaves your machine — the script reads it locally and only prints
the (non-secret) price IDs to paste back into .env.
"""

from __future__ import annotations

import sys
from pathlib import Path

# (env-var suffix, metadata tier, product name, monthly price in cents, description)
TIERS: list[tuple[str, str, str, int, str]] = [
    ("AUDIT", "audit", "CaptureOS — Audit", 9900,
     "Find (money discovery) + Copilot (cited Q&A). The acquisition tier."),
    ("SPRINT", "sprint", "CaptureOS — Sprint", 29900,
     "Everything in Audit + Pursue (filing prep, compliance matrix, auto-filled forms, export)."),
    ("AUTOPILOT", "autopilot", "CaptureOS — Autopilot", 59900,
     "Everything in Sprint + auto-updating compliance, renewals, and the spend guardrail."),
]

REPO_ROOT = Path(__file__).resolve().parents[4]
ENV_PATH = REPO_ROOT / ".env"


def _read_secret_key() -> str:
    if not ENV_PATH.exists():
        sys.exit(f"No .env found at {ENV_PATH}")
    for raw in ENV_PATH.read_text().splitlines():
        line = raw.strip()
        if line.startswith("#") or not line.startswith("STRIPE_SECRET_KEY="):
            continue
        key = line.split("=", 1)[1].strip()
        if key:
            return key
    sys.exit("STRIPE_SECRET_KEY is empty in .env — paste your sandbox secret key first.")


def _existing_product(stripe, tier: str):
    """Return the active product already tagged with this tier, or None (idempotency)."""
    for product in stripe.Product.list(active=True, limit=100).auto_paging_iter():
        try:
            existing_tier = product["metadata"]["tier"]
        except (KeyError, TypeError):
            existing_tier = None
        if existing_tier == tier:
            return product
    return None


def main() -> None:
    try:
        import stripe  # type: ignore
    except ImportError:
        sys.exit("stripe SDK not installed — run: uv sync --extra gcp")

    stripe.api_key = _read_secret_key()
    if stripe.api_key.startswith("sk_live"):
        sys.exit("Refusing to run against a LIVE key from a setup script. Use a sandbox/test key.")

    env_lines = ["BILLING_PROVIDER=stripe"]
    for env_suffix, tier, name, amount_cents, blurb in TIERS:
        product = _existing_product(stripe, tier)
        try:
            default_price = product["default_price"] if product is not None else None
        except (KeyError, TypeError):
            default_price = None
        if default_price:
            price_id, action = default_price, "reused"
        else:
            if product is None:
                product = stripe.Product.create(
                    name=name, description=blurb, metadata={"tier": tier}
                )
            price = stripe.Price.create(
                product=product.id, currency="usd",
                unit_amount=amount_cents, recurring={"interval": "month"},
            )
            stripe.Product.modify(product.id, default_price=price.id)
            price_id, action = price.id, "created"
        env_lines.append(f"STRIPE_PRICE_{env_suffix}={price_id}")
        print(f"  {action:>7}: {name}  ${amount_cents / 100:.0f}/mo  ->  {price_id}", file=sys.stderr)

    print("\n# ---- paste these into .env ----")
    print("\n".join(env_lines))


if __name__ == "__main__":
    main()
