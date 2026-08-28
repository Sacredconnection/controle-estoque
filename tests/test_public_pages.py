from dataclasses import replace

import app as app_module


def test_required_intuit_pages_are_public_with_dashboard_password(monkeypatch):
    protected_settings = replace(app_module.settings, app_password="senha-de-teste")
    monkeypatch.setattr(app_module, "settings", protected_settings)
    app_module.app.config.update(TESTING=True)
    client = app_module.app.test_client()

    dashboard = client.get("/")
    assert dashboard.status_code == 302
    assert dashboard.headers["Location"].endswith("/login")

    expected_content = {
        "/eula": "Contrato de Licença de Usuário Final",
        "/privacy": "Política de Privacidade",
        "/connect": "Conectar ou reconectar uma empresa",
        "/disconnect": "Conexão encerrada",
    }
    for path, text in expected_content.items():
        response = client.get(path)
        assert response.status_code == 200
        assert text in response.get_data(as_text=True)


def test_launch_and_public_aliases_are_available():
    app_module.app.config.update(TESTING=True)
    client = app_module.app.test_client()

    assert client.get("/launch").status_code == 302
    assert client.get("/reconnect").status_code == 200
    assert client.get("/termos-de-uso").status_code == 200
    assert client.get("/politica-de-privacidade").status_code == 200
