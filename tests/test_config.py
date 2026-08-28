from qbo_stock.config import Settings


def test_vercel_hostname_defines_production_oauth_callback(monkeypatch):
    monkeypatch.setenv("QBO_ENVIRONMENT", "production")
    monkeypatch.setenv(
        "VERCEL_PROJECT_PRODUCTION_URL", "controle-estoque-pi-two.vercel.app"
    )
    monkeypatch.delenv("QBO_REDIRECT_URI", raising=False)

    settings = Settings.from_env()

    assert settings.qbo_redirect_uri == (
        "https://controle-estoque-pi-two.vercel.app/oauth/callback"
    )
    assert not settings.production_redirect_warning


def test_explicit_redirect_uri_has_priority_over_vercel_hostname(monkeypatch):
    monkeypatch.setenv("QBO_ENVIRONMENT", "production")
    monkeypatch.setenv("VERCEL_URL", "preview-controle-estoque.vercel.app")
    monkeypatch.setenv("QBO_REDIRECT_URI", "https://estoque.example.com/oauth/callback")

    settings = Settings.from_env()

    assert settings.qbo_redirect_uri == "https://estoque.example.com/oauth/callback"


def test_vercel_values_pasted_with_assignment_or_quotes_are_normalized(monkeypatch):
    monkeypatch.setenv("QBO_ENVIRONMENT", 'QBO_ENVIRONMENT="production"')
    monkeypatch.setenv("PORT", '"8000"')
    monkeypatch.setenv(
        "QBO_REDIRECT_URI",
        "QBO_REDIRECT_URI=https://controle-estoque-pi-two.vercel.app/oauth/callback",
    )

    settings = Settings.from_env()

    assert settings.qbo_environment == "production"
    assert settings.port == 8000
    assert settings.qbo_redirect_uri.endswith("/oauth/callback")
