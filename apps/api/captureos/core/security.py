"""Password hashing (Argon2) and JWT issuance/verification for local auth."""

from __future__ import annotations

import contextlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from captureos.config import get_settings
from captureos.core.errors import AuthError

_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        # Malformed/legacy hash → treat as a failed verification rather than erroring.
        return False


# Precomputed hash used to spend comparable CPU on the "user not found" login path,
# so response timing doesn't reveal whether an email is registered (anti-enumeration).
_DUMMY_HASH = _ph.hash("captureos-timing-equalization-constant")  # noqa: S106


def dummy_verify(plain: str) -> None:
    """Run an Argon2 verification and discard the result (constant-ish timing)."""
    with contextlib.suppress(Exception):
        _ph.verify(_DUMMY_HASH, plain)


def needs_rehash(hashed: str) -> bool:
    try:
        return _ph.check_needs_rehash(hashed)
    except Exception:
        return False


def _create_token(subject: str, token_type: str, ttl: timedelta, extra: dict | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str | uuid.UUID, extra: dict | None = None) -> str:
    settings = get_settings()
    return _create_token(
        str(user_id), "access", timedelta(minutes=settings.jwt_access_ttl_minutes), extra
    )


def create_refresh_token(user_id: str | uuid.UUID) -> str:
    settings = get_settings()
    return _create_token(str(user_id), "refresh", timedelta(days=settings.jwt_refresh_ttl_days))


def decode_token(token: str, *, expected_type: str | None = None) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token has expired", code="token_expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid token") from exc
    if expected_type and payload.get("type") != expected_type:
        raise AuthError(f"Expected a {expected_type} token")
    return payload
