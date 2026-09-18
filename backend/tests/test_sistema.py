def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_frontend_se_sirve(client):
    assert client.get("/").status_code == 200
    assert client.get("/informes").status_code == 200


def test_limiter_registrado_en_app(client):
    from app.limiter import limiter
    from app.main import app

    assert app.state.limiter is limiter
    assert limiter.enabled is False  # conftest lo deshabilita para los tests


def test_settings_de_seguridad_tienen_defaults():
    from app.config import get_settings

    s = get_settings()
    assert s.cors_origins == ""
    assert s.rate_limit_ia == "2/minute"  # fijado por conftest vía env
    assert s.admin_token == ""


def test_sin_cors_origins_no_se_permite_origen_ajeno(client):
    r = client.get("/api/health", headers={"Origin": "https://malo.example"})
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers


def test_parse_cors_origins_ignora_vacios_y_espacios():
    from app.main import parse_cors_origins

    assert parse_cors_origins("") == []
    assert parse_cors_origins(" https://a.cl, https://b.cl ,") == ["https://a.cl", "https://b.cl"]
