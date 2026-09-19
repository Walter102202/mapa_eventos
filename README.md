# Reportes de Baches · Región Metropolitana de Santiago

Aplicación web para reportar baches en el mapa y consultar, por comuna, qué se ha reportado y un informe generado con IA.

- **Reportar**: el usuario marca el punto en el mapa (o usa su ubicación / busca una dirección), elige severidad, agrega comentario y foto opcional. La comuna se asigna sola con MySQL espacial. Fuera de la RM se rechaza.
- **Consultar**: baches por comuna, top de ubicaciones repetidas, resumen IA cacheado 24 h e informes guardados.
- **Agente**: chat en lenguaje natural ("¿qué calles tienen más baches en Ñuñoa?") con tool-calling sobre la base de datos.
- **Moderación de fotos**: cada imagen pasa por un modelo de visión antes de guardarse; solo se aceptan fotos de baches o daños en la vía.

## Stack

| Capa | Tecnología |
|------|------------|
| Backend | Python 3.9+, FastAPI, SQLAlchemy 2, PyMySQL |
| Base de datos | MySQL 8 con tipos espaciales (SRID 4326) |
| IA | OpenAI (resumen por comuna, agente con tools, moderación de imágenes) |
| Frontend | HTML/CSS/JS sin build step, Leaflet, Nominatim para búsqueda de direcciones |
| Seguridad | slowapi (rate limit por IP), Pillow (validación de imágenes) |

## Arquitectura

```
frontend/ (Leaflet)  --/api-->  routers/  -->  services/  -->  MySQL 8 (espacial)
                                 HTTP          SQL crudo        +-- OpenAI (3 usos)
```

- `routers/` valida y devuelve códigos HTTP; `services/` hace el SQL (con `text()`) y llama a OpenAI.
- Lo espacial vive fuera del ORM: `ST_Contains` para asignar comuna, `ST_SRID(POINT(lon, lat), 4326)` al insertar, `ST_AsGeoJSON` para el mapa.
- Clustering de baches: agrupación por `ROUND(lat,4), ROUND(lon,4)` (~11 m).
- Tres llamadas a OpenAI con modelos distintos: `llm_service` (resumen), `agent_service` (agente, máx. 5 iteraciones de tools), `image_service` (moderación con visión).
- El resumen y el agente comparten la tabla caché `resumen_comuna`.
- El mismo FastAPI sirve el frontend (`/` y `/informes`) y las fotos subidas (`/uploads/`).

## Puesta en marcha

Requisitos: Python 3.9+, MySQL 8.0+, una API key de OpenAI.

Todo se ejecuta desde `backend/`: ahí están `requirements.txt`, `.env` y `app/`.

```bash
cd backend
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # Linux / macOS
pip install -r requirements.txt
cp .env.example .env             # completar credenciales (ver tabla abajo)
```

Base de datos, una sola vez:

```bash
mysql -u root -p < scripts/init_db.sql                     # crea baches_rm, tablas, SP y vista
mysql -u root -p baches_rm < scripts/add_foto_column.sql   # migración: columna foto_url
python scripts/download_comunas.py                          # baja polígonos de OSM a data/comunas_rm.geojson
python scripts/load_comunas.py                              # carga el GeoJSON en comunas_rm
```

