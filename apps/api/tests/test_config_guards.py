"""Startup fail-closed guards for prod-like envs (CON-4).

Mirrors the mock-billing guard: mock Issuing must never run on its PUBLIC default HMAC secret in a
deployed env, because the /webhooks/stripe/issuing route is mounted unconditionally and would then
approve/decline card swipes anyone could forge. Local/dev is intentionally unaffected.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from captureos.config import Settings


def _prod_settings(**overrides: object) -> Settings:
    """Build a Settings that PASSES every OTHER production guard, so a test isolates one field.

    ``_env_file=None`` skips the repo-root .env; explicit kwargs override any inherited OS env.
    """
    base: dict[str, object] = {
        "captureos_env": "production",
        "jwt_secret": "x" * 40,  # strong, non-default
        "billing_provider": "stripe",
        "stripe_webhook_secret": "whsec_billing_test",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


def test_prod_rejects_default_mock_issuing_secret() -> None:
    # Issuing disabled (default) + the PUBLIC default mock secret → fail closed at startup.
    with pytest.raises(ValidationError, match="mock Issuing secret is public"):
        _prod_settings()


def test_prod_allows_private_mock_issuing_secret() -> None:
    # Issuing intentionally off in prod, but the mock secret is private → allowed.
    s = _prod_settings(issuing_mock_secret="whsec_private_not_the_default")
    assert not s.stripe_issuing_enabled


def test_prod_allows_real_issuing_with_its_secret() -> None:
    # Real Issuing enabled with its own signing secret → allowed (the StripeIssuing path).
    s = _prod_settings(
        stripe_issuing_enabled=True,
        stripe_issuing_webhook_secret="whsec_real_issuing",
    )
    assert s.stripe_issuing_enabled
    assert s.issuing_webhook_secret == "whsec_real_issuing"


def test_prod_rejects_enabled_issuing_without_any_secret() -> None:
    # Real Issuing enabled but no signing secret anywhere → fail closed (the existing guard).
    with pytest.raises(ValidationError, match="STRIPE_ISSUING_WEBHOOK_SECRET"):
        _prod_settings(stripe_issuing_enabled=True, stripe_webhook_secret="")


def test_local_env_keeps_default_mock_secret() -> None:
    # Local/dev happy path is unaffected: mock Issuing still runs on the public default secret.
    s = Settings(_env_file=None, captureos_env="local", billing_provider="mock")
    assert not s.stripe_issuing_enabled
    assert s.issuing_mock_secret  # public default retained locally — mock hot path works offline
