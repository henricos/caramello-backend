"""Verifica que APP_VERSION aparece no campo version da OpenAPI spec (DEPLOY-03)."""
from __future__ import annotations

import os

import pytest


@pytest.mark.xfail(
    reason="Requer 05-04: APP_VERSION não dinâmico ainda",
    strict=False,
)
def test_openapi_version_field(client):
    """DEPLOY-03: /openapi.json contém campo version com APP_VERSION ou fallback."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert "info" in spec
    assert "version" in spec["info"]
    # Sem APP_VERSION setado, fallback deve ser "0.0.0"
    expected = os.getenv("APP_VERSION", "0.0.0")
    assert spec["info"]["version"] == expected
