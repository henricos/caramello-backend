import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from uuid import uuid4
from caramello.main import app
from caramello.models.user import User

@pytest.fixture(name="client")
def client_fixture():
    return TestClient(app)

def test_create_user(client: TestClient):
    # Dynamic sample data
    data = {'idp_sub': 'test_string', 'email': 'test@example.com', 'name': 'test_string'}
    # Fix unique constraints
    if "email" in data: data["email"] = f"test_{uuid4()}@example.com"
    if "google_id" in data: data["google_id"] = f"gid_{uuid4()}"
    if "uuid" in data: del data["uuid"] # Should not send UUID on create usually?
    
    response = client.post(
        "/user/",
        json=data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["uuid"] is not None

def test_read_user(client: TestClient):
    # Dynamic sample data
    data = {'idp_sub': 'test_string', 'email': 'test@example.com', 'name': 'test_string'}
    if "email" in data: data["email"] = f"test_{uuid4()}@example.com"
    if "google_id" in data: data["google_id"] = f"gid_{uuid4()}"
    
    # Create first
    create_res = client.post(
        "/user/",
        json=data
    )
    assert create_res.status_code == 200, create_res.text
    uuid = create_res.json()["uuid"]
    
    response = client.get(f"/user/{uuid}")
    assert response.status_code == 200
    assert response.json()["uuid"] == uuid

def test_read_user_list(client: TestClient):
    # Dynamic sample data
    data = {'idp_sub': 'test_string', 'email': 'test@example.com', 'name': 'test_string'}
    if "email" in data: data["email"] = f"test_{uuid4()}@example.com"
    if "google_id" in data: data["google_id"] = f"gid_{uuid4()}"

    client.post("/user/", json=data)
    response = client.get("/user/")
    assert response.status_code == 200
    assert len(response.json()) > 0
