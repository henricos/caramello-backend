"""Checks that the OpenAPI spec advertises the installed package version (DEPLOY-03)."""

from __future__ import annotations

from importlib.metadata import version as package_version


def test_openapi_version_field(client):
    """DEPLOY-03: /openapi.json exposes the version from the package metadata.

    `main.py` reads it via `importlib.metadata`, so `pyproject.toml`'s
    `version` is the single source of truth — no APP_VERSION build argument
    can drift away from what is actually installed.
    """
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert "info" in spec
    assert "version" in spec["info"]
    assert spec["info"]["version"] == package_version("caramello-api")
