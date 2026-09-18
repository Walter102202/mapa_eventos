"""Servicio de Agente IA con herramientas para consultar datos de baches."""

import json
from datetime import datetime
from typing import Optional

from openai import OpenAI
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings


def get_openai_client() -> OpenAI:
    """Obtener cliente de OpenAI configurado."""
    settings = get_settings()
    return OpenAI(api_key=settings.openai_api_key)


# Definición de herramientas disponibles para el agente
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "obtener_baches_comuna",
            "description": "Obtiene la lista de baches reportados en una comuna específica. Incluye dirección, severidad, coordenadas y comentarios.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre_comuna": {
                        "type": "string",
                        "description": "Nombre de la comuna (ej: 'Ñuñoa', 'Santiago', 'Providencia')"
                    },
                    "limite": {
                        "type": "integer",
                        "description": "Número máximo de baches a retornar (default: 100)",
                        "default": 100
                    }
                },
                "required": ["nombre_comuna"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_estadisticas_comuna",
            "description": "Obtiene estadísticas resumidas de una comuna: total de baches, cantidad por severidad, y fecha del último reporte.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre_comuna": {
                        "type": "string",
                        "description": "Nombre de la comuna"
                    }
                },
                "required": ["nombre_comuna"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "obtener_top_ubicaciones",
            "description": "Obtiene las ubicaciones con más baches reportados en una comuna, agrupadas por cercanía geográfica.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nombre_comuna": {
                        "type": "string",
                        "description": "Nombre de la comuna"
                    },
                    "limite": {
                        "type": "integer",
                        "description": "Número de ubicaciones a retornar (default: 10)",
                        "default": 10
                    }
                },
                "required": ["nombre_comuna"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "listar_comunas",
            "description": "Lista todas las comunas disponibles en la Región Metropolitana con su cantidad de baches.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_baches_por_direccion",
            "description": "Busca baches que contengan una dirección o calle específica en su descripción.",
            "parameters": {
                "type": "object",
                "properties": {
                    "texto_busqueda": {
                        "type": "string",
                        "description": "Texto a buscar en las direcciones (ej: 'Irarrázaval', 'Moneda')"
                    },
                    "nombre_comuna": {
                        "type": "string",
                        "description": "Opcional: filtrar por comuna específica"
                    }
                },
                "required": ["texto_busqueda"]
            }
        }
    }
]


# ==================== FUNCIONES DE HERRAMIENTAS ====================

def _get_codigo_comuna(db: Session, nombre_comuna: str) -> Optional[str]:
    """Obtener código de comuna a partir del nombre (búsqueda flexible)."""
    query = text("""
        SELECT codigo_comuna FROM comunas_rm
        WHERE LOWER(nombre_comuna) LIKE LOWER(:nombre)
        LIMIT 1
    """)
    result = db.execute(query, {"nombre": f"%{nombre_comuna}%"}).fetchone()
    return result[0] if result else None


def tool_obtener_baches_comuna(db: Session, nombre_comuna: str, limite: int = 100) -> dict:
    """Obtener baches de una comuna."""
    codigo = _get_codigo_comuna(db, nombre_comuna)
    if not codigo:
        return {"error": f"Comuna '{nombre_comuna}' no encontrada"}

    query = text("""
        SELECT
            r.id, r.lat, r.lon, r.direccion, r.severidad, r.comentario, r.created_at,
            c.nombre_comuna
        FROM reportes_baches r
        JOIN comunas_rm c ON r.codigo_comuna = c.codigo_comuna
        WHERE r.codigo_comuna = :codigo
        ORDER BY r.created_at DESC
        LIMIT :limite
    """)

    result = db.execute(query, {"codigo": codigo, "limite": limite})

    baches = []
    for row in result:
        baches.append({
            "id": row[0],
            "lat": row[1],
            "lon": row[2],
            "direccion": row[3] or "Sin dirección registrada",
            "severidad": row[4],
            "comentario": row[5] or "",
            "fecha": row[6].strftime("%Y-%m-%d %H:%M") if row[6] else "",
            "comuna": row[7]
        })

    return {
        "comuna": nombre_comuna,
        "total_encontrados": len(baches),
        "baches": baches
    }


