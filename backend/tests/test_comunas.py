from datetime import datetime

from app.config import get_settings
from app.services import agent_service, comuna_service, llm_service, reporte_service

COMUNA = {"codigo_comuna": "13101", "nombre_comuna": "Santiago", "codigo_region": "13", "total_baches": 3}


def _mock_resumen(monkeypatch):
    monkeypatch.setattr(comuna_service, "get_comuna_by_codigo", lambda db, codigo: COMUNA)
    monkeypatch.setattr(reporte_service, "get_top_clusters_por_comuna", lambda db, codigo, limit=5: [])
    monkeypatch.setattr(reporte_service, "get_comentarios_recientes", lambda db, codigo, limit=50: [])
    monkeypatch.setattr(
        llm_service,
        "generate_resumen",
        lambda **kw: {"resumen": "ok", "top5": [], "generated_at": datetime.now(), "from_cache": False},
    )


def test_agente_aplica_rate_limit(client, monkeypatch, limiter_on):
    monkeypatch.setattr(
        agent_service, "run_agent", lambda **kw: {"respuesta": "hola", "generated_at": datetime.now(), "iterations": 1}
    )
    for _ in range(2):
        assert client.post("/api/comunas/agente", json={"prompt": "resumen de Ñuñoa"}).status_code == 200
    assert client.post("/api/comunas/agente", json={"prompt": "resumen de Ñuñoa"}).status_code == 429


def test_resumen_aplica_rate_limit(client, monkeypatch, limiter_on):
    _mock_resumen(monkeypatch)
    for _ in range(2):
        assert client.get("/api/comunas/13101/resumen").status_code == 200
    assert client.get("/api/comunas/13101/resumen").status_code == 429


def test_refresh_sin_token_devuelve_403(client, monkeypatch):
    _mock_resumen(monkeypatch)
    monkeypatch.setattr(get_settings(), "admin_token", "secreto")
    assert client.get("/api/comunas/13101/resumen?refresh=true").status_code == 403


def test_refresh_con_token_incorrecto_devuelve_403(client, monkeypatch):
    _mock_resumen(monkeypatch)
    monkeypatch.setattr(get_settings(), "admin_token", "secreto")
    r = client.get("/api/comunas/13101/resumen?refresh=true", headers={"X-Admin-Token": "otro"})
    assert r.status_code == 403


def test_refresh_con_admin_token_vacio_devuelve_403(client, monkeypatch):
    _mock_resumen(monkeypatch)
    monkeypatch.setattr(get_settings(), "admin_token", "")
    r = client.get("/api/comunas/13101/resumen?refresh=true", headers={"X-Admin-Token": ""})
    assert r.status_code == 403


def test_refresh_con_token_correcto_devuelve_200(client, monkeypatch):
    _mock_resumen(monkeypatch)
    monkeypatch.setattr(get_settings(), "admin_token", "secreto")
    r = client.get("/api/comunas/13101/resumen?refresh=true", headers={"X-Admin-Token": "secreto"})
    assert r.status_code == 200


def test_resumen_sin_refresh_no_requiere_token(client, monkeypatch):
    _mock_resumen(monkeypatch)
    assert client.get("/api/comunas/13101/resumen").status_code == 200


def test_agente_no_filtra_detalle_del_error(client, monkeypatch):
    def explota(**kw):
        raise RuntimeError("Access denied for user 'root'@'10.0.0.5'")

    monkeypatch.setattr(agent_service, "run_agent", explota)
    r = client.post("/api/comunas/agente", json={"prompt": "resumen de Ñuñoa"})
    assert r.status_code == 500
    assert "10.0.0.5" not in r.json()["detail"]
    assert "root" not in r.json()["detail"]


def test_generate_resumen_no_filtra_detalle_del_error(monkeypatch):
    from tests.conftest import FakeSession

    monkeypatch.setattr(llm_service, "get_cached_resumen", lambda db, codigo, max_age_hours=24: None)

    def explota(prompt):
        raise RuntimeError("Incorrect API key provided: sk-abc123")

    monkeypatch.setattr(llm_service, "call_openai", explota)
    out = llm_service.generate_resumen(
        db=FakeSession(), codigo_comuna="13101", nombre_comuna="Santiago",
        total_baches=3, top_clusters=[], comentarios=[], use_cache=True,
    )
    assert "sk-abc123" not in out["resumen"]
    assert "sk-abc123" not in str(out.get("error", ""))
    assert "Santiago" in out["resumen"]
