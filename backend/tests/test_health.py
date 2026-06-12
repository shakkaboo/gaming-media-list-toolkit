import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert data["docs"] == "/docs"
    assert data["health"] == "/api/health"

def test_get_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "environment" in data

def test_get_config_health():
    response = client.get("/api/health/config")
    assert response.status_code == 200
    data = response.json()
    
    # Check for expected keys
    assert "environment" in data
    assert "search_provider" in data
    assert "traffic_provider" in data
    assert "verified_threshold" in data
    assert "uncertain_threshold" in data
    assert "default_minimum_pageviews" in data
    
    # Check for absence of sensitive keys
    assert "DATABASE_URL" not in data
    assert "BRAVE_SEARCH_API_KEY" not in data
    
    # General check: no keys should look like passwords or secrets
    for key in data.keys():
        assert "password" not in key.lower()
        assert "secret" not in key.lower()
        assert "key" not in key.lower()

def test_unknown_route():
    response = client.get("/api/unknown/route/123")
    assert response.status_code == 404
