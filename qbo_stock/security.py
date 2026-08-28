from __future__ import annotations

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
    path = Path(instance_dir) / "flask_secret.key"
    value = _read_or_create(path, lambda: os.urandom(48).hex().encode("ascii"))
    return value.decode("ascii")


class TokenCipher:
    """Encrypts OAuth tokens before they are stored in SQLite."""

    def __init__(self, instance_dir: str | Path) -> None:
        key_path = Path(instance_dir) / "token_encryption.key"
        key = _read_or_create(key_path, Fernet.generate_key)
        self._fernet = Fernet(key)

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
