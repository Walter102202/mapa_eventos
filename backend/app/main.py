"""
MVP Reportes de Baches - Región Metropolitana de Santiago

API REST para reportar y consultar baches en las comunas de la RM.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routers import comunas, reportes

settings = get_settings()

app = FastAPI(
    title="API Reportes de Baches - Región Metropolitana",
    description="""
API para el reporte y consulta de baches en las calles de la Región Metropolitana de Santiago, Chile.

## Funcionalidades

* **Reportar baches**: Los usuarios pueden reportar baches indicando ubicación y severidad
* **Consultar por comuna**: Ver todos los baches reportados en una comuna específica
* **Resúmenes IA**: Obtener análisis automáticos generados por IA sobre la situación de cada comuna

## Datos geográficos

La API utiliza capacidades espaciales de MySQL para:
- Determinar automáticamente la comuna de cada reporte
- Agrupar reportes por ubicación (clustering)
- Validar que los reportes estén dentro de la Región Metropolitana
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configurar CORS para permitir acceso desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registrar routers
app.include_router(reportes.router)
app.include_router(comunas.router)

# Servir archivos estáticos del frontend
frontend_path = Path(__file__).parent.parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        """Servir la página principal del frontend (Reportar Baches)."""
        return FileResponse(str(frontend_path / "index.html"))

    @app.get("/informes", include_in_schema=False)
    async def serve_informes():
        """Servir la página de Informes por Comuna."""
        return FileResponse(str(frontend_path / "informes_por_comuna.html"))

# Servir imágenes subidas
uploads_path = Path(__file__).parent.parent / "uploads"
uploads_path.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")


@app.get("/api/health", tags=["sistema"])
def health_check():
    """Verificar el estado de la API."""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/api/info", tags=["sistema"])
def api_info():
    """Obtener información sobre la API."""
    return {
        "nombre": "API Reportes de Baches",
        "version": "1.0.0",
        "region": "Región Metropolitana de Santiago",
        "descripcion": "API para reportar y consultar baches en las calles de la RM",
        "endpoints": {
            "reportes": {
                "POST /api/reportes": "Crear un nuevo reporte de bache"
            },
            "comunas": {
                "GET /api/comunas": "Listar todas las comunas",
                "GET /api/comunas/{codigo}/baches": "Obtener baches de una comuna",
                "GET /api/comunas/{codigo}/resumen": "Obtener resumen IA de una comuna"
            }
        }
    }
