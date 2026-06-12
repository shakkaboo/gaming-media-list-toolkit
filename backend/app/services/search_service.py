import asyncio
from typing import List, Tuple
from app.schemas.search import (
    SearchPreviewRequest,
    SearchPreviewResponse,
    SearchResult,
    SearchPreviewError,
    QueryGenerationRequest,
    QueryGenerationResponse,
    CandidatePreviewRequest,
    CandidatePreviewResponse
)
from app.services.candidate_processor import process_search_results
from app.discovery.query_generator import generate_search_queries
from app.providers.search.factory import get_search_provider
from app.providers.search.exceptions import SearchProviderError
from app.config import get_settings

def preview_queries(request: QueryGenerationRequest) -> QueryGenerationResponse:
    queries = generate_search_queries(
        market=request.market,
        language=request.language,
        categories=request.categories,
        keywords=request.keywords,
        maximum_queries=request.maximum_queries
    )
    return QueryGenerationResponse(queries=queries, total=len(queries))

async def preview_search(request: SearchPreviewRequest) -> SearchPreviewResponse:
    queries = generate_search_queries(
        market=request.market,
        language=request.language,
        categories=request.categories,
        keywords=request.keywords,
        maximum_queries=request.maximum_queries
    )
    
    provider = get_search_provider(request.provider)
    settings = get_settings()
    semaphore = asyncio.Semaphore(settings.MAX_SEARCH_CONCURRENCY)
    
    results: List[SearchResult] = []
    errors: List[SearchPreviewError] = []
    
    async def fetch_for_query(query, index: int) -> Tuple[int, List[SearchResult], List[SearchPreviewError]]:
        async with semaphore:
            try:
                res = await provider.search(query, request.results_per_query)
                return index, res, []
            except SearchProviderError as e:
                err = SearchPreviewError(
                    query_text=query.query_text,
                    error_type=e.__class__.__name__,
                    message=str(e)
                )
                return index, [], [err]
            except Exception as e:
                err = SearchPreviewError(
                    query_text=query.query_text,
                    error_type="UnexpectedError",
                    message="An unexpected error occurred during search"
                )
                return index, [], [err]

    tasks = [fetch_for_query(q, i) for i, q in enumerate(queries)]
    completed = await asyncio.gather(*tasks)
    
    completed.sort(key=lambda x: x[0])
    
    for _, res_list, err_list in completed:
        results.extend(res_list)
        errors.extend(err_list)
        
    return SearchPreviewResponse(
        generated_queries=queries,
        results=results,
        result_count=len(results),
        provider=provider.provider_name,
        errors=errors
    )

async def preview_candidates(request: CandidatePreviewRequest) -> CandidatePreviewResponse:
    search_preview_resp = await preview_search(request)

    processing_resp = process_search_results(
        results=search_preview_resp.results,
        additional_blocked_domains=request.additional_blocked_domains,
        market=request.market,
        language=request.language
    )

    rejected_out = processing_resp.rejected if request.include_rejected else None
    duplicates_out = processing_resp.duplicates if request.include_duplicates else None

    return CandidatePreviewResponse(
        generated_queries=search_preview_resp.generated_queries,
        raw_result_count=search_preview_resp.result_count,
        accepted_candidates=processing_resp.accepted,
        rejected_candidates=rejected_out,
        duplicates=duplicates_out,
        accepted_count=processing_resp.accepted_count,
        rejected_count=processing_resp.rejected_count,
        duplicate_count=processing_resp.duplicate_count,
        provider=search_preview_resp.provider,
        errors=search_preview_resp.errors
    )
