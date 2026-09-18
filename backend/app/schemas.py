from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SeveridadEnum(str, Enum):
    baja = "baja"
    media = "media"
    alta = "alta"


# --- Reportes ---

class ReporteCreate(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="Latitud del bache")
    lon: float = Field(..., ge=-180, le=180, description="Longitud del bache")
    direccion: Optional[str] = Field(None, max_length=255, description="Dirección exacta del bache")
    comentario: Optional[str] = Field(None, max_length=1000)
    severidad: SeveridadEnum = SeveridadEnum.media


class ReporteResponse(BaseModel):
    id: int
    lat: float
    lon: float
    codigo_comuna: Optional[str]
    direccion: Optional[str]
    comentario: Optional[str]
    severidad: SeveridadEnum
    foto_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReporteCreatedResponse(BaseModel):
    id: int
    codigo_comuna: str
    nombre_comuna: str
    mensaje: str


# --- Comunas ---

class ComunaBase(BaseModel):
    codigo_comuna: str
    nombre_comuna: str
    codigo_region: str = "13"


class ComunaResponse(ComunaBase):
    total_baches: int = 0

    class Config:
        from_attributes = True


class ComunaListResponse(BaseModel):
    comunas: List[ComunaResponse]
    total: int


# --- Baches por Comuna ---

class BachesListResponse(BaseModel):
    codigo_comuna: str
    nombre_comuna: str
    baches: List[ReporteResponse]
    total: int
    page: int
    page_size: int


# --- Resumen LLM ---

class TopBacheCluster(BaseModel):
    id: str
    lat: float
    lon: float
    num_reportes: int
    descripcion: str


class ResumenComunaResponse(BaseModel):
    codigo_comuna: str
    nombre_comuna: str
    total_baches: int
    resumen: str
    top5: List[TopBacheCluster]
    generated_at: datetime
    from_cache: bool = False


# --- Errores ---

class ErrorResponse(BaseModel):
    detail: str
