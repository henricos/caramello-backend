import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from uuid import uuid4
from caramello.main import app
from caramello.models.family import Family

@pytest.fixture(name="client")
def client_fixture():
    return TestClient(app)

def test_create_family(client: TestClient):
    # Dynamic sample data
    data = {'name': 'test_string', 'description': 'test_string', 'status': 'test_string'}
    # Fix unique constraints
    if "email" in data: data["email"] = f"test_{uuid4()}@example.com"
    if "google_id" in data: data["google_id"] = f"gid_{uuid4()}"
    if "uuid" in data: del data["uuid"] # Should not send UUID on create usually?
    
    response = client.post(
        "/family/",
        json=data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["uuid"] is not None

def test_read_family(client: TestClient):
    # Dynamic sample data
    data = {'name': 'test_string', 'description': 'test_string', 'status': 'test_string'}
    if "email" in data: data["email"] = f"test_{uuid4()}@example.com"
    if "google_id" in data: data["google_id"] = f"gid_{uuid4()}"
    
    # Create first
    create_res = client.post(
        "/family/",
        json=data
    )
    assert create_res.status_code == 200, create_res.text
    uuid = create_res.json()["uuid"]
    
    response = client.get(f"/family/{uuid}")
    assert response.status_code == 200
    assert response.json()["uuid"] == uuid

def test_read_family_list(client: TestClient):
    # Dynamic sample data
    data = {'name': 'test_string', 'description': 'test_string', 'status': 'test_string'}
    if "email" in data: data["email"] = f"test_{uuid4()}@example.com"
    if "google_id" in data: data["google_id"] = f"gid_{uuid4()}"

    client.post("/family/", json=data)
    response = client.get("/family/")
    assert response.status_code == 200
    assert len(response.json()) > 0
