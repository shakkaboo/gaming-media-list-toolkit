from typing import List, Optional, Dict
from app.schemas.search import (
    SearchResult,
    NormalizedCandidate,
    RejectedCandidate,
    DuplicateCandidate,
    CandidateProcessingResponse
)
from app.discovery.url_normalizer import validate_and_normalize_url, NormalizationError
from app.discovery.domain_filter import get_block_reason
from app.config import get_settings

def process_search_results(
    results: List[SearchResult],
    additional_blocked_domains: Optional[List[str]] = None,
    market: Optional[str] = None,
    language: Optional[str] = None
) -> CandidateProcessingResponse:
    settings = get_settings()
    
    additional_blocks_set = None
    if additional_blocked_domains:
        additional_blocks_set = {d.strip().lower() for d in additional_blocked_domains if d.strip()}
        
    accepted_candidates: List[NormalizedCandidate] = []
    rejected_candidates: List[RejectedCandidate] = []
    
    dedup_map: Dict[str, NormalizedCandidate] = {}
    duplicates: List[DuplicateCandidate] = []
    
    for result in results:
        try:
            norm_url, home_url, reg_domain, sub = validate_and_normalize_url(result.url)
        except NormalizationError as e:
            rejected_candidates.append(RejectedCandidate(
                original_url=result.url,
                query_text=result.query_text,
                provider=result.provider,
                result_position=result.position,
                reason_code=e.reason_code,
                safe_reason=e.safe_reason
            ))
            continue
            
        full_host = f"{sub}.{reg_domain}" if sub else reg_domain
        
        block_reason = get_block_reason(full_host, additional_blocks_set)
        if block_reason:
            rejected_candidates.append(RejectedCandidate(
                original_url=result.url,
                query_text=result.query_text,
                provider=result.provider,
                result_position=result.position,
                reason_code=block_reason,
                safe_reason="Domain is blocked by filter policy"
            ))
            continue
            
        if reg_domain in settings.MULTITENANT_HOSTING_DOMAINS:
            dedup_key = full_host
        else:
            dedup_key = reg_domain
            
        candidate = NormalizedCandidate(
            original_url=result.url,
            normalized_url=norm_url,
            homepage_url=home_url,
            registered_domain=reg_domain,
            subdomain=sub,
            title=result.title,
            snippet=result.snippet,
            query_text=result.query_text,
            provider=result.provider,
            result_position=result.position,
            market=market,
            language=language or result.language
        )
        
        if dedup_key in dedup_map:
            existing = dedup_map[dedup_key]
            
            is_equivalent = (existing.query_text == candidate.query_text and 
                             existing.result_position == candidate.result_position)
            
            override = False
            if is_equivalent:
                if existing.normalized_url.startswith("http://") and candidate.normalized_url.startswith("https://"):
                    override = True
            
            if override:
                duplicates.append(DuplicateCandidate(
                    duplicate_url=existing.original_url,
                    kept_url=candidate.original_url,
                    deduplication_key=dedup_key,
                    query_text=existing.query_text,
                    result_position=existing.result_position
                ))
                dedup_map[dedup_key] = candidate
            else:
                duplicates.append(DuplicateCandidate(
                    duplicate_url=candidate.original_url,
                    kept_url=existing.original_url,
                    deduplication_key=dedup_key,
                    query_text=candidate.query_text,
                    result_position=candidate.result_position
                ))
        else:
            dedup_map[dedup_key] = candidate
            
    accepted_candidates = list(dedup_map.values())
    
    return CandidateProcessingResponse(
        accepted=accepted_candidates,
        rejected=rejected_candidates,
        duplicates=duplicates,
        accepted_count=len(accepted_candidates),
        rejected_count=len(rejected_candidates),
        duplicate_count=len(duplicates)
    )