def tool_obtener_estadisticas_comuna(db: Session, nombre_comuna: str) -> dict:
    """Obtener estadísticas de una comuna."""
    codigo = _get_codigo_comuna(db, nombre_comuna)
    if not codigo:
        return {"error": f"Comuna '{nombre_comuna}' no encontrada"}

    query = text("""
        SELECT
            c.nombre_comuna,
            COUNT(r.id) as total,
            SUM(CASE WHEN r.severidad = 'alta' THEN 1 ELSE 0 END) as alta,
            SUM(CASE WHEN r.severidad = 'media' THEN 1 ELSE 0 END) as media,
            SUM(CASE WHEN r.severidad = 'baja' THEN 1 ELSE 0 END) as baja,
            MAX(r.created_at) as ultimo_reporte
        FROM comunas_rm c
        LEFT JOIN reportes_baches r ON c.codigo_comuna = r.codigo_comuna
        WHERE c.codigo_comuna = :codigo
        GROUP BY c.codigo_comuna, c.nombre_comuna
    """)

    result = db.execute(query, {"codigo": codigo}).fetchone()

    return {
        "comuna": result[0],
        "total_baches": result[1] or 0,
        "por_severidad": {
            "alta": result[2] or 0,
            "media": result[3] or 0,
            "baja": result[4] or 0
        },
        "ultimo_reporte": result[5].strftime("%Y-%m-%d %H:%M") if result[5] else "Sin reportes"
    }


def tool_obtener_top_ubicaciones(db: Session, nombre_comuna: str, limite: int = 10) -> dict:
    """Obtener ubicaciones con más baches."""
    codigo = _get_codigo_comuna(db, nombre_comuna)
    if not codigo:
        return {"error": f"Comuna '{nombre_comuna}' no encontrada"}

    query = text("""
        SELECT
            ROUND(lat, 4) as lat_grupo,
            ROUND(lon, 4) as lon_grupo,
            COUNT(*) as num_reportes,
            GROUP_CONCAT(DISTINCT direccion SEPARATOR ' | ') as direcciones,
            GROUP_CONCAT(DISTINCT severidad SEPARATOR ', ') as severidades,
            GROUP_CONCAT(
                CASE WHEN comentario IS NOT NULL AND comentario != ''
                THEN comentario ELSE NULL END
                SEPARATOR ' | '
            ) as comentarios
        FROM reportes_baches
        WHERE codigo_comuna = :codigo
        GROUP BY lat_grupo, lon_grupo
        ORDER BY num_reportes DESC
        LIMIT :limite
    """)

    result = db.execute(query, {"codigo": codigo, "limite": limite})

    ubicaciones = []
    for i, row in enumerate(result, 1):
        ubicaciones.append({
            "ranking": i,
            "lat": float(row[0]),
            "lon": float(row[1]),
            "num_reportes": row[2],
            "direcciones": row[3] or "Sin dirección específica",
            "severidades": row[4],
            "comentarios": (row[5] or "")[:300]  # Limitar longitud
        })

    return {
        "comuna": nombre_comuna,
        "top_ubicaciones": ubicaciones
    }


def tool_listar_comunas(db: Session) -> dict:
    """Listar todas las comunas."""
    query = text("""
        SELECT
            c.nombre_comuna,
            COUNT(r.id) as total_baches
        FROM comunas_rm c
        LEFT JOIN reportes_baches r ON c.codigo_comuna = r.codigo_comuna
        GROUP BY c.codigo_comuna, c.nombre_comuna
        ORDER BY total_baches DESC
    """)

    result = db.execute(query)

    comunas = [{"nombre": row[0], "total_baches": row[1] or 0} for row in result]

    return {
        "total_comunas": len(comunas),
        "comunas": comunas
    }


