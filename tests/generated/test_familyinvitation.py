import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from uuid import uuid4
from caramello.main import app
from caramello.models.familyinvitation import FamilyInvitation

@pytest.fixture(name="client")
def client_fixture():
    return TestClient(app)

def test_create_familyinvitation(client: TestClient):
    # Dynamic sample data
    data = {'family_id': 1, 'inviter_id': 1, 'invitee_email': 'test@example.com', 'status': 'test_string', 'expires_at': '2026-01-01T00:00:00'}
    # Fix unique constraints
    if "email" in data: data["email"] = f"test_{uuid4()}@example.com"
    if "google_id" in data: data["google_id"] = f"gid_{uuid4()}"
    if "uuid" in data: del data["uuid"] # Should not send UUID on create usually?
    
    response = client.post(
        "/family_invitation/",
        json=data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["uuid"] is not None

def test_read_familyinvitation(client: TestClient):
    # Dynamic sample data
    data = {'family_id': 1, 'inviter_id': 1, 'invitee_email': 'test@example.com', 'status': 'test_string', 'expires_at': '2026-01-01T00:00:00'}
    if "email" in data: data["email"] = f"test_{uuid4()}@example.com"
    if "google_id" in data: data["google_id"] = f"gid_{uuid4()}"
    
    # Create first
    create_res = client.post(
        "/family_invitation/",
        json=data
    )
    assert create_res.status_code == 200, create_res.text
    uuid = create_res.json()["uuid"]
    
    response = client.get(f"/family_invitation/{uuid}")
    assert response.status_code == 200
    assert response.json()["uuid"] == uuid

def test_read_familyinvitation_list(client: TestClient):
    # Dynamic sample data
    data = {'family_id': 1, 'inviter_id': 1, 'invitee_email': 'test@example.com', 'status': 'test_string', 'expires_at': '2026-01-01T00:00:00'}
    if "email" in data: data["email"] = f"test_{uuid4()}@example.com"
    if "google_id" in data: data["google_id"] = f"gid_{uuid4()}"

    client.post("/family_invitation/", json=data)
    response = client.get("/family_invitation/")
    assert response.status_code == 200
    assert len(response.json()) > 0
