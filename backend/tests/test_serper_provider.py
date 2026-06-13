import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
from app.providers.search.serper import SerperProvider
from app.providers.search.exceptions import (
    SearchProviderConfigurationError,
    SearchProviderRateLimitError,
    SearchProviderResponseError,
    SearchProviderTimeoutError,
    SearchProviderError
)
from app.schemas.search import GeneratedSearchQuery
from app.config import Settings
from app.providers.search.factory import get_search_provider

@pytest.fixture
def mock_serper_settings():
    return Settings(
        SEARCH_PROVIDER="serper",
        SERPER_API_KEY="test-serper-key",
        SERPER_BASE_URL="https://google.serper.dev",
        SERPER_TIMEOUT_SECONDS=10
    )

@pytest.fixture
def serper_provider(mock_serper_settings):
    with patch("app.providers.search.serper.get_settings", return_value=mock_serper_settings):
        yield SerperProvider()

@pytest.fixture
def sample_query():
    return GeneratedSearchQuery(
        query_text="gaming sites",
        category="general",
        market="US",
        language="en",
        template_name="test"
    )

@pytest.mark.asyncio
async def test_serper_success(serper_provider, sample_query):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "organic": [
            {
                "title": "Site 1",
                "link": "https://site1.com",
                "snippet": "Snippet 1",
                "position": 1
            },
            {
                "title": "Site 2",
                "link": "https://site2.com",
                "snippet": "Snippet 2",
                "position": 2
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    # We need to mock the context manager
    mock_client_instance = MagicMock()
    mock_client_instance.__aenter__.return_value = mock_client
    
    with patch("httpx.AsyncClient", return_value=mock_client_instance) as mock_httpx:
        results = await serper_provider.search(sample_query, limit=10)

        mock_client.post.assert_called_once()
        args, kwargs = mock_client.post.call_args
        
        assert args[0] == "https://google.serper.dev/search"
        assert kwargs["json"] == {"q": "gaming sites", "gl": "us", "hl": "en", "num": 10, "page": 1}
        assert kwargs["headers"]["X-API-KEY"] == "test-serper-key"
        
        assert len(results) == 2
        assert results[0].url == "https://site1.com"
        assert results[0].title == "Site 1"
        assert results[0].snippet == "Snippet 1"
        assert results[0].position == 1
        assert results[0].query_text == "gaming sites"
        assert results[0].provider == "serper"
        assert results[0].language == "en"

@pytest.mark.asyncio
async def test_serper_empty_organic(serper_provider, sample_query):
    mock_response = MagicMock()
    mock_response.json.return_value = {} # Missing organic
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client_instance = MagicMock()
    mock_client_instance.__aenter__.return_value = mock_client
    
    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        results = await serper_provider.search(sample_query, limit=10)
        assert len(results) == 0

@pytest.mark.asyncio
async def test_serper_malformed_items_skipped(serper_provider, sample_query):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "organic": [
            {"title": "No Link"}, # Missing link
            {"link": "ftp://bad-scheme.com"}, # Bad scheme
            {"link": "https://site3.com", "title": 123}, # Bad title type
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client_instance = MagicMock()
    mock_client_instance.__aenter__.return_value = mock_client
    
    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        results = await serper_provider.search(sample_query, limit=10)
        assert len(results) == 1
        assert results[0].url == "https://site3.com"
        assert results[0].title == "" # Cast safely

@pytest.mark.asyncio
async def test_serper_auth_error(serper_provider, sample_query):
    mock_response = MagicMock()
    mock_response.status_code = 403
    
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.HTTPStatusError("403 Forbidden", request=MagicMock(), response=mock_response))
    mock_client_instance = MagicMock()
    mock_client_instance.__aenter__.return_value = mock_client
    
    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        with pytest.raises(SearchProviderConfigurationError):
            await serper_provider.search(sample_query, limit=10)

@pytest.mark.asyncio
async def test_serper_rate_limit(serper_provider, sample_query):
    mock_response = MagicMock()
    mock_response.status_code = 429
    
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.HTTPStatusError("429 Too Many Requests", request=MagicMock(), response=mock_response))
    mock_client_instance = MagicMock()
    mock_client_instance.__aenter__.return_value = mock_client
    
    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        with pytest.raises(SearchProviderRateLimitError):
            await serper_provider.search(sample_query, limit=10)

@pytest.mark.asyncio
async def test_serper_unavailable(serper_provider, sample_query):
    mock_response = MagicMock()
    mock_response.status_code = 502
    
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.HTTPStatusError("502 Bad Gateway", request=MagicMock(), response=mock_response))
    mock_client_instance = MagicMock()
    mock_client_instance.__aenter__.return_value = mock_client
    
    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        with pytest.raises(SearchProviderResponseError):
            await serper_provider.search(sample_query, limit=10)

@pytest.mark.asyncio
async def test_serper_timeout(serper_provider, sample_query):
    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
    mock_client_instance = MagicMock()
    mock_client_instance.__aenter__.return_value = mock_client
    
    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        with pytest.raises(SearchProviderTimeoutError):
            await serper_provider.search(sample_query, limit=10)

@pytest.mark.asyncio
async def test_serper_invalid_json(serper_provider, sample_query):
    mock_response = MagicMock()
    mock_response.json.side_effect = Exception("Invalid JSON")
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client_instance = MagicMock()
    mock_client_instance.__aenter__.return_value = mock_client
    
    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        with pytest.raises(SearchProviderError, match="invalid JSON"):
            await serper_provider.search(sample_query, limit=10)

@pytest.mark.asyncio
async def test_serper_blank_market_language_raises(serper_provider, sample_query):
    sample_query.market = "   "
    with pytest.raises(SearchProviderConfigurationError, match="Market country code is required"):
        await serper_provider.search(sample_query, limit=10)
        
    sample_query.market = "US"
    sample_query.language = ""
    with pytest.raises(SearchProviderConfigurationError, match="Language code is required"):
        await serper_provider.search(sample_query, limit=10)

def test_serper_factory(mock_serper_settings):
    with patch("app.providers.search.factory.get_settings", return_value=mock_serper_settings):
        provider = get_search_provider("serper")
        assert isinstance(provider, SerperProvider)
        assert provider.provider_name == "serper"

def test_unknown_provider_factory(mock_serper_settings):
    with patch("app.providers.search.factory.get_settings", return_value=mock_serper_settings):
        with pytest.raises(SearchProviderConfigurationError):
            get_search_provider("unknown")
