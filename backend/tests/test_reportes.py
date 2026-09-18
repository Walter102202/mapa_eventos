import io

from PIL import Image

from app.services import image_service, reporte_service

REPORTE = {"lat": -33.4489, "lon": -70.6693, "severidad": "alta", "comentario": "Bache grande"}
FORM = {"lat": "-33.4489", "lon": "-70.6693", "severidad": "alta", "comentario": "Bache con foto"}
RESULTADO_OK = {"id": 9, "codigo_comuna": "13101", "nombre_comuna": "Santiago"}


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color="red").save(buf, format="PNG")
    return buf.getvalue()


def _mock_pipeline_ok(monkeypatch):
    monkeypatch.setattr(image_service, "moderate_image", lambda data: (True, ""))
    monkeypatch.setattr(image_service, "save_image", lambda data, name: "/uploads/test.png")
    monkeypatch.setattr(reporte_service, "crear_reporte", lambda db, reporte, foto_url=None: RESULTADO_OK)


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


def test_con_foto_ok_devuelve_201(client, monkeypatch):
    _mock_pipeline_ok(monkeypatch)
    r = client.post("/api/reportes/con-foto", data=FORM, files={"foto": ("bache.png", _png_bytes(), "image/png")})
    assert r.status_code == 201
    assert r.json()["id"] == 9


def test_con_foto_rechaza_contenido_que_no_es_imagen(client, monkeypatch):
    _mock_pipeline_ok(monkeypatch)
    r = client.post("/api/reportes/con-foto", data=FORM, files={"foto": ("bache.png", b"<html>hola</html>", "image/png")})
    assert r.status_code == 400
    assert "imagen" in r.json()["detail"].lower()


def test_con_foto_rechaza_archivo_grande_con_413(client, monkeypatch):
    _mock_pipeline_ok(monkeypatch)
    monkeypatch.setattr(image_service, "MAX_FILE_SIZE", 10)
    r = client.post("/api/reportes/con-foto", data=FORM, files={"foto": ("bache.png", _png_bytes(), "image/png")})
    assert r.status_code == 413


def test_con_foto_aplica_rate_limit(client, monkeypatch, limiter_on):
    _mock_pipeline_ok(monkeypatch)
    for _ in range(2):
        assert client.post("/api/reportes/con-foto", data=FORM).status_code == 201
    assert client.post("/api/reportes/con-foto", data=FORM).status_code == 429
