class SearchProviderError(Exception):
    pass

class SearchProviderConfigurationError(SearchProviderError):
    pass

class SearchProviderRateLimitError(SearchProviderError):
    pass

class SearchProviderTimeoutError(SearchProviderError):
    pass

class SearchProviderResponseError(SearchProviderError):
    pass
