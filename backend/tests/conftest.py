"""Fixtures compartidos. Los tests no necesitan MySQL: get_db se reemplaza por un stub."""

import os

# Debe ir ANTES de importar app.*: Settings se construye al importar y se cachea con lru_cache.
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["RATE_LIMIT_IA"] = "2/minute"
os.environ["CORS_ORIGINS"] = ""
os.environ["ADMIN_TOKEN"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import get_db  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.main import app  # noqa: E402


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


@pytest.fixture
def limiter_on():
    """Habilita el rate limiter (2/minute por conftest) solo durante el test."""
    limiter.enabled = True
    limiter.reset()
    yield
    limiter.enabled = False
    limiter.reset()
