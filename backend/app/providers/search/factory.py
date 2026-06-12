from app.providers.search.base import SearchProvider
from app.providers.search.mock import MockSearchProvider
from app.providers.search.brave import BraveSearchProvider
from app.providers.search.exceptions import SearchProviderConfigurationError
from app.config import get_settings

def get_search_provider(provider_name: str | None = None) -> SearchProvider:
    settings = get_settings()
    effective_name = (provider_name or settings.SEARCH_PROVIDER).lower()
    
    if effective_name == "mock":
        return MockSearchProvider()
    elif effective_name == "brave":
        return BraveSearchProvider()
    else:
        raise SearchProviderConfigurationError(f"Unknown search provider: {effective_name}")
