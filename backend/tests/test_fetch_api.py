import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.schemas.search import NormalizedCandidate
from app.schemas.fetch import FetchRequest
from app.services.fetch_service import FetchService
from unittest.mock import patch

@pytest.fixture
def test_candidates():
    return [
        NormalizedCandidate(
            original_url="http://example.com/",
            normalized_url="http://example.com/",
            homepage_url="http://example.com/",
            registered_domain="example.com",
            subdomain="",
            title="Test",
            snippet="Test snippet",
            query_text="dota 2",
            provider="mock",
            result_position=1,
            market="US",
            language="en"
        )
    ]

@pytest.mark.asyncio
async def test_fetch_preview_api_success(test_candidates):
    with patch("app.services.fetch_service.FetchService.fetch_preview") as mock_fetch_preview:
        mock_fetch_preview.return_value = {
            "results": [],
            "success_count": 0,
            "failure_count": 0,
            "skipped_count": 0
        }
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            req = FetchRequest(candidates=test_candidates).model_dump()
            response = await ac.post("/api/fetch/preview", json=req)
            
        assert response.status_code == 200
        assert response.json()["skipped_count"] == 0

@pytest.mark.asyncio
async def test_fetch_service_limits(test_candidates):
    with patch("app.fetching.page_fetcher.fetch_page_with_retries"):
        with patch("app.services.fetch_service.get_settings") as mock_get_settings:
            import copy
            from app.config import get_settings
            mock_settings = copy.deepcopy(get_settings())
            mock_settings.MAX_FETCH_CANDIDATES = 0
            mock_get_settings.return_value = mock_settings
            
            service = FetchService()
            req = FetchRequest(candidates=test_candidates)
            res = await service.fetch_preview(req)
            
            assert res.skipped_count == 1
            assert len(res.results) == 0

@pytest.mark.asyncio
async def test_fetch_service_max_candidates(test_candidates):
    with patch("app.fetching.page_fetcher.fetch_page_with_retries"):
        service = FetchService()
        
        req = FetchRequest(candidates=test_candidates, maximum_candidates=0)
        res = await service.fetch_preview(req)
        assert res.skipped_count == 0
        assert len(res.results) == 1