`data/comunas_rm.geojson` ya viene en el repo; el script de descarga es opcional para regenerarlo. Alternativa manual: bajar "División Comunal" desde [BCN Chile](https://www.bcn.cl/siit/mapas_vectoriales), convertir a GeoJSON y guardarlo en esa ruta.

Servidor:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Reportar: http://localhost:8000
- Informes por comuna: http://localhost:8000/informes
- Swagger: http://localhost:8000/docs · ReDoc: http://localhost:8000/redoc

El frontend llama a la API por ruta relativa `/api`: hay que abrirlo desde FastAPI, no como archivo local.

## Variables de entorno

`.env` va en `backend/` (pydantic-settings lo lee relativo al cwd). Plantilla en `backend/.env.example`.

| Variable | Default | Descripción |
|----------|---------|-------------|
| `MYSQL_HOST` / `MYSQL_PORT` | `localhost` / `3306` | Servidor MySQL |
| `MYSQL_USER` / `MYSQL_PASSWORD` | `root` / vacío | Credenciales |
| `MYSQL_DATABASE` | `baches_rm` | Base creada por `init_db.sql` |
| `OPENAI_API_KEY` | vacío | Necesaria para resumen, agente y moderación de fotos |
| `DEBUG` | `false` | Modo debug |
| `CORS_ORIGINS` | vacío | Orígenes permitidos separados por coma. Vacío = sin CORS (el frontend lo sirve el mismo FastAPI) |
| `RATE_LIMIT_ENABLED` | `true` | Activa el límite por IP en los endpoints que llaman a OpenAI |
| `RATE_LIMIT_IA` | `5/minute` | Límite por IP y por endpoint (agente, resumen y con-foto tienen buckets independientes) |
| `ADMIN_TOKEN` | vacío | Obligatorio para `?refresh=true` en el resumen, va en el header `X-Admin-Token`. Vacío = refresh deshabilitado |

## API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/health` | Estado de la API |
| GET | `/api/info` | Metadata y endpoints principales |
| POST | `/api/reportes` | Crear reporte (JSON). 400 si cae fuera de la RM |
| POST | `/api/reportes/con-foto` | Crear reporte (multipart) con foto opcional. 400 tipo/contenido inválido, 413 > 5 MB, 422 rechazada por moderación, 429 rate limit |
| GET | `/api/comunas` | Listar comunas con total de baches |
| GET | `/api/comunas/geojson` | Polígonos de comunas para el mapa |
| GET | `/api/comunas/informes` | Comunas con fecha del informe guardado (payload compacto `c`/`n`/`f`) |
| GET | `/api/comunas/{codigo}` | Datos de una comuna. 404 si no existe |
| GET | `/api/comunas/{codigo}/baches` | Baches paginados (`page`, `page_size` máx. 200) |
| GET | `/api/comunas/{codigo}/resumen` | Resumen IA con top 5 de ubicaciones, cacheado 24 h. `?refresh=true` + `X-Admin-Token` lo regenera (403 sin token). 429 rate limit |
| GET | `/api/comunas/{codigo}/informe` | Informe guardado de la comuna, sin llamar a OpenAI |
| POST | `/api/comunas/agente` | Consulta en lenguaje natural al agente. 429 rate limit |

Severidad: `baja`, `media` (default), `alta`. Fotos: jpg, jpeg, png o webp, máximo 5 MB.

### Ejemplos

```bash
# Crear reporte
curl -X POST http://localhost:8000/api/reportes \
  -H "Content-Type: application/json" \
  -d '{"lat": -33.4489, "lon": -70.6693, "severidad": "alta", "comentario": "Bache grande en la esquina"}'

# Crear reporte con foto
curl -X POST http://localhost:8000/api/reportes/con-foto \
  -F lat=-33.4489 -F lon=-70.6693 -F severidad=media -F foto=@bache.jpg

# Resumen IA de Santiago (13101)
curl http://localhost:8000/api/comunas/13101/resumen

# Regenerar el resumen (requiere ADMIN_TOKEN)
curl "http://localhost:8000/api/comunas/13101/resumen?refresh=true" -H "X-Admin-Token: $ADMIN_TOKEN"

# Agente
curl -X POST http://localhost:8000/api/comunas/agente \
  -H "Content-Type: application/json" \
  -d '{"prompt": "¿Cuáles son las calles con más baches en Providencia?"}'
```

Los códigos de comuna son los oficiales (13101 Santiago, 13114 Las Condes, 13120 Ñuñoa, 13123 Providencia...). La lista completa sale de `GET /api/comunas`.

## Desarrollo

```bash
cd backend
pip install -r requirements-dev.txt     # requirements.txt + pytest + ruff
python -m pytest                        # no requiere MySQL: get_db se mockea en tests/conftest.py
python -m pytest tests/test_reportes.py::test_crear_reporte_ok_devuelve_201
ruff check .                            # lint (config en pyproject.toml)
ruff check . --fix

cd ..
node --test frontend/tests/*.test.js    # tests del frontend (escape.js), sin build
```

- Los tests de endpoints con datos mockean la función del service con `monkeypatch` (ver `tests/test_reportes.py`). No hay MySQL de prueba.
- `conftest.py` deshabilita el rate limiter y fija `2/minute`; el fixture `limiter_on` lo enciende para probar el 429.
- Todo el código y los comentarios están en español.

## Seguridad

- **Rate limit** por IP (slowapi) en los tres endpoints que llaman a OpenAI. Detrás de un proxy, arrancar uvicorn con `--proxy-headers` para que la IP sea la real.
- **Admin token**: `?refresh=true` dispara una llamada a OpenAI, por eso exige `X-Admin-Token` (comparación con `secrets.compare_digest`).
- **Uploads**: extensión, luego lectura en chunks con corte a 5 MB (413), validación de contenido con Pillow (magic bytes, bombas de descompresión), moderación con visión y guardado en `backend/uploads/`. El límite de 5 MB protege la memoria, no el request: Starlette ya spooleó el body a disco, así que en despliegue hace falta un límite en el proxy (`client_max_body_size` en nginx).
- **XSS**: `frontend/js/escape.js` (`escapeHtml`, `mdToHtml`) se carga antes de `app.js` e `informes.js`; todo dato de la API, de Nominatim o del LLM que llegue a `innerHTML`/`bindPopup` pasa por ahí.
- **CORS** solo si `CORS_ORIGINS` tiene valores, sin credenciales, métodos GET/POST.
- Los errores internos del agente y del resumen se loggean con `logging` y el cliente recibe un mensaje genérico.

## Estructura del proyecto

```
mapa_eventos/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI, CORS, static, /uploads
│   │   ├── config.py               # Settings (pydantic-settings, lee .env)
│   │   ├── database.py             # Engine y get_db
│   │   ├── limiter.py              # slowapi por IP
│   │   ├── models.py               # SQLAlchemy (sin columnas espaciales)
│   │   ├── schemas.py              # Pydantic
│   │   ├── routers/                # reportes.py, comunas.py
│   │   └── services/               # reporte, comuna, llm, agent, image
│   ├── scripts/
│   │   ├── init_db.sql             # crea todo desde cero (DROP TABLE)
│   │   ├── add_foto_column.sql     # migración posterior
│   │   ├── download_comunas.py     # Overpass (OSM) -> data/comunas_rm.geojson
│   │   └── load_comunas.py         # GeoJSON -> comunas_rm
│   ├── tests/                      # pytest, sin MySQL
│   ├── uploads/                    # fotos subidas (ignorado en git)
│   ├── requirements.txt / requirements-dev.txt
│   ├── pyproject.toml              # ruff + pytest
│   └── .env.example
├── frontend/
│   ├── index.html                  # mapa de reporte + chat con el agente
│   ├── informes_por_comuna.html    # informes guardados (caché en localStorage)
│   ├── css/styles.css
│   ├── js/                         # escape.js, app.js, informes.js
│   └── tests/                      # node --test
└── data/
    └── comunas_rm.geojson
```

## Cambios de esquema

`init_db.sql` hace `DROP TABLE` de todo: no re-ejecutarlo sobre datos reales. Las migraciones posteriores van como scripts SQL sueltos en `backend/scripts/` (ejemplo: `add_foto_column.sql`) y hay que reflejarlas a mano en `models.py` y `schemas.py`.

## Licencia

MIT
