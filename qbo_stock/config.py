from __future__ import annotations

import os
from dataclasses import dataclass


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
        environment = os.getenv("QBO_ENVIRONMENT", "sandbox").strip().lower()
        if environment not in {"sandbox", "production"}:
            raise ValueError("QBO_ENVIRONMENT deve ser 'sandbox' ou 'production'.")

        redirect_uri = os.getenv("QBO_REDIRECT_URI", "").strip()
        vercel_hostname = (
            os.getenv("VERCEL_PROJECT_PRODUCTION_URL", "").strip()
            or os.getenv("VERCEL_URL", "").strip()
        ).strip("/")
        if not redirect_uri and vercel_hostname:
            if not vercel_hostname.startswith(("http://", "https://")):
                vercel_hostname = f"https://{vercel_hostname}"
            redirect_uri = f"{vercel_hostname}/oauth/callback"
        if not redirect_uri:
            redirect_uri = "http://localhost:8000/oauth/callback"

        try:
            port = int(os.getenv("PORT", "8000"))
        except ValueError as exc:
            raise ValueError("PORT deve ser um número inteiro.") from exc

        return cls(
            qbo_client_id=os.getenv("QBO_CLIENT_ID", "").strip(),
            qbo_client_secret=os.getenv("QBO_CLIENT_SECRET", "").strip(),
            qbo_redirect_uri=redirect_uri,
            qbo_environment=environment,
            qbo_minor_version=os.getenv("QBO_MINOR_VERSION", "75").strip(),
            company_a_label=os.getenv("COMPANY_A_LABEL", "Empresa A").strip() or "Empresa A",
            company_b_label=os.getenv("COMPANY_B_LABEL", "Empresa B").strip() or "Empresa B",
            legal_business_name=os.getenv(
                "LEGAL_BUSINESS_NAME", "Sacred Connection"
            ).strip()
            or "Sacred Connection",
            legal_contact_email=os.getenv(
                "LEGAL_CONTACT_EMAIL", "info@sacredconnection.co"
            ).strip()
            or "info@sacredconnection.co",
            legal_country=os.getenv("LEGAL_COUNTRY", "Brasil").strip() or "Brasil",
            app_password=os.getenv("APP_PASSWORD", "").strip(),
            host=os.getenv("HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=port,
            debug=os.getenv("DEBUG", "false").strip().lower() in {"1", "true", "yes", "sim"},
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
