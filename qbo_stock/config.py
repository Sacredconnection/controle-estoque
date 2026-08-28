from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    prefix = f"{name}="
    if value.upper().startswith(prefix):
        value = value[len(prefix) :].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1].strip()
    return value or default


@dataclass(frozen=True)
class Settings:
    qbo_client_id: str
    qbo_client_secret: str
    qbo_redirect_uri: str
    qbo_environment: str
    qbo_minor_version: str
    company_a_label: str
    company_b_label: str
    legal_business_name: str
    legal_contact_email: str
    legal_country: str
    app_password: str
    host: str
    port: int
    debug: bool

    @classmethod
    def from_env(cls) -> "Settings":
        environment = _env("QBO_ENVIRONMENT", "sandbox").lower()
        environment = {
            "prod": "production",
            "produção": "production",
            "producao": "production",
            "real": "production",
            "dev": "sandbox",
            "development": "sandbox",
            "teste": "sandbox",
        }.get(environment, environment)
        if environment not in {"sandbox", "production"}:
            raise ValueError(
                "QBO_ENVIRONMENT deve ser 'sandbox' ou 'production'. "
                f"Valor recebido: {environment!r}."
            )

        redirect_uri = _env("QBO_REDIRECT_URI")
        vercel_hostname = (
            _env("VERCEL_PROJECT_PRODUCTION_URL") or _env("VERCEL_URL")
        ).strip("/")
        if not redirect_uri and vercel_hostname:
            if not vercel_hostname.startswith(("http://", "https://")):
                vercel_hostname = f"https://{vercel_hostname}"
            redirect_uri = f"{vercel_hostname}/oauth/callback"
        if not redirect_uri:
            redirect_uri = "http://localhost:8000/oauth/callback"

        try:
            port = int(_env("PORT", "8000"))
        except ValueError as exc:
            raise ValueError("PORT deve ser um número inteiro.") from exc

        return cls(
            qbo_client_id=_env("QBO_CLIENT_ID"),
            qbo_client_secret=_env("QBO_CLIENT_SECRET"),
            qbo_redirect_uri=redirect_uri,
            qbo_environment=environment,
            qbo_minor_version=_env("QBO_MINOR_VERSION", "75"),
            company_a_label=_env("COMPANY_A_LABEL", "Empresa A") or "Empresa A",
            company_b_label=_env("COMPANY_B_LABEL", "Empresa B") or "Empresa B",
            legal_business_name=_env("LEGAL_BUSINESS_NAME", "Sacred Connection")
            or "Sacred Connection",
            legal_contact_email=_env(
                "LEGAL_CONTACT_EMAIL", "info@sacredconnection.co"
            )
            or "info@sacredconnection.co",
            legal_country=_env("LEGAL_COUNTRY", "Brasil") or "Brasil",
            app_password=_env("APP_PASSWORD"),
            host=_env("HOST", "127.0.0.1") or "127.0.0.1",
            port=port,
            debug=_env("DEBUG", "false").lower() in {"1", "true", "yes", "sim"},
        )

    @property
    def credentials_ready(self) -> bool:
        return bool(self.qbo_client_id and self.qbo_client_secret and self.qbo_redirect_uri)

    @property
    def api_base_url(self) -> str:
        if self.qbo_environment == "sandbox":
            return "https://sandbox-quickbooks.api.intuit.com"
        return "https://quickbooks.api.intuit.com"

    @property
    def labels(self) -> dict[str, str]:
        return {"A": self.company_a_label, "B": self.company_b_label}

    @property
    def production_redirect_warning(self) -> bool:
        return self.qbo_environment == "production" and not self.qbo_redirect_uri.lower().startswith(
            "https://"
        )
