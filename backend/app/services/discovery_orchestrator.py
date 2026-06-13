import asyncio
import logging
from typing import List, Optional, Set, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from dataclasses import dataclass

from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.models.enums import DiscoveryJobStatus, ProcessingStage
from app.schemas.search import (
    NormalizedCandidate,
    SearchPreviewError,
    GeneratedSearchQuery
)
from app.schemas.fetch import FetchRequest, FetchedPage
from app.schemas.verification import VerificationRequest, VerificationResult
from app.schemas.discovery_orchestration import DiscoveryRunSummary
from app.services.fetch_service import FetchService
from app.services.verification_service import VerificationService
from app.services.discovery_persistence import (
    DiscoveryPersistenceService,
    InvalidJobTransition,
    JobNotFound,
    IncompleteJobFinalization,
    WebsiteUpsertResult
)
from app.services.candidate_processor import process_search_results
from app.providers.search.factory import get_search_provider
from app.discovery.query_generator import generate_search_queries

logger = logging.getLogger(__name__)

class DiscoveryOrchestrator:
    def __init__(
        self,
        *,
        session_factory: sessionmaker,
        settings: Settings,
        fetch_service: FetchService,
        verification_service: VerificationService
    ):
        self.session_factory = session_factory
        self.settings = settings
        self.fetch_service = fetch_service
        self.verification_service = verification_service

    async def run_job(self, job_id: UUID) -> DiscoveryRunSummary:
        attempt_number = 0
        try:
            with self.session_factory() as session:
                persistence = DiscoveryPersistenceService(session)
                job = persistence.start_job(job_id)
                attempt_number = job.attempt_number
                job_categories = job.categories
                job_market = job.target_market
                job_language = job.language
                max_queries = job.maximum_queries
        except InvalidJobTransition as e:
            logger.warning(f"Invalid job transition for {job_id}: {e}")
            return DiscoveryRunSummary(
                job_id=job_id, attempt_number=0, final_status="failed",
                queries_total=0, queries_executed=0, queries_skipped=0,
                websites_discovered=0, websites_processed=0, websites_verified=0,
                websites_uncertain=0, websites_rejected=0, errors_count=0
            )
        except JobNotFound:
            logger.warning(f"Job {job_id} not found")
            return DiscoveryRunSummary(
                job_id=job_id, attempt_number=0, final_status="failed",
                queries_total=0, queries_executed=0, queries_skipped=0,
                websites_discovered=0, websites_processed=0, websites_verified=0,
                websites_uncertain=0, websites_rejected=0, errors_count=0
            )
        except Exception as e:
            logger.exception(f"Failed to start job {job_id}")
            raise

        try:
            return await self._run_job_internal(
                job_id=job_id,
                attempt_number=attempt_number,
                categories=job_categories,
                market=job_market,
                language=job_language,
                max_queries=max_queries
            )
        except Exception as e:
            logger.exception(f"Fatal error in orchestrator for job {job_id}: {e}")
            with self.session_factory() as session:
                from sqlalchemy import update
                from app.models.discovery_job import DiscoveryJob
                session.execute(
                    update(DiscoveryJob)
                    .where(DiscoveryJob.id == job_id, DiscoveryJob.status == DiscoveryJobStatus.running)
                    .values(status=DiscoveryJobStatus.failed, completed_at=datetime.now(timezone.utc))
                )
                session.commit()
            raise

    async def _run_job_internal(self, job_id: UUID, attempt_number: int, categories: List[str], market: str, language: str, max_queries: int) -> DiscoveryRunSummary:
        try:
            generated = generate_search_queries(
                market=market,
                language=language,
                categories=categories,
                keywords=[],
                maximum_queries=max_queries
            )
        except Exception as e:
            with self.session_factory() as session:
                persistence = DiscoveryPersistenceService(session)
                persistence.record_processing_error(
                    job_id=job_id,
                    attempt_number=attempt_number,
                    stage=ProcessingStage.query_generation,
                    error_code="query_generation_failed",
                    safe_message="Failed to generate queries",
                    retryable=False
                )
                from sqlalchemy import update
                from app.models.discovery_job import DiscoveryJob
                session.execute(
                    update(DiscoveryJob)
                    .where(DiscoveryJob.id == job_id, DiscoveryJob.status == DiscoveryJobStatus.running)
                    .values(status=DiscoveryJobStatus.failed, completed_at=datetime.now(timezone.utc))
                )
                session.commit()
            return await self._build_summary(job_id, attempt_number)

        with self.session_factory() as session:
            persistence = DiscoveryPersistenceService(session)
            db_queries = persistence.persist_generated_queries(job_id, generated)
            query_tuples = [
                (
                    q.id,
                    q.query_text,
                    getattr(q.status, 'value', str(q.status)),
                    q.provider,
                    q.requested_limit,
                    q.category or "unknown"
                ) for q in db_queries
            ]

        websites_to_process = []
        for q_id, q_text, q_status, q_provider, q_limit, q_category in query_tuples:
            if q_status == "completed":
                continue

            provider = get_search_provider(q_provider)
            provider_query = GeneratedSearchQuery(
                query_text=q_text,
                category=q_category,
                market=market,
                language=language,
                template_name="persisted_query"
            )
            try:
                results = await provider.search(provider_query, q_limit)
                processing_resp = process_search_results(
                    results=results,
                    market=market,
                    language=language
                )

                with self.session_factory() as session:
                    persistence = DiscoveryPersistenceService(session)
                    for candidate in processing_resp.accepted:
                        upsert_res = persistence.upsert_website(candidate)

                        from app.models.discovery_job import DiscoveryJob
                        from app.models.search_query import SearchQuery
                        job = session.get(DiscoveryJob, job_id)
                        query = session.get(SearchQuery, q_id)

                        persistence.persist_discovery_source(
                            job=job,
                            query=query,
                            website=upsert_res.website,
                            candidate=candidate
                        )
                        websites_to_process.append((upsert_res.website.id, candidate))

                    persistence.mark_query_completed(q_id, len(processing_resp.accepted))
                    session.commit()
            except Exception as e:
                with self.session_factory() as session:
                    persistence = DiscoveryPersistenceService(session)
                    error_code = getattr(e, "__class__", type(e)).__name__
                    if "timeout" in str(e).lower():
                        error_code = "search_timeout"
                    persistence.record_processing_error(
                        job_id=job_id,
                        attempt_number=attempt_number,
                        stage=ProcessingStage.search,
                        error_code=error_code,
                        safe_message=f"Search failed: {str(e)}",
                        retryable=True,
                        search_query_id=q_id
                    )
                    persistence.mark_query_failed(q_id, str(e))
                    session.commit()

        seen_websites = set()
        unique_websites = []
        for w_id, cand in websites_to_process:
            if w_id not in seen_websites:
                seen_websites.add(w_id)
                unique_websites.append((w_id, cand))

        for website_id, candidate in unique_websites:
            fetch_req = FetchRequest(
                candidates=[candidate],
                maximum_candidates=1,
                use_homepage_url=True,
                include_html_preview=False
            )

            page = None
            verif_result = None

            try:
                fetched_pages, _ = await self.fetch_service.fetch_pages(fetch_req)
                if fetched_pages:
                    page = fetched_pages[0]
            except Exception as e:
                error_code = "fetch_crash"
                safe_msg = str(e)[:200]
                with self.session_factory() as session:
                    persistence = DiscoveryPersistenceService(session)
                    persistence.record_processing_error(
                        job_id=job_id,
                        attempt_number=attempt_number,
                        stage=ProcessingStage.fetching,
                        error_code=error_code,
                        safe_message=safe_msg,
                        retryable=True,
                        website_id=website_id
                    )
                    session.commit()

                from app.schemas.verification import VerificationReason
                verif_result = VerificationResult(
                    requested_url=candidate.homepage_url or f"https://{candidate.registered_domain}",
                    final_url=candidate.homepage_url or f"https://{candidate.registered_domain}",
                    registered_domain=candidate.registered_domain,
                    score=0,
                    verification_status="uncertain",
                    confidence=0.0,
                    gaming_relevance_score=0,
                    editorial_structure_score=0,
                    activity_score=0,
                    publication_identity_score=0,
                    negative_penalty=0,
                    negative_reasons=[
                        VerificationReason(code=error_code, message=safe_msg, weight=100, evidence=[])
                    ],
                    activity_status="inactive",
                    article_count_estimate=0,
                    classifier_version="fallback_v1",
                    analysed_at=datetime.now(timezone.utc),
                    fetch_success=False
                )

            if page and not page.success and not verif_result:
                # Handle explicit fetch failure
                with self.session_factory() as session:
                    persistence = DiscoveryPersistenceService(session)
                    persistence.record_processing_error(
                        job_id=job_id,
                        attempt_number=attempt_number,
                        stage=ProcessingStage.fetching,
                        error_code=page.error_code or "fetch_failed",
                        safe_message=page.safe_error or "Fetch failed",
                        retryable="timeout" in (page.error_code or "").lower() or "timeout" in (page.safe_error or "").lower(),
                        website_id=website_id
                    )
                    session.commit()

                from app.schemas.verification import VerificationReason
                verif_result = VerificationResult(
                    requested_url=page.requested_url,
                    final_url=page.final_url or page.requested_url,
                    registered_domain=page.registered_domain or candidate.registered_domain,
                    score=0,
                    verification_status="uncertain",
                    confidence=0.0,
                    gaming_relevance_score=0,
                    editorial_structure_score=0,
                    activity_score=0,
                    publication_identity_score=0,
                    negative_penalty=0,
                    negative_reasons=[
                        VerificationReason(
                            code="fetch_failed",
                            message=page.safe_error or "Fetch failed",
                            weight=100,
                            evidence=[page.error_code or "unknown"]
                        )
                    ],
                    activity_status="inactive",
                    article_count_estimate=0,
                    classifier_version="fallback_v1",
                    analysed_at=datetime.now(timezone.utc),
                    fetch_success=False,
                    fetch_error_code=page.error_code
                )

            if page and page.success and not verif_result:
                try:
                    verif_request = VerificationRequest(candidates=[candidate])
                    verif_result = await asyncio.to_thread(
                        self.verification_service._verify_page_sync,
                        page,
                        datetime.now(timezone.utc),
                        verif_request
                    )
                except Exception as e:
                    error_code = "verification_crash"
                    safe_msg = str(e)[:200]
                    with self.session_factory() as session:
                        persistence = DiscoveryPersistenceService(session)
                        persistence.record_processing_error(
                            job_id=job_id,
                            attempt_number=attempt_number,
                            stage=ProcessingStage.verification,
                            error_code=error_code,
                            safe_message=safe_msg,
                            retryable=False,
                            website_id=website_id
                        )
                        session.commit()

                    from app.schemas.verification import VerificationReason
                    verif_result = VerificationResult(
                        requested_url=page.requested_url,
                        final_url=page.final_url,
                        registered_domain=page.registered_domain,
                        score=0,
                        verification_status="uncertain",
                        confidence=0.0,
                        gaming_relevance_score=0,
                        editorial_structure_score=0,
                        activity_score=0,
                        publication_identity_score=0,
                        negative_penalty=0,
                        negative_reasons=[
                            VerificationReason(code=error_code, message=safe_msg, weight=100, evidence=[])
                        ],
                        activity_status="inactive",
                        article_count_estimate=0,
                        classifier_version="fallback_v1",
                        analysed_at=datetime.now(timezone.utc),
                        fetch_success=True
                    )

            with self.session_factory() as session:
                persistence = DiscoveryPersistenceService(session)
                from app.models.website import Website
                from app.models.discovery_job import DiscoveryJob
                website = session.get(Website, website_id)
                job = session.get(DiscoveryJob, job_id)

                class VerificationResultAdapter:
                    def __init__(self, vr):
                        self.status = vr.verification_status
                        self.score = vr.score
                        self.confidence = vr.confidence
                        self.positive_reasons = getattr(vr, 'positive_reasons', [])
                        self.negative_reasons = getattr(vr, 'negative_reasons', [])
                        self.detected_categories = getattr(vr, 'detected_categories', [])
                        self.is_active = (vr.activity_status == "active")
                        self.classifier_version = vr.classifier_version
                        class Meta:
                            title = None
                            description = None
                        self.metadata = Meta()

                adapter = VerificationResultAdapter(verif_result)

                persistence.persist_verification(
                    job=job,
                    website=website,
                    result=adapter
                )
                session.commit()

        with self.session_factory() as session:
            persistence = DiscoveryPersistenceService(session)
            persistence.recalculate_job_counters(job_id)
            session.commit()

        try:
            with self.session_factory() as session:
                persistence = DiscoveryPersistenceService(session)
                persistence.finalize_job(job_id)
                session.commit()
        except IncompleteJobFinalization as e:
            logger.error(f"Incomplete job finalization for {job_id}: {e}")

        return await self._build_summary(job_id, attempt_number)

    async def _build_summary(self, job_id: UUID, attempt_number: int) -> DiscoveryRunSummary:
        with self.session_factory() as session:
            from app.models.discovery_job import DiscoveryJob
            from app.models.search_query import SearchQuery
            from app.models.processing_error import ProcessingError
            from sqlalchemy import select, func

            job = session.get(DiscoveryJob, job_id)

            queries_total = session.execute(
                select(func.count()).select_from(SearchQuery).where(SearchQuery.discovery_job_id == job_id)
            ).scalar() or 0

            queries_executed = session.execute(
                select(func.count()).select_from(SearchQuery).where(
                    SearchQuery.discovery_job_id == job_id,
                    SearchQuery.status.in_(["completed", "failed"])
                )
            ).scalar() or 0

            queries_skipped = session.execute(
                select(func.count()).select_from(SearchQuery).where(
                    SearchQuery.discovery_job_id == job_id,
                    SearchQuery.status == "pending"
                )
            ).scalar() or 0

            errors_count = session.execute(
                select(func.count()).select_from(ProcessingError).where(ProcessingError.discovery_job_id == job_id)
            ).scalar() or 0

            return DiscoveryRunSummary(
                job_id=job_id,
                attempt_number=attempt_number,
                final_status=getattr(job.status, "value", str(job.status)),
                queries_total=queries_total,
                queries_executed=queries_executed,
                queries_skipped=queries_skipped,
                websites_discovered=job.candidates_found,
                websites_processed=job.sites_fetched,
                websites_verified=job.sites_verified,
                websites_uncertain=job.websites_uncertain,
                websites_rejected=job.sites_rejected,
                errors_count=errors_count
            )
