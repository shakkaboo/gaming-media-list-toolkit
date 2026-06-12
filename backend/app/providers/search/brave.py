import httpx
import logging
import asyncio
from typing import List
from datetime import datetime
from app.providers.search.base import SearchProvider
from app.schemas.search import GeneratedSearchQuery, SearchResult
from app.providers.search.exceptions import (
    SearchProviderRateLimitError,
    SearchProviderTimeoutError,
    SearchProviderResponseError,
    SearchProviderConfigurationError
)
from app.config import get_settings

logger = logging.getLogger(__name__)

class BraveSearchProvider(SearchProvider):
    provider_name = "brave"
    
    def __init__(self):
        self.settings = get_settings()
        if not self.settings.BRAVE_SEARCH_API_KEY:
            raise SearchProviderConfigurationError("Brave API key is missing")

    async def search(self, query: GeneratedSearchQuery, limit: int) -> List[SearchResult]:
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "X-Subscription-Token": self.settings.BRAVE_SEARCH_API_KEY
        }
        
        params = {
            "q": query.query_text,
            "count": limit,
            "safesearch": self.settings.BRAVE_SEARCH_SAFESEARCH
        }
        
        if self.settings.BRAVE_SEARCH_FRESHNESS:
            params["freshness"] = self.settings.BRAVE_SEARCH_FRESHNESS
            
        timeout = httpx.Timeout(self.settings.SEARCH_REQUEST_TIMEOUT_SECONDS)
        
        retries = 0
        max_retries = self.settings.BRAVE_SEARCH_MAX_RETRIES
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            while True:
                try:
                    response = await client.get(
                        self.settings.BRAVE_SEARCH_BASE_URL,
                        headers=headers,
                        params=params
                    )
                except httpx.TimeoutException:
                    logger.error(f"[{self.provider_name}] Timeout fetching query: {query.query_text}")
                    raise SearchProviderTimeoutError("Search request timed out")
                except httpx.RequestError as e:
                    logger.error(f"[{self.provider_name}] Request error for query {query.query_text}: {str(e)}")
                    raise SearchProviderResponseError("Failed to execute search request")
                    
                if response.status_code in (401, 403):
                    logger.error(f"[{self.provider_name}] Authentication/Authorization error.")
                    raise SearchProviderConfigurationError("Invalid provider credentials")
                    
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "1"))
                    if retries < max_retries and retry_after <= 5:
                        retries += 1
                        logger.warning(f"[{self.provider_name}] Rate limited, sleeping for {retry_after}s ({retries}/{max_retries})")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        logger.warning(f"[{self.provider_name}] Rate limited, retries exhausted or sleep too long.")
                        raise SearchProviderRateLimitError("Rate limit exceeded")
                    
                if response.status_code in (500, 502, 503, 504):
                    if retries < max_retries:
                        retries += 1
                        logger.warning(f"[{self.provider_name}] Transient error {response.status_code}, retrying ({retries}/{max_retries})")
                        continue
                    else:
                        logger.error(f"[{self.provider_name}] Transient error {response.status_code}, max retries exceeded.")
                        raise SearchProviderResponseError(f"Provider returned transient error {response.status_code}")
                
                if response.status_code >= 400:
                    logger.error(f"[{self.provider_name}] Bad response {response.status_code}")
                    raise SearchProviderResponseError(f"Provider returned error {response.status_code}")
                    
                break

        try:
            data = response.json()
        except ValueError:
            logger.error(f"[{self.provider_name}] Invalid JSON response")
            raise SearchProviderResponseError("Invalid JSON response from provider")
            
        web_results = data.get("web", {}).get("results", [])
        results = []
        
        position = 1
        for item in web_results:
            url = item.get("url")
            title = item.get("title")
            if not url or not title:
                continue
                
            published_at = None
            page_age = item.get("page_age")
            if page_age:
                try:
                    published_at = datetime.fromisoformat(page_age.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
            
            results.append(SearchResult(
                url=url,
                title=title,
                snippet=item.get("description"),
                query_text=query.query_text,
                provider=self.provider_name,
                position=position,
                published_at=published_at,
                language=item.get("language") or query.language
            ))
            position += 1
            
        return results
