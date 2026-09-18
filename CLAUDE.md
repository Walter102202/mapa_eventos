# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es

MVP para reportar y consultar baches en la Región Metropolitana de Santiago. Backend FastAPI + MySQL 8 espacial + OpenAI; frontend HTML/JS plano con Leaflet servido por el mismo FastAPI. Todo el código y los comentarios están en español.

## Comandos

Todo se ejecuta desde `backend/` (ahí viven `requirements.txt`, `.env` y `app/`).

```bash
cd backend
python -m venv venv && venv\Scripts\activate      # Windows
pip install -r requirements-dev.txt               # incluye requirements.txt + pytest + ruff
cp .env.example .env

# Base de datos (una sola vez)
mysql -u root -p < scripts/init_db.sql            # crea baches_rm, tablas, SP y vista
mysql -u root -p baches_rm < scripts/add_foto_column.sql   # migración posterior: columna foto_url
python scripts/download_comunas.py                # opcional: baja polígonos de OSM a data/comunas_rm.geojson
python scripts/load_comunas.py                    # carga data/comunas_rm.geojson en comunas_rm

# Servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Tests y lint
python -m pytest                                  # no requieren MySQL: get_db se mockea en tests/conftest.py
python -m pytest tests/test_reportes.py::test_crear_reporte_ok_devuelve_201
ruff check .                                      # config en pyproject.toml; B008 ignorado (Depends de FastAPI)
```

- App: http://localhost:8000 (reportar) y http://localhost:8000/informes. Swagger en `/docs`.
- `.env` va en `backend/` (pydantic-settings lo lee relativo al cwd, por eso hay que arrancar desde `backend/`). Variables en `.env.example`.
- Los tests que tocan un endpoint con datos mockean la función del service con `monkeypatch` (ver `tests/test_reportes.py`); no hay MySQL de prueba.
- Tests del frontend (sin build): `node --test frontend/tests/*.test.js` desde la raíz. `frontend/js/escape.js` (`escapeHtml`, `mdToHtml`) se carga antes de `app.js` e `informes.js`; todo dato de la API, de Nominatim o del LLM que llegue a `innerHTML`/`bindPopup` pasa por ahí.
- Variables de seguridad en `.env`: `CORS_ORIGINS` (vacío = sin CORS), `RATE_LIMIT_ENABLED`, `RATE_LIMIT_IA` (por IP, aplica a agente, resumen y con-foto), `ADMIN_TOKEN` (obligatorio para `?refresh=true`, header `X-Admin-Token`). En tests `conftest.py` deshabilita el limiter y fija `2/minute`; el fixture `limiter_on` lo enciende.

## Arquitectura

**Flujo:** `routers/` (HTTP, validación, códigos de error) → `services/` (SQL crudo + OpenAI) → MySQL. Los routers no tocan SQL salvo dos endpoints en `routers/comunas.py` (`/informes` y `/{codigo}/informe`) que consultan `resumen_comuna` directo.

**Geometría fuera del ORM.** `models.py` (SQLAlchemy) declara las tablas pero omite las columnas espaciales (`comunas_rm.geom`, `reportes_baches.punto`). Todo lo espacial se hace con `text()` en los services: `ST_Contains` para asignar comuna a un punto (`comuna_service.find_comuna_for_point`), `ST_SRID(POINT(lon, lat), 4326)` al insertar, `ST_AsGeoJSON` para el mapa. Si un reporte cae fuera de la RM, `find_comuna_for_point` devuelve None y el router responde 400. Orden de coordenadas en SQL: `POINT(lon, lat)`.

**Clustering** de baches = agrupar por `ROUND(lat,4), ROUND(lon,4)` (~11 m) con `GROUP_CONCAT`. Está duplicado en `reporte_service.get_top_clusters_por_comuna` y `agent_service.tool_obtener_top_ubicaciones`.

**Tres usos de OpenAI, tres modelos distintos, cada uno con su propio `get_openai_client()`:**
- `llm_service`: resumen por comuna (`GET /api/comunas/{codigo}/resumen`), cacheado 24 h en `resumen_comuna`; `?refresh=true` lo regenera.
- `agent_service`: agente con tool-calling (`POST /api/comunas/agente`), loop de máx. 5 iteraciones sobre `TOOLS` / `execute_tool`. Si detecta una comuna, guarda la respuesta en `resumen_comuna` también, así que el agente y el resumen comparten la misma tabla caché.
- `image_service`: moderación de la foto (vision) antes de guardarla en `backend/uploads/`, que FastAPI sirve en `/uploads/`. Foto rechazada → 422.

**Reportes:** `POST /api/reportes` (JSON) y `POST /api/reportes/con-foto` (multipart). El frontend elige uno u otro según haya foto.

**Frontend** (`frontend/`): dos páginas sin build step. `js/app.js` es el mapa de reporte (Leaflet, geolocalización, búsqueda de direcciones vía Nominatim, chat con el agente). `js/informes.js` lista comunas y muestra informes guardados, con caché en `localStorage`. Ambas llaman a la API por ruta relativa `/api`, así que hay que servirlas desde FastAPI, no abrir el HTML a mano.

**Seguridad.** `app/limiter.py` (slowapi, por IP) decora los endpoints que llaman a OpenAI; los endpoints decorados deben recibir `request: Request` con ese nombre exacto. Las fotos se leen en chunks con `image_service.read_upload_limited` (413 si superan 5 MB) y se validan por contenido con Pillow (`validate_image_content`) antes de la moderación. Los `except` de agente y resumen loggean con `logging` y devuelven mensajes genéricos.

## Cambios de esquema

`init_db.sql` hace `DROP TABLE` de todo: no re-ejecutarlo sobre datos reales. Las migraciones posteriores van como scripts SQL sueltos en `backend/scripts/` (ejemplo: `add_foto_column.sql`) y hay que reflejarlas a mano en `models.py` y `schemas.py`.
