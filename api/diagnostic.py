from __future__ import annotations

import importlib
import json
import os
import tempfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path


class handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        checks: dict[str, object] = {
            "python": True,
            "vercel": bool(os.getenv("VERCEL")),
            "blob_configured": bool(os.getenv("BLOB_READ_WRITE_TOKEN")),
            "flask_secret_configured": bool(os.getenv("FLASK_SECRET_KEY")),
            "token_key_configured": bool(os.getenv("TOKEN_ENCRYPTION_KEY")),
        }

        try:
            probe = Path(tempfile.gettempdir()) / "qbo-stock-write-probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            checks["temporary_filesystem"] = "ok"
        except Exception as exc:
            checks["temporary_filesystem"] = f"{type(exc).__name__}: {exc}"

        for module_name in ("flask", "cryptography", "openpyxl", "vercel.blob"):
            try:
                importlib.import_module(module_name)
                checks[f"import:{module_name}"] = "ok"
            except Exception as exc:
                checks[f"import:{module_name}"] = f"{type(exc).__name__}: {exc}"

        try:
            importlib.import_module("app")
            checks["import:app"] = "ok"
        except Exception as exc:
            checks["import:app"] = f"{type(exc).__name__}: {exc}"

        body = json.dumps(checks, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
