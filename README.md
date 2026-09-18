# MVP Reportes de Baches - Región Metropolitana de Santiago

Aplicación web para reportar y consultar baches en las calles de la Región Metropolitana de Santiago, Chile.

## Características

- **Reportar baches**: Los usuarios pueden reportar baches indicando ubicación y severidad
- **Detección automática de comuna**: El sistema determina la comuna usando MySQL espacial
- **Consulta por comuna**: Ver todos los baches reportados en una comuna
- **Resúmenes IA**: Análisis automáticos generados por OpenAI sobre la situación de cada comuna
- **Mapa interactivo**: Interfaz con Leaflet.js para visualizar y reportar baches

## Stack Tecnológico

- **Backend**: Python + FastAPI
- **Base de datos**: MySQL 8.x con soporte espacial
- **LLM**: OpenAI GPT-4
- **Frontend**: HTML/CSS/JavaScript + Leaflet.js

## Requisitos

- Python 3.9+
- MySQL 8.0+
- API Key de OpenAI

## Instalación

### 1. Clonar el repositorio

```bash
cd mapa_eventos
```

### 2. Crear entorno virtual e instalar dependencias

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Editar `.env` con tus credenciales:

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=tu_password
MYSQL_DATABASE=baches_rm

OPENAI_API_KEY=sk-tu-api-key
```

### 4. Crear base de datos

```bash
mysql -u root -p < scripts/init_db.sql
```

### 5. Obtener datos de comunas

Opción A: Descargar desde OpenStreetMap (automático):

```bash
python scripts/download_comunas.py
```

Opción B: Descargar manualmente desde [BCN Chile](https://www.bcn.cl/siit/mapas_vectoriales):
- Descargar "División Comunal"
- Convertir a GeoJSON
- Guardar como `data/comunas_rm.geojson`

### 6. Cargar comunas en MySQL

```bash
python scripts/load_comunas.py
```

### 7. Ejecutar la aplicación

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Desarrollo

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest              # tests (no requieren MySQL)
python -m pytest tests/test_reportes.py::test_crear_reporte_ok_devuelve_201   # un test
ruff check .                  # lint
ruff check . --fix            # autofix (imports, etc.)
```

## Uso

### Acceder a la aplicación

- **Frontend**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Endpoints API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/reportes` | Crear un nuevo reporte de bache |
| GET | `/api/comunas` | Listar todas las comunas |
| GET | `/api/comunas/geojson` | Obtener comunas en formato GeoJSON |
| GET | `/api/comunas/{codigo}/baches` | Obtener baches de una comuna |
| GET | `/api/comunas/{codigo}/resumen` | Obtener resumen IA de una comuna |

### Ejemplo: Crear reporte

```bash
curl -X POST http://localhost:8000/api/reportes \
  -H "Content-Type: application/json" \
  -d '{
    "lat": -33.4489,
    "lon": -70.6693,
    "comentario": "Bache grande en la esquina",
    "severidad": "alta"
  }'
```

### Ejemplo: Obtener resumen IA

```bash
curl http://localhost:8000/api/comunas/13101/resumen
```

## Estructura del Proyecto

```
mapa_eventos/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app
│   │   ├── config.py            # Configuración
│   │   ├── database.py          # Conexión MySQL
│   │   ├── models.py            # Modelos SQLAlchemy
│   │   ├── schemas.py           # Schemas Pydantic
│   │   ├── services/            # Lógica de negocio
│   │   └── routers/             # Endpoints API
│   ├── scripts/
│   │   ├── init_db.sql          # Script de creación de BD
│   │   ├── load_comunas.py      # Carga de datos GIS
│   │   └── download_comunas.py  # Descarga de datos OSM
│   ├── tests/                   # pytest, sin MySQL (get_db mockeado)
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pyproject.toml           # config ruff + pytest
│   └── .env.example
├── frontend/
│   ├── index.html
│   ├── css/styles.css
│   └── js/app.js
├── data/
│   └── comunas_rm.geojson       # Datos GIS
└── README.md
```

## Notas Técnicas

- **SRID 4326**: Todas las geometrías usan WGS84 (EPSG:4326)
- **Clustering**: Los baches se agrupan por coordenadas redondeadas a 4 decimales (~11m)
- **Caché LLM**: Los resúmenes se cachean 24 horas para optimizar costos
- **Solo RM**: El sistema solo acepta reportes dentro de la Región Metropolitana

## Códigos de comunas de la RM

Algunos códigos de comunas de ejemplo:
- 13101: Santiago
- 13102: Cerrillos
- 13103: Cerro Navia
- 13104: Conchalí
- 13105: El Bosque
- 13106: Estación Central
- 13107: Huechuraba
- 13108: Independencia
- 13109: La Cisterna
- 13110: La Florida
- 13111: La Granja
- 13112: La Pintana
- 13113: La Reina
- 13114: Las Condes
- 13115: Lo Barnechea
- 13116: Lo Espejo
- 13117: Lo Prado
- 13118: Macul
- 13119: Maipú
- 13120: Ñuñoa
- 13121: Pedro Aguirre Cerda
- 13122: Peñalolén
- 13123: Providencia
- 13124: Pudahuel
- 13125: Quilicura
- 13126: Quinta Normal
- 13127: Recoleta
- 13128: Renca
- 13129: San Joaquín
- 13130: San Miguel
- 13131: San Ramón
- 13132: Vitacura

## Licencia

MIT
