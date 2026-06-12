from abc import ABC, abstractmethod
from typing import List
from app.schemas.search import GeneratedSearchQuery, SearchResult

class SearchProvider(ABC):
    provider_name: str

    @abstractmethod
    async def search(
        self,
        query: GeneratedSearchQuery,
        limit: int,
    ) -> List[SearchResult]:
        pass
