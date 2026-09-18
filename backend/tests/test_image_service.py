from app.services.image_service import MAX_FILE_SIZE, validate_image


def test_acepta_jpg_pequeno():
    ok, msg = validate_image("bache.JPG", 1024)
    assert ok and msg == ""


def test_rechaza_extension_no_permitida():
    ok, msg = validate_image("bache.gif", 1024)
    assert not ok and "no permitido" in msg


def test_rechaza_archivo_muy_grande():
    ok, msg = validate_image("bache.png", MAX_FILE_SIZE + 1)
    assert not ok and "muy grande" in msg
