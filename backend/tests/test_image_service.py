import asyncio
import io

from PIL import Image
from starlette.datastructures import UploadFile

from app.services import image_service
from app.services.image_service import (
    MAX_FILE_SIZE,
    read_upload_limited,
    validate_image,
    validate_image_content,
)


def test_acepta_jpg_pequeno():
    ok, msg = validate_image("bache.JPG", 1024)
    assert ok and msg == ""


def test_rechaza_extension_no_permitida():
    ok, msg = validate_image("bache.gif", 1024)
    assert not ok and "no permitido" in msg


def test_rechaza_archivo_muy_grande():
    ok, msg = validate_image("bache.png", MAX_FILE_SIZE + 1)
    assert not ok and "muy grande" in msg


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (2, 2), color="red").save(buf, format="PNG")
    return buf.getvalue()


def _gif_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("P", (2, 2)).save(buf, format="GIF")
    return buf.getvalue()


def test_validate_image_content_acepta_png_real():
    ok, msg = validate_image_content(_png_bytes())
    assert ok and msg == ""


def test_validate_image_content_rechaza_html_con_extension_png():
    ok, msg = validate_image_content(b"<html><script>alert(1)</script></html>")
    assert not ok and "imagen" in msg.lower()


def test_validate_image_content_rechaza_formato_no_permitido():
    ok, msg = validate_image_content(_gif_bytes())
    assert not ok and "GIF" in msg


def test_read_upload_limited_devuelve_bytes_si_cabe():
    data = b"x" * 1000
    upload = UploadFile(file=io.BytesIO(data), filename="a.png")
    assert asyncio.run(read_upload_limited(upload, max_bytes=1000)) == data


def test_read_upload_limited_corta_si_supera_el_maximo(monkeypatch):
    monkeypatch.setattr(image_service, "MAX_FILE_SIZE", 10)
    upload = UploadFile(file=io.BytesIO(b"x" * 11), filename="a.png")
    assert asyncio.run(read_upload_limited(upload)) is None
