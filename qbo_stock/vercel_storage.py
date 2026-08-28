from __future__ import annotations

import os
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import requests

from .db import Database


class _RequestsBlobClient:
    api_url = "https://vercel.com/api/blob"

    def __init__(self, token: str) -> None:
        self.token = token
        parts = token.split("_")
        if len(parts) < 4 or not parts[3]:
            raise ValueError("BLOB_READ_WRITE_TOKEN inválido.")
        self.store_id = parts[3]

    def _headers(self, **extra: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "x-api-version": "11",
            "x-api-blob-request-id": (
                f"{self.store_id}:{int(time.time() * 1000)}:{uuid.uuid4().hex[:8]}"
            ),
            "x-api-blob-request-attempt": "0",
            **extra,
        }

    def iter_objects(self, *, prefix: str):
        cursor = None
        while True:
            params = {"prefix": prefix, "limit": 1000}
            if cursor:
                params["cursor"] = cursor
            response = requests.get(
                self.api_url,
                headers=self._headers(),
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            for item in payload.get("blobs", []):
                yield SimpleNamespace(
                    pathname=item["pathname"],
                    url=item.get("url", ""),
                )
            cursor = payload.get("cursor")
            if not payload.get("hasMore") or not cursor:
                break

    def get(self, pathname: str, **kwargs):
        url = (
            f"https://{self.store_id}.private.blob.vercel-storage.com/"
            f"{pathname.lstrip('/')}"
        )
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {self.token}"},
            timeout=30,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return SimpleNamespace(status_code=response.status_code, content=response.content)

    def put(self, pathname: str, body: bytes, **kwargs):
        response = requests.put(
            self.api_url,
            headers=self._headers(
                **{
                    "x-content-type": kwargs.get(
                        "content_type", "application/octet-stream"
                    ),
                    "x-add-random-suffix": "0",
                    "x-allow-overwrite": "0",
                    "x-vercel-blob-access": kwargs.get("access", "private"),
                }
            ),
            params={"pathname": pathname},
            data=body,
            timeout=30,
        )
        response.raise_for_status()
        return SimpleNamespace(pathname=pathname)


class VercelBlobDatabase(Database):
    """SQLite stored in /tmp with immutable snapshots in a private Vercel Blob store."""

    prefix = "qbo-stock/sqlite/"

    def __init__(
        self,
        path: str | Path,
        token: str,
        *,
        client: Any | None = None,
    ) -> None:
        if client is None:
            client = _RequestsBlobClient(token)
        self._client = client
        self._lock = threading.RLock()
        self._snapshot_pathname: str | None = None
        self.last_error: str | None = None
        self._local_path = Path(path)
        self._local_path.parent.mkdir(parents=True, exist_ok=True)
        self.refresh(strict=False)
        super().__init__(self._local_path)

    def _latest_snapshot(self):
        snapshots = self._client.iter_objects(prefix=self.prefix)
        return max(snapshots, key=lambda item: item.pathname, default=None)

    def refresh(self, *, strict: bool = False) -> bool:
        with self._lock:
            try:
                latest = self._latest_snapshot()
                if latest is None or latest.pathname == self._snapshot_pathname:
                    self.last_error = None
                    return True
                result = self._client.get(
                    latest.pathname,
                    access="private",
                    use_cache=False,
                )
                if result is None or result.status_code != 200:
                    raise RuntimeError("snapshot persistente não encontrado")
                temporary = self._local_path.with_suffix(".restore.tmp")
                temporary.write_bytes(result.content)
                os.replace(temporary, self._local_path)
                self._snapshot_pathname = latest.pathname
                self.last_error = None
                return True
            except Exception as exc:
                self.last_error = f"{type(exc).__name__}: {exc}"
                if strict:
                    raise RuntimeError(
                        "Não foi possível carregar o banco persistente da Vercel."
                    ) from exc
                return False

    def _persist(self) -> None:
        pathname = (
            f"{self.prefix}{time.time_ns():020d}-{uuid.uuid4().hex}.sqlite3"
        )
        try:
            self._client.put(
                pathname,
                self._local_path.read_bytes(),
                access="private",
                content_type="application/vnd.sqlite3",
                add_random_suffix=False,
            )
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise RuntimeError(
                "A alteração local foi feita, mas não pôde ser persistida no Vercel Blob."
            ) from exc
        self._snapshot_pathname = pathname
        self.last_error = None

    def _prepare_write(self) -> None:
        self.refresh(strict=True)

    def save_connection(self, **kwargs) -> None:
        with self._lock:
            self._prepare_write()
            super().save_connection(**kwargs)
            self._persist()

    def update_tokens(self, slot: str, **kwargs) -> None:
        with self._lock:
            self._prepare_write()
            super().update_tokens(slot, **kwargs)
            self._persist()

    def delete_connection(self, slot: str) -> None:
        with self._lock:
            self._prepare_write()
            super().delete_connection(slot)
            self._persist()

    def replace_inventory(self, slot: str, items) -> int:
        with self._lock:
            self._prepare_write()
            count = super().replace_inventory(slot, items)
            self._persist()
            return count

    def record_sync(self, **kwargs) -> None:
        with self._lock:
            self._prepare_write()
            super().record_sync(**kwargs)
            self._persist()

    def clear_demo(self) -> None:
        with self._lock:
            self._prepare_write()
            super().clear_demo()
            self._persist()
