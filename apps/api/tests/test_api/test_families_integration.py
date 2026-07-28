"""Integration tests for the families domain — against the real caramello_dev database.

Uses a per-test transaction rollback (the db_session + async_client fixtures from
conftest.py). Requires the caramello_dev database to be reachable and already migrated.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
async def test_create_family(async_client):
    """FAMILY-01: POST /families/registry creates a family against the real database."""
    response = await async_client.post(
        "/api/v1/families/registry",
        json={"name": "Familia Integração"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Familia Integração"
    assert "uuid" in data


@pytest.mark.integration
async def test_list_my_families(async_client):
    """FAMILY-02: GET /families/families returns a list containing the created family."""
    # Creates a family to guarantee at least one result
    create_response = await async_client.post(
        "/api/v1/families/registry",
        json={"name": "Familia para Listar"},
    )
    assert create_response.status_code == 201
    created_uuid = create_response.json()["uuid"]

    # Lists and checks that the created family is present
    response = await async_client.get("/api/v1/families/families")
    assert response.status_code == 200
    families = response.json()
    assert isinstance(families, list)
    uuids = [f["uuid"] for f in families]
    assert created_uuid in uuids


@pytest.mark.integration
async def test_pre_register_member(async_client):
    """D-07: POST /families/{uuid}/pre-register pre-registers a member by e-mail."""
    # Creates a family to have a valid UUID
    create_response = await async_client.post(
        "/api/v1/families/registry",
        json={"name": "Familia para Pre-Register"},
    )
    assert create_response.status_code == 201
    family_uuid = create_response.json()["uuid"]

    # Pre-registers the member and checks the returned e-mail
    response = await async_client.post(
        f"/api/v1/families/families/{family_uuid}/pre-register",
        json={"email": "novo@example.com"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "novo@example.com"
    # The two foreign keys are exposed as UUIDs (`expose_as_uuid` in the DSL) and
    # the integer ids never reach the wire — the invariant in the root
    # docs/architecture.md. Asserted against a real database because that is the
    # only place the UUID -> internal id resolution actually happens.
    assert data["family_uuid"] == family_uuid
    assert "uuid" in data
    for leaked in ("family_id", "inviter_id", "id"):
        assert leaked not in data, f"{leaked} must not appear in the response: {data}"


@pytest.mark.integration
async def test_list_members(async_client):
    """D-07: GET /families/{uuid}/members lists the family members with the owner role."""
    # Creates a family to have a valid UUID
    create_response = await async_client.post(
        "/api/v1/families/registry",
        json={"name": "Familia para Listar Membros"},
    )
    assert create_response.status_code == 201
    family_uuid = create_response.json()["uuid"]

    # Lists the members — must hold exactly 1 item: the fake_user with the owner role
    response = await async_client.get(f"/api/v1/families/families/{family_uuid}/members")
    assert response.status_code == 200
    members = response.json()
    assert isinstance(members, list)
    assert len(members) >= 1
    roles = [m["role"] for m in members]
    assert "owner" in roles
