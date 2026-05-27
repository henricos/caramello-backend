"""Testes de integração do domínio families — banco real caramello_dev.

Usa transaction rollback por teste (fixtures db_session + async_client de conftest.py).
Requer: banco caramello_dev acessível e migrado previamente.
"""
from __future__ import annotations

import pytest


@pytest.mark.integration
async def test_create_family(async_client):
    """FAMILY-01: POST /families/registry cria família com banco real."""
    response = await async_client.post(
        "/families/registry",
        json={"name": "Familia Integração"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Familia Integração"
    assert "uuid" in data


@pytest.mark.integration
async def test_list_my_families(async_client):
    """FAMILY-02: GET /families/families retorna lista do usuário autenticado."""
    response = await async_client.get("/families/families")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.integration
async def test_pre_register_member(async_client):
    """D-07: POST /families/{uuid}/pre-register pré-registra membro por email."""
    # Cria família para ter UUID válido
    create_response = await async_client.post(
        "/families/registry",
        json={"name": "Familia para Pre-Register"},
    )
    assert create_response.status_code == 201
    family_uuid = create_response.json()["uuid"]

    # Pré-registra membro
    response = await async_client.post(
        f"/families/families/{family_uuid}/pre-register",
        json={"email": "novo@example.com"},
    )
    assert response.status_code == 201


@pytest.mark.integration
async def test_list_members(async_client):
    """D-07: GET /families/{uuid}/members lista membros da família."""
    # Cria família para ter UUID válido
    create_response = await async_client.post(
        "/families/registry",
        json={"name": "Familia para Listar Membros"},
    )
    assert create_response.status_code == 201
    family_uuid = create_response.json()["uuid"]

    # Lista membros — deve conter ao menos o owner
    response = await async_client.get(f"/families/families/{family_uuid}/members")
    assert response.status_code == 200
    members = response.json()
    assert isinstance(members, list)
    assert len(members) >= 1
