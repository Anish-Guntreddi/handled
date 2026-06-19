"""Pluggable authentication (D5). Local JWT by default; Firebase in prod."""

from __future__ import annotations

from functools import lru_cache

from captureos.auth.base import AuthPrincipal, AuthProvider
from captureos.auth.local import LocalAuthProvider
from captureos.config import AuthProviderName, get_settings


@lru_cache
def get_auth_provider() -> AuthProvider:
    settings = get_settings()
    if settings.auth_provider is AuthProviderName.firebase:
        from captureos.auth.firebase import FirebaseAuthProvider

        return FirebaseAuthProvider(settings)
    return LocalAuthProvider(settings)


__all__ = ["AuthPrincipal", "AuthProvider", "get_auth_provider"]
