"""Router para endpoints de comunas."""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..limiter import limiter
from ..schemas import (
    BachesListResponse,
    ComunaListResponse,
    ComunaResponse,
    ErrorResponse,
    ReporteResponse,
    ResumenComunaResponse,
    TopBacheCluster,
)
from ..services import agent_service, comuna_service, llm_service, reporte_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/comunas", tags=["comunas"])


# Schema para el prompt del agente
class AgentPromptRequest(BaseModel):
    prompt: str
    codigo_comuna: Optional[str] = None


@router.get("", response_model=ComunaListResponse)
def listar_comunas(db: Session = Depends(get_db)):
    """
    Listar todas las comunas de la Región Metropolitana.

    Retorna cada comuna con su código, nombre y cantidad de baches reportados.
    """
    comunas = comuna_service.get_all_comunas(db)
    return ComunaListResponse(
        comunas=[ComunaResponse(**c) for c in comunas],
        total=len(comunas)
    )


@router.get("/geojson")
def get_comunas_geojson(db: Session = Depends(get_db)):
    """
    Obtener todas las comunas en formato GeoJSON.

    Útil para renderizar los polígonos de comunas en el mapa.
    """
    return comuna_service.get_comunas_geojson(db)


@router.get("/informes")
def listar_informes(db: Session = Depends(get_db)):
    """
    Listar todas las comunas con información sobre si tienen informe generado.
    Optimizado: sin COUNT para mejor rendimiento.
    """
    from sqlalchemy import text

    # Query simplificada sin COUNT (más rápida)
    query = text("""
        SELECT
            c.codigo_comuna,
            c.nombre_comuna,
            rc.generated_at as fecha_informe
        FROM comunas_rm c
        LEFT JOIN resumen_comuna rc ON c.codigo_comuna = rc.codigo_comuna
        ORDER BY c.nombre_comuna
    """)

    result = db.execute(query)

    comunas = []
    for row in result:
        comunas.append({
            "c": row[0],  # codigo_comuna (abreviado para reducir payload)
            "n": row[1],  # nombre_comuna
            "f": row[2].isoformat() if row[2] else None  # fecha_informe
        })

    return {"comunas": comunas}


@router.get(
    "/{codigo_comuna}",
    response_model=ComunaResponse,
    responses={404: {"model": ErrorResponse}}
)
def get_comuna(codigo_comuna: str, db: Session = Depends(get_db)):
    """
    Obtener información de una comuna específica.

    - **codigo_comuna**: Código oficial de la comuna (ej: "13101" para Santiago)
    """
    comuna = comuna_service.get_comuna_by_codigo(db, codigo_comuna)
    if not comuna:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comuna con código '{codigo_comuna}' no encontrada"
        )
    return ComunaResponse(**comuna)


@router.get(
    "/{codigo_comuna}/baches",
    response_model=BachesListResponse,
    responses={404: {"model": ErrorResponse}}
)
def get_baches_por_comuna(
    codigo_comuna: str,
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(50, ge=1, le=200, description="Tamaño de página"),
    db: Session = Depends(get_db)
):
    """
    Obtener todos los baches reportados en una comuna.

    Los resultados están paginados y ordenados por fecha de creación (más recientes primero).

    - **codigo_comuna**: Código oficial de la comuna
    - **page**: Número de página (desde 1)
    - **page_size**: Cantidad de resultados por página (máx 200)
    """
    # Verificar que la comuna existe
    comuna = comuna_service.get_comuna_by_codigo(db, codigo_comuna)
    if not comuna:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comuna con código '{codigo_comuna}' no encontrada"
        )

    # Obtener baches
    resultado = reporte_service.get_baches_por_comuna(db, codigo_comuna, page, page_size)

    return BachesListResponse(
        codigo_comuna=codigo_comuna,
        nombre_comuna=comuna["nombre_comuna"],
        baches=[ReporteResponse(**b) for b in resultado["baches"]],
        total=resultado["total"],
        page=resultado["page"],
        page_size=resultado["page_size"]
    )


