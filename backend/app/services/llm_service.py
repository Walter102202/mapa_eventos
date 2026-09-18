"""Servicio para integración con OpenAI LLM."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from openai import OpenAI
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings

logger = logging.getLogger(__name__)


def get_openai_client() -> OpenAI:
    """Obtener cliente de OpenAI configurado."""
    settings = get_settings()
    return OpenAI(api_key=settings.openai_api_key)


PROMPT_TEMPLATE = """Eres un analista urbano especializado en infraestructura vial. Analiza los siguientes datos sobre baches reportados en la comuna de {nombre_comuna}, Región Metropolitana de Santiago, Chile.

## Datos de la comuna:
- **Nombre:** {nombre_comuna}
- **Total de baches reportados:** {total_baches}

## Top 5 ubicaciones con más reportes:
{top5_table}

## Comentarios recientes de ciudadanos:
{comentarios}

## Tu tarea:
Genera un análisis estructurado en formato JSON con exactamente esta estructura:

{{
  "resumen": "Un resumen de 2-3 párrafos describiendo la situación general de baches en la comuna. Menciona patrones observados, sectores más afectados (si se puede inferir de los comentarios), y la gravedad general de la situación.",
  "top5": [
    {{
      "id": "cluster_1",
      "lat": -33.xxxx,
      "lon": -70.xxxx,
      "num_reportes": N,
      "descripcion": "Descripción breve del lugar basada en los comentarios de usuarios, o 'Ubicación sin descripción específica' si no hay comentarios relevantes."
    }}
  ]
}}

IMPORTANTE:
- El campo "resumen" debe ser un texto fluido y profesional
- Los datos de lat, lon y num_reportes en top5 deben coincidir exactamente con los proporcionados
- Las descripciones deben basarse en los comentarios de usuarios cuando estén disponibles
- Si no hay suficientes datos, indica que se necesitan más reportes para un análisis completo
- Responde SOLO con el JSON, sin texto adicional ni bloques de código markdown
"""


def build_prompt(
    nombre_comuna: str,
    total_baches: int,
    top_clusters: list,
    comentarios: list
) -> str:
    """Construir el prompt para el LLM."""
    # Formatear tabla de top 5
    if top_clusters:
        top5_lines = []
        for c in top_clusters:
            comentarios_cluster = c.get("comentarios", "")[:200]  # Limitar longitud
            top5_lines.append(
                f"- **{c['id']}**: ({c['lat']}, {c['lon']}) - {c['num_reportes']} reportes\n"
                f"  Comentarios: {comentarios_cluster if comentarios_cluster else 'Sin comentarios'}"
            )
        top5_table = "\n".join(top5_lines)
    else:
        top5_table = "No hay suficientes datos para identificar ubicaciones con múltiples reportes."

    # Formatear comentarios
    if comentarios:
        comentarios_text = "\n".join([f"- {c[:150]}" for c in comentarios[:30]])
    else:
        comentarios_text = "No hay comentarios disponibles."

    return PROMPT_TEMPLATE.format(
        nombre_comuna=nombre_comuna,
        total_baches=total_baches,
        top5_table=top5_table,
        comentarios=comentarios_text
    )


def call_openai(prompt: str) -> dict:
    """Llamar a OpenAI y parsear la respuesta JSON."""
    client = get_openai_client()

    response = client.chat.completions.create(
        model="gpt-5.1-2025-11-13",
        messages=[
            {
                "role": "system",
                "content": "Eres un analista urbano experto. Respondes siempre en JSON válido."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.7,
        max_tokens=2000,
        response_format={"type": "json_object"}
    )

    content = response.choices[0].message.content
    return json.loads(content)


def get_cached_resumen(db: Session, codigo_comuna: str, max_age_hours: int = 24) -> Optional[dict]:
    """
    Obtener resumen desde caché si existe y no está expirado.

    Returns:
        Diccionario con resumen_texto, top5_json y generated_at, o None si no hay caché válido
    """
    query = text("""
        SELECT resumen_texto, top5_json, generated_at
        FROM resumen_comuna
        WHERE codigo_comuna = :codigo
            AND generated_at > :min_date
    """)

    min_date = datetime.now() - timedelta(hours=max_age_hours)
    result = db.execute(query, {"codigo": codigo_comuna, "min_date": min_date}).fetchone()

    if result:
        return {
            "resumen_texto": result[0],
            "top5_json": result[1] if isinstance(result[1], list) else json.loads(result[1]) if result[1] else [],
            "generated_at": result[2]
        }
    return None


def save_resumen_to_cache(
    db: Session,
    codigo_comuna: str,
    resumen_texto: str,
    top5_json: list
):
    """Guardar resumen en caché."""
    query = text("""
        INSERT INTO resumen_comuna (codigo_comuna, resumen_texto, top5_json, generated_at)
        VALUES (:codigo, :resumen, :top5, NOW())
        ON DUPLICATE KEY UPDATE
            resumen_texto = :resumen,
            top5_json = :top5,
            generated_at = NOW()
    """)

    db.execute(query, {
        "codigo": codigo_comuna,
        "resumen": resumen_texto,
        "top5": json.dumps(top5_json)
    })
    db.commit()


def generate_resumen(
    db: Session,
    codigo_comuna: str,
    nombre_comuna: str,
    total_baches: int,
    top_clusters: list,
    comentarios: list,
    use_cache: bool = True
) -> dict:
    """
    Generar resumen de baches para una comuna usando LLM.

    Args:
        db: Sesión de base de datos
        codigo_comuna: Código de la comuna
        nombre_comuna: Nombre de la comuna
        total_baches: Total de baches reportados
        top_clusters: Lista de clusters más reportados
        comentarios: Lista de comentarios recientes
        use_cache: Si usar caché (default True)

    Returns:
        Diccionario con resumen, top5, generated_at y from_cache
    """
    # Verificar caché
    if use_cache:
        cached = get_cached_resumen(db, codigo_comuna)
        if cached:
            return {
                "resumen": cached["resumen_texto"],
                "top5": cached["top5_json"],
                "generated_at": cached["generated_at"],
                "from_cache": True
            }

    # Si no hay datos suficientes, retornar mensaje por defecto
    if total_baches == 0:
        return {
            "resumen": f"La comuna de {nombre_comuna} no tiene baches reportados actualmente. "
                      "Esto puede indicar que no se han registrado incidentes o que la comuna "
                      "mantiene sus calles en buen estado.",
            "top5": [],
            "generated_at": datetime.now(),
            "from_cache": False
        }

    # Construir prompt y llamar al LLM
    prompt = build_prompt(nombre_comuna, total_baches, top_clusters, comentarios)

    try:
        llm_response = call_openai(prompt)

        resumen = llm_response.get("resumen", "No se pudo generar el resumen.")
        top5 = llm_response.get("top5", [])

        # Guardar en caché
        save_resumen_to_cache(db, codigo_comuna, resumen, top5)

        return {
            "resumen": resumen,
            "top5": top5,
            "generated_at": datetime.now(),
            "from_cache": False
        }

    except Exception:
        logger.exception("Error generando resumen LLM para comuna %s", codigo_comuna)
        return {
            "resumen": "No se pudo generar el resumen automático en este momento. "
                       f"La comuna de {nombre_comuna} tiene {total_baches} baches reportados.",
            "top5": top_clusters[:5] if top_clusters else [],
            "generated_at": datetime.now(),
            "from_cache": False,
            "error": True
        }
