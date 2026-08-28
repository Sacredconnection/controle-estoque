from qbo_stock.config import Settings


def test_render_hostname_defines_production_oauth_callback(monkeypatch):
    monkeypatch.setenv("QBO_ENVIRONMENT", "production")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "controle-estoque-qbo.onrender.com")
    monkeypatch.delenv("QBO_REDIRECT_URI", raising=False)

    settings = Settings.from_env()

    assert settings.qbo_redirect_uri == (
        "https://controle-estoque-qbo.onrender.com/oauth/callback"
    )
    assert not settings.production_redirect_warning


def test_explicit_redirect_uri_has_priority_over_render_hostname(monkeypatch):
    monkeypatch.setenv("QBO_ENVIRONMENT", "production")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "controle-estoque-qbo.onrender.com")
    monkeypatch.setenv("QBO_REDIRECT_URI", "https://estoque.example.com/oauth/callback")

    settings = Settings.from_env()

    assert settings.qbo_redirect_uri == "https://estoque.example.com/oauth/callback"
