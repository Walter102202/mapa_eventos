from app.services import reporte_service

REPORTE = {"lat": -33.4489, "lon": -70.6693, "severidad": "alta", "comentario": "Bache grande"}


def test_crear_reporte_fuera_de_rm_devuelve_400(client, monkeypatch):
    monkeypatch.setattr(reporte_service, "crear_reporte", lambda db, reporte, foto_url=None: None)
    r = client.post("/api/reportes", json=REPORTE)
    assert r.status_code == 400
    assert "Región Metropolitana" in r.json()["detail"]


def test_crear_reporte_ok_devuelve_201(client, monkeypatch):
    monkeypatch.setattr(
        reporte_service,
        "crear_reporte",
        lambda db, reporte, foto_url=None: {"id": 7, "codigo_comuna": "13101", "nombre_comuna": "Santiago"},
    )
    r = client.post("/api/reportes", json=REPORTE)
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == 7
    assert body["codigo_comuna"] == "13101"
    assert "Santiago" in body["mensaje"]


def test_crear_reporte_con_lat_invalida_devuelve_422(client):
    r = client.post("/api/reportes", json={**REPORTE, "lat": 95})
    assert r.status_code == 422
