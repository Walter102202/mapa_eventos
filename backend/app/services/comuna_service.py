"""Servicio para operaciones con comunas."""

from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_all_comunas(db: Session) -> List[dict]:
    """Obtener todas las comunas con conteo de baches."""
    query = text("""
        SELECT
            c.codigo_comuna,
            c.nombre_comuna,
            c.codigo_region,
            COUNT(r.id) AS total_baches
        FROM comunas_rm c
        LEFT JOIN reportes_baches r ON c.codigo_comuna = r.codigo_comuna
        GROUP BY c.codigo_comuna, c.nombre_comuna, c.codigo_region
        ORDER BY c.nombre_comuna
    """)
    result = db.execute(query)
    return [
        {
            "codigo_comuna": row[0],
            "nombre_comuna": row[1],
            "codigo_region": row[2],
            "total_baches": row[3] or 0
        }
        for row in result
    ]


def get_comuna_by_codigo(db: Session, codigo_comuna: str) -> Optional[dict]:
    """Obtener una comuna por su código."""
    query = text("""
        SELECT
            c.codigo_comuna,
            c.nombre_comuna,
            c.codigo_region,
            COUNT(r.id) AS total_baches
        FROM comunas_rm c
        LEFT JOIN reportes_baches r ON c.codigo_comuna = r.codigo_comuna
        WHERE c.codigo_comuna = :codigo
        GROUP BY c.codigo_comuna, c.nombre_comuna, c.codigo_region
    """)
    result = db.execute(query, {"codigo": codigo_comuna}).fetchone()
    if not result:
        return None
    return {
        "codigo_comuna": result[0],
        "nombre_comuna": result[1],
        "codigo_region": result[2],
        "total_baches": result[3] or 0
    }


def find_comuna_for_point(db: Session, lon: float, lat: float) -> Optional[Tuple[str, str]]:
    """
    Encontrar la comuna que contiene un punto dado.

    Args:
        db: Sesión de base de datos
        lon: Longitud del punto
        lat: Latitud del punto

    Returns:
        Tupla (codigo_comuna, nombre_comuna) o None si el punto está fuera de la RM
    """
    query = text("""
        SELECT codigo_comuna, nombre_comuna
        FROM comunas_rm
        WHERE ST_Contains(geom, ST_SRID(POINT(:lon, :lat), 4326))
        LIMIT 1
    """)
    result = db.execute(query, {"lon": lon, "lat": lat}).fetchone()
    if result:
        return (result[0], result[1])
    return None


def get_comunas_geojson(db: Session) -> dict:
    """Obtener todas las comunas como GeoJSON para el frontend."""
    # Sin ORDER BY para evitar error de memoria con geometrías grandes
    # El ordenamiento se hace en Python después
    query = text("""
        SELECT
            c.codigo_comuna,
            c.nombre_comuna,
            COALESCE(b.total_baches, 0) AS total_baches,
            ST_AsGeoJSON(c.geom) AS geom_json
        FROM comunas_rm c
        LEFT JOIN (
            SELECT codigo_comuna, COUNT(*) AS total_baches
            FROM reportes_baches
            GROUP BY codigo_comuna
        ) b ON c.codigo_comuna = b.codigo_comuna
    """)
    result = db.execute(query)

    import json
    features = []
    for row in result:
        geom = json.loads(row[3]) if row[3] else None
        if geom:
            features.append({
                "type": "Feature",
                "properties": {
                    "codigo_comuna": row[0],
                    "nombre_comuna": row[1],
                    "total_baches": row[2] or 0
                },
                "geometry": geom
            })

    # Ordenar en Python (evita error de memoria en MySQL)
    features.sort(key=lambda f: f["properties"]["nombre_comuna"])

    return {
        "type": "FeatureCollection",
        "features": features
    }
