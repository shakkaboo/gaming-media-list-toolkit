import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from app.schemas.search import SearchPreviewResponse

client = TestClient(app)

def test_preview_queries_api():
    response = client.post("/api/search/queries/preview", json={
        "market": "US",
        "language": "en",
        "categories": ["RPG"]
    })
    assert response.status_code == 200
    assert response.json()["total"] > 0

def test_preview_queries_api_invalid():
    response = client.post("/api/search/queries/preview", json={
        "market": "",
        "language": "en",
        "categories": ["RPG"]
    })
    assert response.status_code == 422

@patch("app.api.search.preview_search")
def test_preview_results_api(mock_preview_search):
    from app.schemas.search import SearchPreviewResponse
    mock_preview_search.return_value = SearchPreviewResponse(
        provider="mock",
        result_count=0,
        errors=[],
        generated_queries=[],
        results=[]
    )
    
    response = client.post("/api/search/results/preview", json={
        "market": "US",
        "language": "en",
        "categories": ["RPG"],
        "results_per_query": 5
    })
    assert response.status_code == 200

def test_preview_results_api_invalid_provider():
    response = client.post("/api/search/results/preview", json={
        "market": "US",
        "language": "en",
        "categories": ["RPG"],
        "results_per_query": 5,
        "provider": "invalid"
    })
    assert response.status_code == 422
