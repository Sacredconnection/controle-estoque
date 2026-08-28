from types import SimpleNamespace

from qbo_stock.runtime import instance_dir
from qbo_stock.security import TokenCipher, load_flask_secret
from qbo_stock.vercel_storage import VercelBlobDatabase


class FakeBlobClient:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def iter_objects(self, *, prefix):
        return [
            SimpleNamespace(pathname=pathname)
            for pathname in sorted(self.files)
            if pathname.startswith(prefix)
        ]

    def get(self, pathname, **kwargs):
        content = self.files.get(pathname)
        if content is None:
            return None
        return SimpleNamespace(status_code=200, content=content)

    def put(self, pathname, body, **kwargs):
        self.files[pathname] = bytes(body)
        return SimpleNamespace(pathname=pathname)


def test_vercel_uses_writable_temporary_instance(monkeypatch, tmp_path):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("QBO_INSTANCE_DIR", raising=False)
    monkeypatch.setattr("qbo_stock.runtime.tempfile.gettempdir", lambda: str(tmp_path))

    assert instance_dir(tmp_path / "readonly") == tmp_path / "qbo-stock-instance"


def test_read_only_deployment_falls_back_without_vercel_variable(monkeypatch, tmp_path):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("QBO_INSTANCE_DIR", raising=False)
    monkeypatch.setattr("qbo_stock.runtime.tempfile.gettempdir", lambda: str(tmp_path))

    def deny_local_probe(*args, **kwargs):
        raise PermissionError("deployment somente leitura")

    monkeypatch.setattr("qbo_stock.runtime.tempfile.NamedTemporaryFile", deny_local_probe)

    assert instance_dir(tmp_path / "deployment") == tmp_path / "qbo-stock-instance"


def test_vercel_secrets_are_stable_between_cold_starts(monkeypatch, tmp_path):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("FLASK_SECRET_KEY", "segredo-estavel-da-sessao")
    monkeypatch.delenv("TOKEN_ENCRYPTION_KEY", raising=False)

    first_cipher = TokenCipher(tmp_path / "cold-start-1")
    second_cipher = TokenCipher(tmp_path / "cold-start-2")
    encrypted = first_cipher.encrypt("refresh-token")

    assert load_flask_secret(tmp_path / "cold-start-1") == "segredo-estavel-da-sessao"
    assert second_cipher.decrypt(encrypted) == "refresh-token"


def test_blob_snapshot_restores_sqlite_after_cold_start(tmp_path):
    client = FakeBlobClient()
    first = VercelBlobDatabase(tmp_path / "first" / "stock.db", "token", client=client)
    first.save_connection(
        slot="A",
        realm_id="123",
        company_name="Empresa A",
        access_token="encrypted-access",
        refresh_token="encrypted-refresh",
        access_expires_at=1,
        refresh_expires_at=2,
    )

    restored = VercelBlobDatabase(
        tmp_path / "second" / "stock.db", "token", client=client
    )

    connection = restored.get_connection("A")
    assert connection is not None
    assert connection["realm_id"] == "123"
    assert connection["company_name"] == "Empresa A"
