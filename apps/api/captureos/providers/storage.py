"""Blob storage: LocalStorage (filesystem, default) and GCSStorage (prod).

Security: keys are sanitized to prevent path traversal outside the base dir (NFR-2).
URIs use a ``local://<key>`` or ``gs://<bucket>/<key>`` scheme.
"""

from __future__ import annotations

from pathlib import Path

from captureos.config import Settings
from captureos.providers.base import PresignedUpload, StorageProvider, StoredBlob

_LOCAL_SCHEME = "local://"


def _key_from_uri(uri: str) -> str:
    return uri[len(_LOCAL_SCHEME) :] if uri.startswith(_LOCAL_SCHEME) else uri


class LocalStorage(StorageProvider):
    name = "local"

    def __init__(self, settings: Settings) -> None:
        self._base = Path(settings.storage_local_dir).resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Reject traversal: the resolved path must stay under the base dir.
        candidate = (self._base / key.lstrip("/")).resolve()
        if not str(candidate).startswith(str(self._base)):
            raise ValueError(f"Illegal storage key (path traversal): {key!r}")
        return candidate

    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredBlob:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredBlob(uri=f"{_LOCAL_SCHEME}{key}", size=len(data))

    async def get(self, uri: str) -> bytes:
        return self._path(_key_from_uri(uri)).read_bytes()

    async def delete(self, uri: str) -> None:
        path = self._path(_key_from_uri(uri))
        if path.exists():
            path.unlink()

    async def exists(self, uri: str) -> bool:
        return self._path(_key_from_uri(uri)).exists()

    def presign_upload(self, key: str, *, content_type: str | None = None) -> PresignedUpload:
        # The backend hosts the upload route for local storage (added in M1).
        return PresignedUpload(
            url=f"/api/v1/blobs/{key}",
            method="PUT",
            headers={"content-type": content_type} if content_type else {},
            storage_uri=f"{_LOCAL_SCHEME}{key}",
        )

    def presign_download(self, uri: str, *, expires_seconds: int = 3600) -> str:
        return f"/api/v1/blobs/{_key_from_uri(uri)}"


class GCSStorage(StorageProvider):  # pragma: no cover - requires GCP credentials
    name = "gcs"

    def __init__(self, settings: Settings) -> None:
        if not settings.gcs_bucket:
            raise RuntimeError("GCS_BUCKET required when STORAGE_PROVIDER=gcs")
        try:
            from google.cloud import storage  # type: ignore
        except ImportError as exc:
            raise RuntimeError("google-cloud-storage not installed (uv sync --extra gcp)") from exc
        self._bucket_name = settings.gcs_bucket
        self._client = storage.Client()
        self._bucket = self._client.bucket(settings.gcs_bucket)

    def _key_from_uri(self, uri: str) -> str:
        prefix = f"gs://{self._bucket_name}/"
        return uri[len(prefix) :] if uri.startswith(prefix) else uri

    async def put(self, key: str, data: bytes, *, content_type: str | None = None) -> StoredBlob:
        import anyio

        blob = self._bucket.blob(key)
        await anyio.to_thread.run_sync(
            lambda: blob.upload_from_string(data, content_type=content_type)
        )
        return StoredBlob(uri=f"gs://{self._bucket_name}/{key}", size=len(data))

    async def get(self, uri: str) -> bytes:
        import anyio

        blob = self._bucket.blob(self._key_from_uri(uri))
        return await anyio.to_thread.run_sync(blob.download_as_bytes)

    async def delete(self, uri: str) -> None:
        import anyio

        blob = self._bucket.blob(self._key_from_uri(uri))
        await anyio.to_thread.run_sync(blob.delete)

    async def exists(self, uri: str) -> bool:
        import anyio

        blob = self._bucket.blob(self._key_from_uri(uri))
        return await anyio.to_thread.run_sync(blob.exists)

    def presign_upload(self, key: str, *, content_type: str | None = None) -> PresignedUpload:
        from datetime import timedelta

        blob = self._bucket.blob(key)
        url = blob.generate_signed_url(
            version="v4", expiration=timedelta(minutes=15), method="PUT", content_type=content_type
        )
        return PresignedUpload(
            url=url,
            method="PUT",
            headers={"content-type": content_type} if content_type else {},
            storage_uri=f"gs://{self._bucket_name}/{key}",
        )

    def presign_download(self, uri: str, *, expires_seconds: int = 3600) -> str:
        from datetime import timedelta

        blob = self._bucket.blob(self._key_from_uri(uri))
        return blob.generate_signed_url(
            version="v4", expiration=timedelta(seconds=expires_seconds), method="GET"
        )
