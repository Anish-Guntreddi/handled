"""Auth provider interface and the principal it resolves a token to."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(slots=True)
class AuthPrincipal:
    # For local auth, ``subject`` is the CaptureOS user id. For Firebase it is the uid;
    # the user is then resolved/provisioned by ``external_auth_id``.
    subject: str
    email: str | None = None
    is_local: bool = True


@runtime_checkable
class AuthProvider(Protocol):
    name: str

    async def verify_token(self, token: str) -> AuthPrincipal: ...
