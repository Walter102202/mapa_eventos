import enum

from sqlalchemy import JSON, Column, DateTime, Double, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from .database import Base


class Severidad(str, enum.Enum):
    baja = "baja"
    media = "media"
    alta = "alta"


class ComunaRM(Base):
    __tablename__ = "comunas_rm"

    codigo_comuna = Column(String(10), primary_key=True)
    nombre_comuna = Column(String(100), nullable=False)
    codigo_region = Column(String(5), default="13")
    # geom se maneja con raw SQL para operaciones espaciales


class ReporteBache(Base):
    __tablename__ = "reportes_baches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lat = Column(Double, nullable=False)
    lon = Column(Double, nullable=False)
    # punto se maneja con raw SQL para operaciones espaciales
    codigo_comuna = Column(String(10), ForeignKey("comunas_rm.codigo_comuna"))
    direccion = Column(String(255))  # Dirección exacta para facilitar reparaciones
    comentario = Column(Text)
    severidad = Column(Enum(Severidad), default=Severidad.media)
    foto_url = Column(String(500), nullable=True)  # URL de la foto del bache
    created_at = Column(DateTime, server_default=func.now())


class ResumenComuna(Base):
    __tablename__ = "resumen_comuna"

    codigo_comuna = Column(String(10), ForeignKey("comunas_rm.codigo_comuna"), primary_key=True)
    resumen_texto = Column(Text)
    top5_json = Column(JSON)
    generated_at = Column(DateTime, server_default=func.now())