@router.get(
    "/{codigo_comuna}/resumen",
    response_model=ResumenComunaResponse,
    responses={
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        429: {"description": "Demasiadas solicitudes"},
    }
)
@limiter.limit(get_settings().rate_limit_ia)
def get_resumen_comuna(
    request: Request,
    codigo_comuna: str,
    refresh: bool = Query(False, description="Regenerar el resumen ignorando caché (requiere X-Admin-Token)"),
    x_admin_token: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    Obtener resumen generado por IA de los baches en una comuna.

    El resumen incluye:
    - Análisis textual de la situación de baches
    - Top 5 ubicaciones con más reportes
    - Descripción de cada ubicación basada en comentarios de usuarios

    Los resúmenes se cachean por 24 horas para optimizar costos.
    Use `refresh=true` para forzar una nueva generación (requiere header `X-Admin-Token`).

    - **codigo_comuna**: Código oficial de la comuna
    - **refresh**: Si true, regenera el resumen ignorando la caché
    """
    # refresh=true dispara una llamada a OpenAI: solo con token de administrador
    if refresh:
        admin_token = get_settings().admin_token
        if not admin_token or x_admin_token != admin_token:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="refresh=true requiere el header X-Admin-Token",
            )

    # Verificar que la comuna existe
    comuna = comuna_service.get_comuna_by_codigo(db, codigo_comuna)
    if not comuna:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comuna con código '{codigo_comuna}' no encontrada"
        )

    # Obtener datos para el resumen
    total_baches = comuna["total_baches"]
    top_clusters = reporte_service.get_top_clusters_por_comuna(db, codigo_comuna)
    comentarios = reporte_service.get_comentarios_recientes(db, codigo_comuna)

    # Generar resumen
    resumen_data = llm_service.generate_resumen(
        db=db,
        codigo_comuna=codigo_comuna,
        nombre_comuna=comuna["nombre_comuna"],
        total_baches=total_baches,
        top_clusters=top_clusters,
        comentarios=comentarios,
        use_cache=not refresh
    )

    # Convertir top5 al formato esperado
    top5 = []
    for item in resumen_data.get("top5", []):
        top5.append(TopBacheCluster(
            id=item.get("id", ""),
            lat=item.get("lat", 0),
            lon=item.get("lon", 0),
            num_reportes=item.get("num_reportes", 0),
            descripcion=item.get("descripcion", "")
        ))

    return ResumenComunaResponse(
        codigo_comuna=codigo_comuna,
        nombre_comuna=comuna["nombre_comuna"],
        total_baches=total_baches,
        resumen=resumen_data.get("resumen", ""),
        top5=top5,
        generated_at=resumen_data.get("generated_at", datetime.now()),
        from_cache=resumen_data.get("from_cache", False)
    )


@router.post("/agente", responses={429: {"description": "Demasiadas solicitudes"}})
@limiter.limit(get_settings().rate_limit_ia)
def consultar_agente(
    request: Request,
    body: AgentPromptRequest,
    db: Session = Depends(get_db)
):
    """
    Consultar al agente IA con un prompt en lenguaje natural.

    El agente puede:
    - Obtener datos de baches de cualquier comuna
    - Generar resúmenes personalizados
    - Buscar baches por dirección
    - Analizar estadísticas y patrones

    Ejemplos de prompts:
    - "Hazme un resumen de los baches de Ñuñoa"
    - "¿Cuáles son las calles con más baches en Providencia?"
    - "Busca baches en Avenida Irarrázaval"
    - "¿Qué comuna tiene más baches de severidad alta?"
    """
    if not body.prompt or len(body.prompt.strip()) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El prompt debe tener al menos 3 caracteres"
        )

    try:
        result = agent_service.run_agent(
            db=db,
            user_prompt=body.prompt,
            selected_comuna=body.codigo_comuna
        )

        return {
            "respuesta": result.get("respuesta", ""),
            "generated_at": result.get("generated_at", datetime.now()).isoformat(),
            "iterations": result.get("iterations", 0)
        }

    except Exception:
        logger.exception("Error al ejecutar el agente para prompt=%r comuna=%r", body.prompt[:80], body.codigo_comuna)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al procesar la consulta. Intente nuevamente más tarde.",
        ) from None


@router.get("/{codigo_comuna}/informe")
def get_informe_comuna(
    codigo_comuna: str,
    db: Session = Depends(get_db)
):
    """
    Obtener el informe guardado de una comuna.

    Retorna el resumen, top5 y fecha de generación si existe.
    """
    import json

    from sqlalchemy import text

    # Verificar que la comuna existe
    comuna = comuna_service.get_comuna_by_codigo(db, codigo_comuna)
    if not comuna:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comuna con código '{codigo_comuna}' no encontrada"
        )

    # Obtener informe guardado
    query = text("""
        SELECT resumen_texto, top5_json, generated_at
        FROM resumen_comuna
        WHERE codigo_comuna = :codigo
    """)

    result = db.execute(query, {"codigo": codigo_comuna}).fetchone()

    if not result or not result[0]:
        return {
            "codigo_comuna": codigo_comuna,
            "nombre_comuna": comuna["nombre_comuna"],
            "total_baches": comuna["total_baches"],
            "tiene_informe": False,
            "resumen": None,
            "top5": [],
            "generated_at": None
        }

    # Parsear top5_json
    top5 = []
    if result[1]:
        try:
            top5 = json.loads(result[1]) if isinstance(result[1], str) else result[1]
        except (ValueError, TypeError):
            pass

    return {
        "codigo_comuna": codigo_comuna,
        "nombre_comuna": comuna["nombre_comuna"],
        "total_baches": comuna["total_baches"],
        "tiene_informe": True,
        "resumen": result[0],
        "top5": top5,
        "generated_at": result[2].isoformat() if result[2] else None
    }
