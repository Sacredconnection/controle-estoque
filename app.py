from __future__ import annotations

import json
import os
from threading import Timer

startup_error: str | None = None

try:
    from dashboard_app import *  # noqa: F403
    from dashboard_app import app, settings
except Exception as exc:
    startup_error = f"{type(exc).__name__}: {exc}"

    def app(environ, start_response):
        path = environ.get("PATH_INFO", "/")
        if path == "/health":
            payload = {
                "status": "startup_error",
                "error": startup_error,
            }
        else:
            payload = {
                "status": "startup_error",
                "message": "A aplicação não pôde ser inicializada. Consulte /health.",
            }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        start_response(
            "500 Internal Server Error",
            [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body))),
                ("Cache-Control", "no-store"),
            ],
        )
        return [body]


if __name__ == "__main__":
    if startup_error:
        raise RuntimeError(startup_error)
    if os.getenv("OPEN_BROWSER", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "sim",
    }:
        import webbrowser

        Timer(
            1.2,
            lambda: webbrowser.open_new(f"http://localhost:{settings.port}"),  # noqa: F405
        ).start()
    app.run(host=settings.host, port=settings.port, debug=settings.debug)  # noqa: F405
