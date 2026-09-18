"""Fixtures compartidos. Los tests no necesitan MySQL: get_db se reemplaza por un stub."""

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


class FakeSession:
    """Sesión vacía para endpoints cuyo acceso a datos se mockea en el test."""

    def close(self):
        pass


def _fake_get_db():
    yield FakeSession()


@pytest.fixture
def client():
    app.dependency_overrides[get_db] = _fake_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
