from __future__ import annotations

import os
import tempfile
from pathlib import Path


def instance_dir(base_dir: str | Path) -> Path:
    """Return a writable instance directory for local and serverless runtimes."""
    configured = os.getenv("QBO_INSTANCE_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    if os.getenv("VERCEL", "").strip():
        return Path(tempfile.gettempdir()) / "qbo-stock-instance"

    local_instance = Path(base_dir).resolve() / "instance"
    try:
        local_instance.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=local_instance, prefix=".write-probe-"):
            pass
        return local_instance
    except OSError:
        return Path(tempfile.gettempdir()) / "qbo-stock-instance"
