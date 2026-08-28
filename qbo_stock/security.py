from __future__ import annotations

import base64
import hashlib
import hmac
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


def _read_or_create(path: Path, generator) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.read_bytes().strip()

    value = generator()
    path.write_bytes(value)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return value


def load_flask_secret(instance_dir: str | Path) -> str:
    configured = os.getenv("FLASK_SECRET_KEY", "").strip()
    if configured:
        return configured

    stable_source = os.getenv("QBO_CLIENT_SECRET", "").strip() or os.getenv(
        "APP_PASSWORD", ""
    ).strip()
    if os.getenv("VERCEL", "").strip() and stable_source:
        return hmac.new(
            stable_source.encode("utf-8"),
            b"qbo-stock-flask-session-v1",
            hashlib.sha256,
        ).hexdigest()

    path = Path(instance_dir) / "flask_secret.key"
    value = _read_or_create(path, lambda: os.urandom(48).hex().encode("ascii"))
    return value.decode("ascii")


class TokenCipher:
    """Encrypts OAuth tokens before they are stored in SQLite."""

    def __init__(self, instance_dir: str | Path) -> None:
        configured = os.getenv("TOKEN_ENCRYPTION_KEY", "").strip()
        if configured:
            key = configured.encode("ascii")
        else:
            stable_source = os.getenv("FLASK_SECRET_KEY", "").strip() or os.getenv(
                "QBO_CLIENT_SECRET", ""
            ).strip()
            if os.getenv("VERCEL", "").strip() and stable_source:
                digest = hmac.new(
                    stable_source.encode("utf-8"),
                    b"qbo-stock-token-encryption-v1",
                    hashlib.sha256,
                ).digest()
                key = base64.urlsafe_b64encode(digest)
            else:
                key_path = Path(instance_dir) / "token_encryption.key"
                key = _read_or_create(key_path, Fernet.generate_key)
        try:
            self._fernet = Fernet(key)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "TOKEN_ENCRYPTION_KEY deve ser uma chave Fernet válida."
            ) from exc

    def encrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._fernet.encrypt(value.encode("utf-8")).decode("ascii")

    def decrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return self._fernet.decrypt(value.encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise RuntimeError(
                "Não foi possível descriptografar os tokens. "
                "Não apague o arquivo instance/token_encryption.key."
            ) from exc
