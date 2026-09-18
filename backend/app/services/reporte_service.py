"""Servicio para operaciones con reportes de baches."""

from typing import List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..schemas import ReporteCreate
from .comuna_service import find_comuna_for_point


def crear_reporte(
    db: Session,
    reporte: ReporteCreate,
    foto_url: Optional[str] = None
) -> Optional[dict]:
    """
    Crear un nuevo reporte de bache.

    Args:
        db: Sesión de base de datos
        reporte: Datos del reporte
        foto_url: URL de la foto del bache (opcional)

    Returns:
        Diccionario con id, codigo_comuna y nombre_comuna, o None si está fuera de RM
    """
    # Encontrar la comuna para el punto
    comuna_info = find_comuna_for_point(db, reporte.lon, reporte.lat)

    if not comuna_info:
        return None  # Punto fuera de la Región Metropolitana

    codigo_comuna, nombre_comuna = comuna_info

    # Insertar el reporte
    query = text("""
        INSERT INTO reportes_baches (lat, lon, punto, codigo_comuna, direccion, comentario, severidad, foto_url)
        VALUES (
            :lat,
            :lon,
            ST_SRID(POINT(:lon, :lat), 4326),
            :codigo_comuna,
            :direccion,
            :comentario,
            :severidad,
            :foto_url
        )
    """)

    db.execute(query, {
        "lat": reporte.lat,
        "lon": reporte.lon,
        "codigo_comuna": codigo_comuna,
        "direccion": reporte.direccion,
        "comentario": reporte.comentario,
        "severidad": reporte.severidad.value,
        "foto_url": foto_url
    })
    db.commit()

    # Obtener el ID del reporte insertado
    result = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()
    reporte_id = result[0]

    return {
        "id": reporte_id,
        "codigo_comuna": codigo_comuna,
        "nombre_comuna": nombre_comuna
    }


def get_baches_por_comuna(
    db: Session,
    codigo_comuna: str,
    page: int = 1,
    page_size: int = 50
) -> dict:
    """
    Obtener baches de una comuna con paginación.

    Args:
        db: Sesión de base de datos
        codigo_comuna: Código de la comuna
        page: Número de página (1-indexed)
        page_size: Tamaño de página

    Returns:
        Diccionario con baches y metadatos de paginación
    """
    offset = (page - 1) * page_size

    # Contar total
    count_query = text("""
        SELECT COUNT(*) FROM reportes_baches WHERE codigo_comuna = :codigo
    """)
    total = db.execute(count_query, {"codigo": codigo_comuna}).scalar()

    # Obtener baches
    query = text("""
        SELECT id, lat, lon, direccion, comentario, severidad, foto_url, created_at
        FROM reportes_baches
        WHERE codigo_comuna = :codigo
        ORDER BY created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    result = db.execute(query, {
        "codigo": codigo_comuna,
        "limit": page_size,
        "offset": offset
    })

    baches = [
        {
            "id": row[0],
            "lat": row[1],
            "lon": row[2],
            "codigo_comuna": codigo_comuna,
            "direccion": row[3],
            "comentario": row[4],
            "severidad": row[5],
            "foto_url": row[6],
            "created_at": row[7]
        }
        for row in result
    ]

    return {
        "baches": baches,
        "total": total,
        "page": page,
        "page_size": page_size
    }


def get_top_clusters_por_comuna(
    db: Session,
    codigo_comuna: str,
    limit: int = 5
) -> List[dict]:
    """
    Obtener los clusters de baches más reportados en una comuna.

    Agrupa por coordenadas redondeadas a 4 decimales (~11 metros).

    Returns:
        Lista de clusters con coordenadas, número de reportes y comentarios
    """
    query = text("""
        SELECT
            ROUND(lat, 4) AS lat_grupo,
            ROUND(lon, 4) AS lon_grupo,
            COUNT(*) AS num_reportes,
            GROUP_CONCAT(
                CASE WHEN comentario IS NOT NULL AND comentario != ''
                THEN comentario ELSE NULL END
                SEPARATOR ' | '
            ) AS comentarios
        FROM reportes_baches
        WHERE codigo_comuna = :codigo
        GROUP BY lat_grupo, lon_grupo
        ORDER BY num_reportes DESC
        LIMIT :limit
    """)

    result = db.execute(query, {"codigo": codigo_comuna, "limit": limit})

    clusters = []
    for i, row in enumerate(result):
        clusters.append({
            "id": f"cluster_{i + 1}",
            "lat": float(row[0]),
            "lon": float(row[1]),
            "num_reportes": row[2],
            "comentarios": row[3] or ""
        })

    return clusters


def get_comentarios_recientes(
    db: Session,
    codigo_comuna: str,
    limit: int = 50
) -> List[str]:
    """Obtener los comentarios más recientes de una comuna."""
    query = text("""
        SELECT comentario
        FROM reportes_baches
        WHERE codigo_comuna = :codigo
            AND comentario IS NOT NULL
            AND comentario != ''
        ORDER BY created_at DESC
        LIMIT :limit
    """)

    result = db.execute(query, {"codigo": codigo_comuna, "limit": limit})
    return [row[0] for row in result]


def get_estadisticas_comuna(db: Session, codigo_comuna: str) -> dict:
    """Obtener estadísticas de baches para una comuna."""
    query = text("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN severidad = 'alta' THEN 1 ELSE 0 END) AS alta,
            SUM(CASE WHEN severidad = 'media' THEN 1 ELSE 0 END) AS media,
            SUM(CASE WHEN severidad = 'baja' THEN 1 ELSE 0 END) AS baja
        FROM reportes_baches
        WHERE codigo_comuna = :codigo
    """)

    result = db.execute(query, {"codigo": codigo_comuna}).fetchone()

    return {
        "total": result[0] or 0,
        "por_severidad": {
            "alta": result[1] or 0,
            "media": result[2] or 0,
            "baja": result[3] or 0
        }
    }
