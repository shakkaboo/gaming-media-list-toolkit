from app.providers.search.base import SearchProvider
from app.schemas.search import GeneratedSearchQuery, SearchResult
from typing import List
from datetime import datetime, timezone

class MockSearchProvider(SearchProvider):
    provider_name = "mock"

    async def search(self, query: GeneratedSearchQuery, limit: int) -> List[SearchResult]:
        base_results = [
            SearchResult(
                url=f"https://news.example.com/{query.category.replace(' ', '')}",
                title=f"Gaming News - {query.category}",
                snippet="The latest in gaming news.",
                query_text=query.query_text,
                provider=self.provider_name,
                position=1,
                published_at=datetime.now(timezone.utc),
                language=query.language
            ),
            SearchResult(
                url=f"https://esports.example.com/{query.category.replace(' ', '')}",
                title=f"Esports Updates: {query.category}",
                snippet="Esports coverage.",
                query_text=query.query_text,
                provider=self.provider_name,
                position=2
            ),
            SearchResult(
                url=f"https://reviews.example.com/games",
                title=f"Game Reviews",
                snippet="Reviewing top games.",
                query_text=query.query_text,
                provider=self.provider_name,
                position=3
            ),
            SearchResult(
                url=f"https://news.example.com/duplicate/article",
                title=f"Duplicate Domain News",
                snippet="Another article from the same news site.",
                query_text=query.query_text,
                provider=self.provider_name,
                position=4
            ),
            SearchResult(
                url=f"https://twitter.com/GamingUser",
                title=f"GamingUser (@GamingUser) on Twitter",
                snippet="Social media profile.",
                query_text=query.query_text,
                provider=self.provider_name,
                position=5
            ),
            SearchResult(
                url=f"https://store.steampowered.com/app/123",
                title=f"Buy Game on Steam",
                snippet="Steam store page.",
                query_text=query.query_text,
                provider=self.provider_name,
                position=6
            )
        ]
        
        return base_results[:limit]