def tool_buscar_baches_por_direccion(db: Session, texto_busqueda: str, nombre_comuna: str = None) -> dict:
    """Buscar baches por texto en dirección."""
    params = {"texto": f"%{texto_busqueda}%"}

    where_clause = "WHERE (r.direccion LIKE :texto OR r.comentario LIKE :texto)"

    if nombre_comuna:
        codigo = _get_codigo_comuna(db, nombre_comuna)
        if codigo:
            where_clause += " AND r.codigo_comuna = :codigo"
            params["codigo"] = codigo

    query = text(f"""
        SELECT
            r.id, r.lat, r.lon, r.direccion, r.severidad, r.comentario,
            r.created_at, c.nombre_comuna
        FROM reportes_baches r
        JOIN comunas_rm c ON r.codigo_comuna = c.codigo_comuna
        {where_clause}
        ORDER BY r.created_at DESC
        LIMIT 50
    """)

    result = db.execute(query, params)

    baches = []
    for row in result:
        baches.append({
            "id": row[0],
            "lat": row[1],
            "lon": row[2],
            "direccion": row[3] or "Sin dirección",
            "severidad": row[4],
            "comentario": row[5] or "",
            "fecha": row[6].strftime("%Y-%m-%d") if row[6] else "",
            "comuna": row[7]
        })

    return {
        "busqueda": texto_busqueda,
        "filtro_comuna": nombre_comuna,
        "total_encontrados": len(baches),
        "baches": baches
    }


# ==================== EJECUTOR DE HERRAMIENTAS ====================

def execute_tool(db: Session, tool_name: str, arguments: dict) -> str:
    """Ejecutar una herramienta y retornar el resultado como JSON."""

    tool_functions = {
        "obtener_baches_comuna": lambda: tool_obtener_baches_comuna(
            db,
            arguments.get("nombre_comuna"),
            arguments.get("limite", 100)
        ),
        "obtener_estadisticas_comuna": lambda: tool_obtener_estadisticas_comuna(
            db,
            arguments.get("nombre_comuna")
        ),
        "obtener_top_ubicaciones": lambda: tool_obtener_top_ubicaciones(
            db,
            arguments.get("nombre_comuna"),
            arguments.get("limite", 10)
        ),
        "listar_comunas": lambda: tool_listar_comunas(db),
        "buscar_baches_por_direccion": lambda: tool_buscar_baches_por_direccion(
            db,
            arguments.get("texto_busqueda"),
            arguments.get("nombre_comuna")
        )
    }

    if tool_name in tool_functions:
        result = tool_functions[tool_name]()
        return json.dumps(result, ensure_ascii=False, default=str)

    return json.dumps({"error": f"Herramienta '{tool_name}' no encontrada"})


# ==================== AGENTE PRINCIPAL ====================

SYSTEM_PROMPT = """Eres un asistente experto en análisis de datos urbanos, especializado en el estado de las calles y baches de la Región Metropolitana de Santiago, Chile.

Tu trabajo es ayudar a los usuarios a entender la situación de los baches en diferentes comunas, utilizando las herramientas disponibles para consultar datos reales.

## Instrucciones:
1. Usa las herramientas disponibles para obtener datos actualizados antes de responder
2. Si el usuario pide un resumen de una comuna, SIEMPRE ejecuta estas herramientas en orden:
   a) obtener_estadisticas_comuna - para tener el total y severidades
   b) obtener_top_ubicaciones - para identificar las zonas más afectadas
   c) obtener_baches_comuna (opcional) - si necesitas más detalles
3. Proporciona información útil para ciudadanos y autoridades municipales
4. Destaca las zonas más problemáticas y los patrones que observes
5. Sé conciso pero informativo
6. Si no encuentras datos, indícalo claramente

## IMPORTANTE - Formato de respuesta:
- NUNCA incluyas coordenadas (latitud/longitud) en tu respuesta - los usuarios no las necesitan
- Usa SOLO nombres de calles, direcciones y barrios
- Organiza la información con secciones claras usando ## para títulos
- Usa viñetas (-) para listar información
- Incluye datos numéricos: total de baches, cantidad por severidad
- Menciona direcciones específicas cuando estén disponibles
- Indica la severidad de los baches (alta, media, baja)
- Si una dirección no está disponible, describe la zona o indica "sin dirección registrada"

## Estructura sugerida para resúmenes de comuna:
1. Resumen general (total baches, situación)
2. Distribución por severidad
3. Calles/zonas más afectadas (con direcciones cuando las haya)
4. Observaciones o recomendaciones
"""


