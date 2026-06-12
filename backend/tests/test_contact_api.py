import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas.search import NormalizedCandidate

client = TestClient(app)

def test_preview_contacts_api():
    req_data = {
        "candidates": [
            {
                "requested_url": "http://example.com/",
                "normalized_url": "http://example.com/",
                "homepage_url": "http://example.com/",
                "registered_domain": "example.com",
                "is_multitenant": False,
                "original_url": "http://example.com/",
                "title": "Example Gaming",
                "query_text": "gaming media",
                "provider": "mock",
                "result_position": 1
            }
        ],
        "allow_uncertain": False
    }
    
    # Just checking it accepts the request and returns the right schema
    # The actual network is mocked at the service level if we use respx, 
    # but here it will timeout or fail fetching.
    # We just want to see if the endpoint works and returns 200 with schema.
    resp = client.post("/api/contacts/preview", json=req_data)
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "sites_processed" in data
