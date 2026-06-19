"""Firebase auth provider. Verifies Firebase ID tokens (prod; `gcp` extra)."""

from __future__ import annotations

from captureos.auth.base import AuthPrincipal, AuthProvider
from captureos.config import Settings
from captureos.core.errors import AuthError


class FirebaseAuthProvider(AuthProvider):  # pragma: no cover - requires Firebase config
    name = "firebase"

    def __init__(self, settings: Settings) -> None:
        try:
            import firebase_admin  # type: ignore
            from firebase_admin import credentials
        except ImportError as exc:
            raise RuntimeError("firebase-admin not installed (uv sync --extra gcp)") from exc
        if not firebase_admin._apps:
            cred = (
                credentials.Certificate(settings.google_application_credentials)
                if settings.google_application_credentials
                else credentials.ApplicationDefault()
            )
            firebase_admin.initialize_app(cred, {"projectId": settings.firebase_project_id})
        self._settings = settings

    async def verify_token(self, token: str) -> AuthPrincipal:
        import anyio
        from firebase_admin import auth as fb_auth  # type: ignore

        try:
            decoded = await anyio.to_thread.run_sync(lambda: fb_auth.verify_id_token(token))
        except Exception as exc:
            raise AuthError("Invalid Firebase token") from exc
        return AuthPrincipal(subject=decoded["uid"], email=decoded.get("email"), is_local=False)
