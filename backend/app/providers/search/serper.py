import httpx
import logging
from typing import List, Dict, Any
from app.providers.search.base import SearchProvider
from app.schemas.search import GeneratedSearchQuery, SearchResult
from app.providers.search.exceptions import (
    SearchProviderConfigurationError,
    SearchProviderRateLimitError,
    SearchProviderResponseError,
    SearchProviderTimeoutError,
    SearchProviderError
)
from app.config import get_settings

logger = logging.getLogger(__name__)

class SerperProvider(SearchProvider):
    provider_name = "serper"

    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.SERPER_API_KEY
        self.base_url = self.settings.SERPER_BASE_URL
        self.timeout = self.settings.SERPER_TIMEOUT_SECONDS

    async def search(self, query: GeneratedSearchQuery, limit: int) -> List[SearchResult]:
        if not self.api_key:
            raise SearchProviderConfigurationError("SERPER_API_KEY is not configured")

        url = f"{self.base_url.rstrip('/')}/search"
        
        # Mapping: market/country -> gl, language -> hl
        if not query.market or not query.market.strip():
            raise SearchProviderConfigurationError("Market country code is required for Serper search")
        if not query.language or not query.language.strip():
            raise SearchProviderConfigurationError("Language code is required for Serper search")

        gl = query.market.strip().lower()
        hl = query.language.strip().lower()
        
        # Query limit processing.
        # Ensure num is at least 1, max is defined by Serper, we can cap it at 100 for safety, 
        # but respect the job's requested limit.
        num = max(1, min(limit, 100))

        payload = {
            "q": query.query_text,
            "gl": gl,
            "hl": hl,
            "num": num,
            "page": query.page
        }
        
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status in (401, 403):
                    raise SearchProviderConfigurationError("Invalid or missing Serper API key")
                elif status == 429:
                    raise SearchProviderRateLimitError("Serper API rate limit exceeded")
                elif status >= 500:
                    raise SearchProviderResponseError(f"Serper API is currently unavailable (Status {status})")
                else:
                    raise SearchProviderResponseError(f"Serper API returned unexpected status {status}")
            except httpx.TimeoutException:
                raise SearchProviderTimeoutError("Connection to Serper API timed out")
            except httpx.RequestError as e:
                raise SearchProviderError("Network connection to Serper API failed")

            try:
                data = response.json()
            except Exception:
                raise SearchProviderError("Serper API returned invalid JSON")

        return self._map_results(data, query.query_text, query.language)

    def _map_results(self, data: Dict[str, Any], query_text: str, language: str) -> List[SearchResult]:
        organic_results = data.get("organic", [])
        if not organic_results or not isinstance(organic_results, list):
            return []

        results = []
        seen_urls = set()

        for item in organic_results:
            if not isinstance(item, dict):
                continue
                
            link = item.get("link")
            if not link or not isinstance(link, str) or not link.startswith("http"):
                continue

            if link in seen_urls:
                continue
            seen_urls.add(link)

            title = item.get("title", "")
            snippet = item.get("snippet", "")
            position = item.get("position", len(results) + 1)
            
            try:
                position = int(position)
            except (ValueError, TypeError):
                position = len(results) + 1

            results.append(SearchResult(
                url=link,
                title=title if isinstance(title, str) else "",
                snippet=snippet if isinstance(snippet, str) else "",
                query_text=query_text,
                provider=self.provider_name,
                position=position,
                language=language
            ))

        return results
