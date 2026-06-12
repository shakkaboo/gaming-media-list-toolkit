from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime

class GeneratedSearchQuery(BaseModel):
    query_text: str = Field(..., max_length=500)
    category: str
    market: str
    language: str
    template_name: str

class SearchResult(BaseModel):
    url: str
    title: str
    snippet: Optional[str] = None
    query_text: str
    provider: str
    position: int
    published_at: Optional[datetime] = None
    language: Optional[str] = None

class SearchPreviewError(BaseModel):
    query_text: str
    error_type: str
    message: str

class QueryGenerationRequest(BaseModel):
    market: str = Field(..., min_length=1, max_length=100)
    language: str = Field(..., min_length=1, max_length=50)
    categories: List[str] = Field(..., min_length=1, max_length=20)
    keywords: Optional[List[str]] = Field(default=None, max_length=20)
    maximum_queries: Optional[int] = Field(None, ge=1, le=100)

    @field_validator("market", "language")
    @classmethod
    def clean_strings(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Value cannot be blank")
        return cleaned

    @field_validator("categories", "keywords")
    @classmethod
    def clean_lists(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return v
        cleaned_list = []
        seen = set()
        for item in v:
            c = item.strip()
            if not c:
                continue
            if len(c) > 100:
                raise ValueError("List items must not exceed 100 characters")
            clower = c.lower()
            if clower not in seen:
                seen.add(clower)
                cleaned_list.append(c)
        return cleaned_list

    @field_validator("categories")
    @classmethod
    def require_categories(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one valid category is required")
        return v

class QueryGenerationResponse(BaseModel):
    queries: List[GeneratedSearchQuery]
    total: int

class SearchPreviewRequest(QueryGenerationRequest):
    results_per_query: int = Field(..., ge=1, le=20)
    provider: Optional[str] = Field(None, pattern="^(?i)(mock|brave)$")

class SearchPreviewResponse(BaseModel):
    generated_queries: List[GeneratedSearchQuery]
    results: List[SearchResult]
    result_count: int
    provider: str
    errors: List[SearchPreviewError]
