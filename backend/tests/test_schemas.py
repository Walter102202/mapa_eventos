import pytest
from pydantic import ValidationError

from app.schemas import ReporteCreate, SeveridadEnum


def test_reporte_severidad_default_media():
    r = ReporteCreate(lat=-33.45, lon=-70.67)
    assert r.severidad == SeveridadEnum.media


@pytest.mark.parametrize("lat,lon", [(91, 0), (-91, 0), (0, 181), (0, -181)])
def test_reporte_rechaza_coordenadas_fuera_de_rango(lat, lon):
    with pytest.raises(ValidationError):
        ReporteCreate(lat=lat, lon=lon)


def test_reporte_rechaza_severidad_invalida():
    with pytest.raises(ValidationError):
        ReporteCreate(lat=-33.45, lon=-70.67, severidad="critica")