def save_agent_response_to_cache(db: Session, codigo_comuna: str, respuesta: str, top5_data: list = None):
    """Guardar respuesta del agente en caché."""
    top5_json = json.dumps(top5_data or [], ensure_ascii=False)

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
        "resumen": respuesta,
        "top5": top5_json
    })
    db.commit()


def run_agent(db: Session, user_prompt: str, selected_comuna: str = None) -> dict:
    """
    Ejecutar el agente con el prompt del usuario.

    Args:
        db: Sesión de base de datos
        user_prompt: Prompt del usuario
        selected_comuna: Comuna seleccionada actualmente (contexto adicional)

    Returns:
        Diccionario con la respuesta del agente y metadata
    """
    client = get_openai_client()

    # Agregar contexto de comuna seleccionada si existe
    context = ""
    if selected_comuna:
        context = f"\n\n[Contexto: El usuario tiene seleccionada la comuna con código '{selected_comuna}']"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt + context}
    ]

    # Límite de iteraciones para evitar loops infinitos
    max_iterations = 5
    iteration = 0
    detected_comuna_codigo = None  # Para guardar en caché
    captured_top5 = None  # Para guardar top5 en caché

    while iteration < max_iterations:
        iteration += 1

        # Llamar al modelo
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=2000
        )

        assistant_message = response.choices[0].message

        # Si no hay tool calls, tenemos la respuesta final
        if not assistant_message.tool_calls:
            respuesta = assistant_message.content

            # Guardar en caché si tenemos una comuna identificada
            codigo_para_cache = detected_comuna_codigo or selected_comuna
            if codigo_para_cache and respuesta:
                try:
                    save_agent_response_to_cache(db, codigo_para_cache, respuesta, captured_top5)
                except Exception as e:
                    print(f"Error guardando en caché: {e}")

            return {
                "respuesta": respuesta,
                "generated_at": datetime.now(),
                "iterations": iteration,
                "cached_for_comuna": codigo_para_cache,
                "top5": captured_top5
            }

        # Agregar mensaje del asistente con tool calls
        messages.append({
            "role": "assistant",
            "content": assistant_message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in assistant_message.tool_calls
            ]
        })

        # Ejecutar cada herramienta
        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            # Detectar comuna si la herramienta la menciona
            if "nombre_comuna" in arguments and not detected_comuna_codigo:
                nombre = arguments["nombre_comuna"]
                codigo = _get_codigo_comuna(db, nombre)
                if codigo:
                    detected_comuna_codigo = codigo

            # Ejecutar la herramienta
            tool_result = execute_tool(db, function_name, arguments)

            # Capturar top5 si es la herramienta de top ubicaciones
            if function_name == "obtener_top_ubicaciones" and not captured_top5:
                try:
                    result_data = json.loads(tool_result)
                    if "top_ubicaciones" in result_data:
                        # Formatear para el esquema de top5
                        captured_top5 = []
                        for i, ub in enumerate(result_data["top_ubicaciones"][:5], 1):
                            captured_top5.append({
                                "id": f"cluster_{i}",
                                "lat": ub.get("lat", 0),
                                "lon": ub.get("lon", 0),
                                "num_reportes": ub.get("num_reportes", 0),
                                "descripcion": ub.get("direcciones", "Sin dirección")[:200]
                            })
                except (ValueError, TypeError, AttributeError):
                    pass

            # Agregar resultado al historial
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            })

    # Si llegamos al límite de iteraciones
    return {
        "respuesta": "Lo siento, no pude completar el análisis. Por favor, intenta con una consulta más específica.",
        "generated_at": datetime.now(),
        "iterations": iteration,
        "error": "max_iterations_reached"
    }
