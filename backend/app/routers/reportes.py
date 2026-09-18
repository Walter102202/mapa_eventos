"""Router para endpoints de reportes de baches."""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..limiter import limiter
from ..schemas import ErrorResponse, ReporteCreate, ReporteCreatedResponse, SeveridadEnum
from ..services import image_service, reporte_service

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


@router.post(
    "",
    response_model=ReporteCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Ubicación fuera de la Región Metropolitana"}
    }
)
def crear_reporte(
    reporte: ReporteCreate,
    db: Session = Depends(get_db)
):
    """
    Crear un nuevo reporte de bache.

    El sistema determina automáticamente la comuna basándose en las coordenadas.
    Solo se aceptan reportes dentro de la Región Metropolitana de Santiago.

    - **lat**: Latitud del bache (-90 a 90)
    - **lon**: Longitud del bache (-180 a 180)
    - **comentario**: Descripción opcional del bache
    - **severidad**: Nivel de severidad (baja, media, alta)
    """
    resultado = reporte_service.crear_reporte(db, reporte)

    if not resultado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La ubicación especificada está fuera de la Región Metropolitana de Santiago. "
                   "Solo se aceptan reportes dentro de las comunas de la RM."
        )

    return ReporteCreatedResponse(
        id=resultado["id"],
        codigo_comuna=resultado["codigo_comuna"],
        nombre_comuna=resultado["nombre_comuna"],
        mensaje=f"Reporte creado exitosamente en la comuna de {resultado['nombre_comuna']}"
    )


@router.post(
    "/con-foto",
    response_model=ReporteCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Error en validación o ubicación"},
        413: {"model": ErrorResponse, "description": "Imagen demasiado grande"},
        422: {"model": ErrorResponse, "description": "Imagen rechazada por moderación"},
        429: {"description": "Demasiadas solicitudes"},
    }
)
@limiter.limit(get_settings().rate_limit_ia)
async def crear_reporte_con_foto(
    request: Request,
    lat: float = Form(...),
    lon: float = Form(...),
    severidad: str = Form("media"),
    direccion: Optional[str] = Form(None),
    comentario: Optional[str] = Form(None),
    foto: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """
    Crear un nuevo reporte de bache con foto opcional.

    La foto es analizada automáticamente para detectar contenido inapropiado.
    Solo se aceptan imágenes de baches o daños en vías públicas.

    - **lat**: Latitud del bache
    - **lon**: Longitud del bache
    - **severidad**: Nivel de severidad (baja, media, alta)
    - **direccion**: Dirección del bache (opcional)
    - **comentario**: Descripción opcional del bache
    - **foto**: Imagen del bache (opcional, máx 5MB, jpg/png/webp)
    """
    foto_url = None

    # Procesar imagen si se proporciona
    if foto and foto.filename:
        # Extensión antes de leer nada (barato)
        is_valid, error_msg = image_service.validate_image(foto.filename, 0)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

        # Leer en chunks y cortar si supera el máximo: nunca cargamos un archivo gigante en memoria
        image_data = await image_service.read_upload_limited(foto)
        if image_data is None:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"El archivo es muy grande. Máximo {image_service.MAX_FILE_SIZE // (1024 * 1024)} MB",
            )

        # Contenido real (magic bytes), no solo la extensión
        is_valid, error_msg = image_service.validate_image_content(image_data)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

        # Moderar contenido
        is_appropriate, rejection_reason = image_service.moderate_image(image_data)
        if not is_appropriate:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Imagen rechazada: {rejection_reason}"
            )

        # Guardar imagen
        foto_url = image_service.save_image(image_data, foto.filename)

    # Crear reporte
    try:
        severidad_enum = SeveridadEnum(severidad)
    except ValueError:
        severidad_enum = SeveridadEnum.media

    reporte = ReporteCreate(
        lat=lat,
        lon=lon,
        severidad=severidad_enum,
        direccion=direccion,
        comentario=comentario
    )

    resultado = reporte_service.crear_reporte(db, reporte, foto_url=foto_url)

    if not resultado:
        # Si falla, eliminar la imagen subida
        if foto_url:
            image_service.delete_image(foto_url)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La ubicación especificada está fuera de la Región Metropolitana de Santiago."
        )

    return ReporteCreatedResponse(
        id=resultado["id"],
        codigo_comuna=resultado["codigo_comuna"],
        nombre_comuna=resultado["nombre_comuna"],
        mensaje=f"Reporte creado exitosamente en la comuna de {resultado['nombre_comuna']}"
    )
