"""Local JWT auth provider. Verifies tokens issued by ``core.security``."""

from __future__ import annotations

from captureos.auth.base import AuthPrincipal, AuthProvider
from captureos.config import Settings
from captureos.core.security import decode_token


class LocalAuthProvider(AuthProvider):
    name = "local"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def verify_token(self, token: str) -> AuthPrincipal:
        payload = decode_token(token, expected_type="access")
        return AuthPrincipal(subject=str(payload["sub"]), email=payload.get("email"), is_local=True)
