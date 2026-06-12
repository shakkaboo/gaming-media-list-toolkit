import pytest
import respx
import httpx
from datetime import datetime
from unittest.mock import patch
from app.providers.search.mock import MockSearchProvider
from app.providers.search.brave import BraveSearchProvider
from app.providers.search.exceptions import (
    SearchProviderConfigurationError,
    SearchProviderRateLimitError,
    SearchProviderTimeoutError,
    SearchProviderResponseError
)
from app.schemas.search import GeneratedSearchQuery

@pytest.fixture
def sample_query():
    return GeneratedSearchQuery(
        query_text="RPG news",
        category="RPG",
        market="US",
        language="en",
        template_name="news"
    )

@pytest.mark.asyncio
async def test_mock_provider(sample_query):
    provider = MockSearchProvider()
    results = await provider.search(sample_query, limit=3)
    assert len(results) == 3
    assert results[0].provider == "mock"
    assert results[0].query_text == "RPG news"
    
    all_results = await provider.search(sample_query, limit=10)
    urls = [r.url for r in all_results]
    assert any("duplicate/article" in u for u in urls)
    assert any("twitter.com" in u for u in urls)

@pytest.mark.asyncio
@respx.mock
@patch("app.providers.search.brave.get_settings")
async def test_brave_provider_success(mock_get_settings, sample_query):
    mock_get_settings.return_value.BRAVE_SEARCH_API_KEY = "test_key"
    mock_get_settings.return_value.BRAVE_SEARCH_BASE_URL = "https://api.search.brave.com/res/v1/web/search"
    mock_get_settings.return_value.SEARCH_REQUEST_TIMEOUT_SECONDS = 10
    mock_get_settings.return_value.BRAVE_SEARCH_SAFESEARCH = "moderate"
    mock_get_settings.return_value.BRAVE_SEARCH_FRESHNESS = None
    mock_get_settings.return_value.BRAVE_SEARCH_MAX_RETRIES = 2
    
    respx.get("https://api.search.brave.com/res/v1/web/search").mock(return_value=httpx.Response(200, json={
        "web": {
            "results": [
                {
                    "url": "https://example.com/1",
                    "title": "Example 1",
                    "description": "Desc 1",
                    "page_age": "2023-10-27T10:00:00Z"
                }
            ]
        }
    }))
    
    provider = BraveSearchProvider()
    results = await provider.search(sample_query, limit=1)
    
    assert len(results) == 1
    assert results[0].url == "https://example.com/1"
    assert results[0].published_at is not None

@pytest.mark.asyncio
@respx.mock
@patch("app.providers.search.brave.get_settings")
async def test_brave_provider_401(mock_get_settings, sample_query):
    mock_get_settings.return_value.BRAVE_SEARCH_API_KEY = "test_key"
    mock_get_settings.return_value.BRAVE_SEARCH_BASE_URL = "https://api.search.brave.com/res/v1/web/search"
    mock_get_settings.return_value.SEARCH_REQUEST_TIMEOUT_SECONDS = 10
    mock_get_settings.return_value.BRAVE_SEARCH_SAFESEARCH = "moderate"
    mock_get_settings.return_value.BRAVE_SEARCH_FRESHNESS = None
    mock_get_settings.return_value.BRAVE_SEARCH_MAX_RETRIES = 2
    
    respx.get("https://api.search.brave.com/res/v1/web/search").mock(return_value=httpx.Response(401))
    
    provider = BraveSearchProvider()
    with pytest.raises(SearchProviderConfigurationError):
        await provider.search(sample_query, limit=1)

@pytest.mark.asyncio
@respx.mock
@patch("app.providers.search.brave.get_settings")
async def test_brave_provider_429(mock_get_settings, sample_query):
    mock_get_settings.return_value.BRAVE_SEARCH_API_KEY = "test_key"
    mock_get_settings.return_value.BRAVE_SEARCH_BASE_URL = "https://api.search.brave.com/res/v1/web/search"
    mock_get_settings.return_value.SEARCH_REQUEST_TIMEOUT_SECONDS = 10
    mock_get_settings.return_value.BRAVE_SEARCH_SAFESEARCH = "moderate"
    mock_get_settings.return_value.BRAVE_SEARCH_FRESHNESS = None
    mock_get_settings.return_value.BRAVE_SEARCH_MAX_RETRIES = 2
    
    # Retry-After is > 5s, so it should raise immediately
    respx.get("https://api.search.brave.com/res/v1/web/search").mock(return_value=httpx.Response(429, headers={"Retry-After": "10"}))
    
    provider = BraveSearchProvider()
    with pytest.raises(SearchProviderRateLimitError):
        await provider.search(sample_query, limit=1)

@pytest.mark.asyncio
@respx.mock
@patch("app.providers.search.brave.get_settings")
async def test_brave_provider_500_retry(mock_get_settings, sample_query):
    mock_get_settings.return_value.BRAVE_SEARCH_API_KEY = "test_key"
    mock_get_settings.return_value.BRAVE_SEARCH_BASE_URL = "https://api.search.brave.com/res/v1/web/search"
    mock_get_settings.return_value.SEARCH_REQUEST_TIMEOUT_SECONDS = 10
    mock_get_settings.return_value.BRAVE_SEARCH_SAFESEARCH = "moderate"
    mock_get_settings.return_value.BRAVE_SEARCH_FRESHNESS = None
    mock_get_settings.return_value.BRAVE_SEARCH_MAX_RETRIES = 1
    
    route = respx.get("https://api.search.brave.com/res/v1/web/search")
    route.side_effect = [
        httpx.Response(500),
        httpx.Response(200, json={"web": {"results": []}})
    ]
    
    provider = BraveSearchProvider()
    results = await provider.search(sample_query, limit=1)
    assert len(results) == 0
    assert route.call_count == 2
