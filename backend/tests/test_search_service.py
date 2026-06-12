import pytest
from app.services.search_service import preview_search, preview_queries
from app.schemas.search import SearchPreviewRequest, QueryGenerationRequest
from unittest.mock import patch
from app.providers.search.exceptions import SearchProviderConfigurationError

def test_preview_queries():
    req = QueryGenerationRequest(
        market="US",
        language="en",
        categories=["RPG"],
        maximum_queries=2
    )
    res = preview_queries(req)
    assert res.total == 2
    assert len(res.queries) == 2

@pytest.mark.asyncio
async def test_preview_search_mock():
    req = SearchPreviewRequest(
        market="US",
        language="en",
        categories=["RPG"],
        results_per_query=2,
        provider="mock",
        maximum_queries=2
    )
    res = await preview_search(req)
    assert res.provider == "mock"
    assert res.result_count > 0
    assert len(res.errors) == 0
    assert len(res.generated_queries) == 2
    
@pytest.mark.asyncio
@patch("app.services.search_service.get_search_provider")
async def test_preview_search_error_handling(mock_get_provider):
    class FailingProvider:
        provider_name = "failing"
        async def search(self, query, limit):
            raise ValueError("Unexpected mock error")
            
    mock_get_provider.return_value = FailingProvider()
    
    req = SearchPreviewRequest(
        market="US",
        language="en",
        categories=["RPG"],
        results_per_query=2,
        provider="mock",
        maximum_queries=1
    )
    res = await preview_search(req)
    assert res.result_count == 0
    assert len(res.errors) == 1
    assert res.errors[0].error_type == "UnexpectedError"
    
@pytest.mark.asyncio
async def test_preview_search_config_error():
    req = SearchPreviewRequest(
        market="US",
        language="en",
        categories=["RPG"],
        results_per_query=2,
        provider="brave",
        maximum_queries=1
    )
    with patch("app.providers.search.brave.get_settings") as mock_get_settings:
        mock_get_settings.return_value.BRAVE_SEARCH_API_KEY = None
        mock_get_settings.return_value.SEARCH_PROVIDER = "brave"
        with pytest.raises(SearchProviderConfigurationError):
            await preview_search(req)
