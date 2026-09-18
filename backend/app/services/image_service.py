"""Servicio para manejo y moderación de imágenes."""

import base64
import io
import uuid
from pathlib import Path
from typing import Optional, Tuple

from fastapi import UploadFile
from openai import OpenAI
from PIL import Image, UnidentifiedImageError

from ..config import get_settings

settings = get_settings()

# Directorio para guardar las imágenes
UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Extensiones permitidas
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

# Formatos que Pillow debe detectar en el contenido (la extensión sola no alcanza)
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
CHUNK_SIZE = 64 * 1024


def get_openai_client() -> OpenAI:
    """Obtener cliente de OpenAI."""
    return OpenAI(api_key=settings.openai_api_key)


def validate_image(filename: str, file_size: int) -> Tuple[bool, str]:
    """
    Validar que el archivo sea una imagen válida.

    Returns:
        Tuple[bool, str]: (es_válido, mensaje_error)
    """
    # Verificar extensión
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Tipo de archivo no permitido. Use: {', '.join(ALLOWED_EXTENSIONS)}"

    # Verificar tamaño
    if file_size > MAX_FILE_SIZE:
        return False, f"El archivo es muy grande. Máximo {MAX_FILE_SIZE // (1024*1024)} MB"

    return True, ""


async def read_upload_limited(upload: UploadFile, max_bytes: Optional[int] = None) -> Optional[bytes]:
    """
    Leer un upload en chunks y cortar apenas supera max_bytes.

    Evita cargar en memoria un archivo gigante antes de validar el tamaño.

    Returns:
        bytes con el contenido, o None si superó el máximo.
    """
    limite = max_bytes if max_bytes is not None else MAX_FILE_SIZE
    chunks = []
    total = 0
    while True:
        chunk = await upload.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > limite:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def validate_image_content(data: bytes) -> Tuple[bool, str]:
    """
    Validar que los bytes sean realmente una imagen JPEG/PNG/WEBP (magic bytes + estructura).

    Returns:
        Tuple[bool, str]: (es_válido, mensaje_error)
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            formato = img.format
            img.verify()
    except Image.DecompressionBombError:
        return False, "La imagen es demasiado grande para procesarse"
    except (UnidentifiedImageError, OSError, ValueError):
        return False, "El archivo no es una imagen válida"

    if formato not in ALLOWED_FORMATS:
        return False, f"Formato {formato} no permitido. Use: {', '.join(sorted(ALLOWED_FORMATS))}"

    return True, ""


def moderate_image(image_data: bytes) -> Tuple[bool, str]:
    """
    Moderar una imagen usando OpenAI Vision para detectar contenido inapropiado.

    Args:
        image_data: Bytes de la imagen

    Returns:
        Tuple[bool, str]: (es_apropiado, motivo_rechazo)
    """
    try:
        client = get_openai_client()

        # Convertir imagen a base64
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        # Usar GPT-4o para analizar la imagen
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Más económico para moderación
            messages=[
                {
                    "role": "system",
                    "content": """Eres un moderador de contenido. Tu tarea es analizar imágenes
                    para una aplicación de reporte de baches en calles.

                    RECHAZA la imagen si contiene:
                    - Contenido sexual, desnudez o sugestivo
                    - Violencia gráfica o gore
                    - Contenido de odio o discriminatorio
                    - Drogas o sustancias ilegales
                    - Información personal identificable (rostros claros, documentos, patentes legibles)
                    - Spam o publicidad
                    - Contenido que claramente NO es un bache o daño en la vía pública

                    ACEPTA la imagen si:
                    - Muestra un bache, grieta o daño en pavimento/calle
                    - Muestra aceras dañadas o en mal estado
                    - Muestra señalética dañada relacionada con vías
                    - Es una foto genérica de calle/pavimento (aunque no muestre claramente un bache)

                    Responde SOLO con un JSON: {"apropiado": true/false, "motivo": "explicación breve"}"""
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Analiza esta imagen y determina si es apropiada para una app de reporte de baches."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}",
                                "detail": "low"  # Usar baja resolución para ahorrar tokens
                            }
                        }
                    ]
                }
            ],
            max_tokens=150
        )

        # Parsear respuesta
        content = response.choices[0].message.content.strip()

        # Intentar extraer JSON de la respuesta
        import json
        try:
            # Buscar JSON en la respuesta
            if "{" in content and "}" in content:
                json_str = content[content.find("{"):content.rfind("}")+1]
                result = json.loads(json_str)
                return result.get("apropiado", False), result.get("motivo", "")
        except json.JSONDecodeError:
            pass

        # Si no se pudo parsear, asumir que es apropiado si no hay palabras clave negativas
        negative_keywords = ["rechaz", "inapropiad", "no permitid", "sexual", "violenc"]
        is_appropriate = not any(kw in content.lower() for kw in negative_keywords)
        return is_appropriate, content

    except Exception as e:
        # En caso de error, registrar y permitir (fail-open para no bloquear usuarios)
        print(f"Error en moderación de imagen: {e}")
        # Por seguridad, si hay error de API, rechazar
        return False, "Error al verificar la imagen. Intente nuevamente."


def save_image(image_data: bytes, original_filename: str) -> str:
    """
    Guardar imagen en el servidor.

    Args:
        image_data: Bytes de la imagen
        original_filename: Nombre original del archivo

    Returns:
        str: URL relativa de la imagen guardada
    """
    # Generar nombre único
    ext = Path(original_filename).suffix.lower()
    unique_filename = f"{uuid.uuid4().hex}{ext}"

    # Guardar archivo
    file_path = UPLOAD_DIR / unique_filename
    with open(file_path, "wb") as f:
        f.write(image_data)

    # Retornar URL relativa
    return f"/uploads/{unique_filename}"


def delete_image(foto_url: str) -> bool:
    """
    Eliminar una imagen del servidor.

    Args:
        foto_url: URL relativa de la imagen

    Returns:
        bool: True si se eliminó correctamente
    """
    try:
        if foto_url and foto_url.startswith("/uploads/"):
            filename = foto_url.replace("/uploads/", "")
            file_path = UPLOAD_DIR / filename
            if file_path.exists():
                file_path.unlink()
                return True
    except Exception as e:
        print(f"Error eliminando imagen: {e}")
    return False
