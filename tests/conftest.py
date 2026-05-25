"""Fixtures compartilhadas para os testes do Caramello."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """TestClient da app FastAPI, importado tarde para evitar erros em waves anteriores."""
    from caramello.main import app
    return TestClient(app)
