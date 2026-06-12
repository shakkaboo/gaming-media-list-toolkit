import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_candidate_preview_api_with_mock_provider():
    payload = {
        "market": "US",
        "language": "en",
        "categories": ["esports"],
        "keywords": ["dota"],
        "maximum_queries": 1,
        "results_per_query": 5,
        "provider": "mock",
        "include_rejected": True,
        "include_duplicates": True
    }
    
    response = client.post("/api/search/candidates/preview", json=payload)
    assert response.status_code == 200
    data = response.json()
    
    assert "accepted_candidates" in data
    assert "rejected_candidates" in data
    assert "duplicates" in data
    
    # Since we use mock provider, the results are deterministic
    # The mock provider generates things like example.com, youtube.com, etc.
    # We expect twitter.com to be rejected.
    rejected = [r["original_url"] for r in data.get("rejected_candidates", [])]
    assert any("twitter.com" in r for r in rejected)
    
    assert data["accepted_count"] > 0
    assert data["provider"] == "mock"

def test_candidate_preview_api_invalid_request():
    payload = {
        "market": "",
        "language": "en",
        "categories": ["esports"],
        "results_per_query": 5,
        "provider": "mock"
    }
    response = client.post("/api/search/candidates/preview", json=payload)
    assert response.status_code == 422
