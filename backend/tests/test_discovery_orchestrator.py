import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime, timezone
from pydantic import ValidationError

from app.models.base import Base
from app.models.discovery_job import DiscoveryJob
from app.models.enums import DiscoveryJobStatus, VerificationStatus, ProcessingStage
from app.models.website import Website
from app.models.search_query import SearchQuery
from app.models.discovery_source import DiscoverySource
from app.models.processing_error import ProcessingError

from app.schemas.search import NormalizedCandidate, SearchResult, CandidateProcessingResponse
from app.schemas.fetch import FetchedPage
from app.schemas.verification import VerificationResult
from app.services.fetch_service import FetchService
from app.services.verification_service import VerificationService
from app.services.discovery_orchestrator import DiscoveryOrchestrator
from app.services.discovery_persistence import DiscoveryPersistenceService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine

@pytest.fixture
def session_factory(db_engine):
    return sessionmaker(bind=db_engine)

@pytest.fixture
def db_session(session_factory):
    with session_factory() as session:
        yield session

@pytest.fixture
def pending_job(db_session):
    job = DiscoveryJob(
        id=uuid4(),
        status=DiscoveryJobStatus.pending,
        target_market="US",
        language="en",
        categories=["indie"],
        maximum_queries=5,
        minimum_pageviews=0,
        results_per_query=10,
        search_provider="mock",
        traffic_provider="mock"
    )
    db_session.add(job)
    db_session.commit()
    return job

@pytest.fixture
def mock_fetch_service():
    return MagicMock(spec=FetchService)

@pytest.fixture
def mock_verification_service():
    return MagicMock(spec=VerificationService)

@pytest.fixture
def orchestrator(session_factory, mock_fetch_service, mock_verification_service):
    return DiscoveryOrchestrator(
        session_factory=session_factory,
        settings=MagicMock(),
        fetch_service=mock_fetch_service,
        verification_service=mock_verification_service
    )

@patch("app.services.discovery_orchestrator.get_search_provider")
@patch("app.services.discovery_orchestrator.process_search_results")
@pytest.mark.asyncio
async def test_successful_sequential_flow(mock_process, mock_get_provider, orchestrator, pending_job, db_session, mock_fetch_service, mock_verification_service):
    # Mock search provider
    mock_provider = AsyncMock()
    mock_provider.search.return_value = [SearchResult(url="https://example.com/indie", title="Example", snippet="...", domain="example.com", query_text="indie games", provider="mock", position=1)]
    mock_get_provider.return_value = mock_provider

    # Mock candidate processing
    candidate = NormalizedCandidate(
        normalized_url="example.com", registered_domain="example.com", homepage_url="https://example.com",
        original_url="https://example.com/indie", title="Example", query_text="indie games", provider="mock", result_position=1
    )
    mock_process.return_value = CandidateProcessingResponse(
        accepted=[candidate], rejected=[], duplicates=[], accepted_count=1, rejected_count=0, duplicate_count=0
    )

    # Mock fetching
    fetched_page = FetchedPage(
        requested_url="https://example.com", final_url="https://example.com", registered_domain="example.com",
        status_code=200, content_type="text/html", content_length=1000, html="<html></html>", title="Test",
        fetched_at=datetime.now(timezone.utc), redirect_chain=[], redirect_count=0, elapsed_ms=100, success=True,
        error_code=None, safe_error=None
    )
    mock_fetch_service.fetch_pages.return_value = ([fetched_page], 0)

    # Mock verification
    ver_res = VerificationResult(
        requested_url="https://example.com", final_url="https://example.com", registered_domain="example.com",
        score=85, verification_status="verified", confidence=0.9, gaming_relevance_score=80,
        editorial_structure_score=90, activity_score=80, publication_identity_score=90, negative_penalty=0,
        activity_status="active", article_count_estimate=10, classifier_version="v1",
        analysed_at=datetime.now(timezone.utc), fetch_success=True
    )
    mock_verification_service._verify_page_sync.return_value = ver_res

    summary = await orchestrator.run_job(pending_job.id)

    errors = db_session.query(ProcessingError).filter_by(discovery_job_id=pending_job.id).all()
    if summary.final_status != "completed":
        print([e.message for e in errors])

    assert summary.final_status == "completed"
    assert summary.websites_discovered == 1
    assert summary.errors_count == 0

    db_session.expire_all()
    job_db = db_session.get(DiscoveryJob, pending_job.id)
    assert job_db.candidates_found == 1
    assert job_db.sites_verified == 1

@patch("app.services.discovery_orchestrator.get_search_provider")
@pytest.mark.asyncio
async def test_search_provider_failure_isolated(mock_get_provider, orchestrator, pending_job, db_session):
    mock_provider = AsyncMock()
    mock_provider.search.side_effect = Exception("Provider timeout")
    mock_get_provider.return_value = mock_provider

    summary = await orchestrator.run_job(pending_job.id)

    assert summary.final_status == "completed_with_errors"
    assert summary.errors_count > 0

    errors = db_session.query(ProcessingError).filter_by(discovery_job_id=pending_job.id).all()
    assert len(errors) > 0
    assert errors[0].stage == ProcessingStage.search
    assert errors[0].message == "Search failed: Provider timeout"

@patch("app.services.discovery_orchestrator.get_search_provider")
@patch("app.services.discovery_orchestrator.process_search_results")
@pytest.mark.asyncio
async def test_fetch_failure_records_error(mock_process, mock_get_provider, orchestrator, pending_job, db_session, mock_fetch_service):
    # Mock search
    mock_provider = AsyncMock()
    mock_provider.search.return_value = [SearchResult(url="https://example.com/indie", title="Example", snippet="...", domain="example.com", query_text="indie games", provider="mock", position=1)]
    mock_get_provider.return_value = mock_provider

    candidate = NormalizedCandidate(
        normalized_url="example.com", registered_domain="example.com", homepage_url="https://example.com",
        original_url="https://example.com/indie", title="Example", query_text="indie games", provider="mock", result_position=1
    )
    mock_process.return_value = CandidateProcessingResponse(
        accepted=[candidate], rejected=[], duplicates=[], accepted_count=1, rejected_count=0, duplicate_count=0
    )

    # Mock fetching to fail
    fetched_page = FetchedPage(
        requested_url="https://example.com", final_url="https://example.com", registered_domain="example.com",
        status_code=500, content_type=None, content_length=None, html=None, title=None,
        fetched_at=datetime.now(timezone.utc), redirect_chain=[], redirect_count=0, elapsed_ms=100, success=False,
        error_code="http_500", safe_error="Server error"
    )
    mock_fetch_service.fetch_pages.return_value = ([fetched_page], 0)

    summary = await orchestrator.run_job(pending_job.id)

    assert summary.final_status == "completed_with_errors"
    assert summary.errors_count == 1

    error = db_session.query(ProcessingError).filter_by(discovery_job_id=pending_job.id).first()
    assert error.stage == ProcessingStage.fetching
    assert error.error_type == "http_500"

    from app.models.website_verification import WebsiteVerification
    verif = db_session.query(WebsiteVerification).filter_by(discovery_job_id=pending_job.id).first()
    assert verif is not None
    assert getattr(verif.status, "value", str(verif.status)) == "uncertain"
    assert verif.classifier_version == "fallback_v1"

@patch("app.services.discovery_orchestrator.get_search_provider")
@patch("app.services.discovery_orchestrator.process_search_results")
@pytest.mark.asyncio
async def test_fetch_timeout_and_isolation(mock_process, mock_get_provider, orchestrator, pending_job, db_session, mock_fetch_service, mock_verification_service):
    # Mock search
    mock_provider = AsyncMock()
    mock_provider.search.return_value = []
    mock_get_provider.return_value = mock_provider

    cand1 = NormalizedCandidate(normalized_url="timeout.com", registered_domain="timeout.com", homepage_url="https://timeout.com", original_url="https://timeout.com/1", title="T", query_text="Q", provider="mock", result_position=1)
    cand2 = NormalizedCandidate(normalized_url="crash.com", registered_domain="crash.com", homepage_url="https://crash.com", original_url="https://crash.com/1", title="C", query_text="Q", provider="mock", result_position=2)
    cand3 = NormalizedCandidate(normalized_url="good.com", registered_domain="good.com", homepage_url="https://good.com", original_url="https://good.com/1", title="G", query_text="Q", provider="mock", result_position=3)

    mock_process.return_value = CandidateProcessingResponse(
        accepted=[cand1, cand2, cand3], rejected=[], duplicates=[], accepted_count=3, rejected_count=0, duplicate_count=0
    )

    # Fetcher behavior
    async def fetch_pages_side_effect(req):
        domain = req.candidates[0].registered_domain
        if domain == "timeout.com":
            return [FetchedPage(requested_url="https://timeout.com", final_url="https://timeout.com", registered_domain="timeout.com", status_code=0, content_type="", content_length=0, html="", title="", success=False, error_code="timeout", safe_error="Timeout", elapsed_ms=5000, fetched_at=datetime.now(timezone.utc), redirect_chain=[], redirect_count=0)], 0
        elif domain == "crash.com":
            raise Exception("Unexpected fetcher crash")
        else:
            return [FetchedPage(requested_url="https://good.com", final_url="https://good.com", registered_domain="good.com", status_code=200, content_type="text/html", content_length=10, html="...", title="Good", success=True, error_code=None, safe_error=None, elapsed_ms=100, fetched_at=datetime.now(timezone.utc), redirect_chain=[], redirect_count=0)], 0

    mock_fetch_service.fetch_pages.side_effect = fetch_pages_side_effect

    # Verifier behavior
    def verify_side_effect(page, dt, req):
        if page.registered_domain == "good.com":
            raise Exception("Unexpected verifier crash")

    mock_verification_service._verify_page_sync.side_effect = verify_side_effect

    summary = await orchestrator.run_job(pending_job.id)

    assert summary.final_status == "completed_with_errors"
    assert summary.websites_processed == 3
    assert summary.websites_uncertain == 3

    errors = db_session.query(ProcessingError).filter_by(discovery_job_id=pending_job.id).all()
    assert len(errors) == 3

    print([e.error_type for e in errors])
    print([e.error_type for e in errors])
    print([e.error_type for e in errors])
    print([e.error_type for e in errors])
    timeout_err = next(e for e in errors if e.error_type == "timeout")
    assert timeout_err.is_retryable == True

    crash_err = next(e for e in errors if e.error_type == "fetch_crash")
    assert crash_err.is_retryable == True

    verif_err = next(e for e in errors if e.error_type == "verification_crash")
    assert verif_err.is_retryable == False

    from app.models.website_verification import WebsiteVerification
    verifs = db_session.query(WebsiteVerification).filter_by(discovery_job_id=pending_job.id).all()
    assert len(verifs) == 3
    for v in verifs:
        assert getattr(v.status, "value", str(v.status)) == "uncertain"
        assert v.classifier_version == "fallback_v1"

@patch("app.services.discovery_orchestrator.get_search_provider")
@patch("app.services.discovery_orchestrator.process_search_results")
@pytest.mark.asyncio
async def test_duplicate_results_single_website(mock_process, mock_get_provider, orchestrator, pending_job, db_session, mock_fetch_service, mock_verification_service):
    mock_provider = AsyncMock()
    mock_get_provider.return_value = mock_provider

    candidate1 = NormalizedCandidate(
        normalized_url="example.com", registered_domain="example.com", homepage_url="https://example.com",
        original_url="https://example.com/indie", title="Example", query_text="indie games", provider="mock", result_position=1
    )
    candidate2 = NormalizedCandidate(
        normalized_url="example.com", registered_domain="example.com", homepage_url="https://example.com",
        original_url="https://example.com/other", title="Other", query_text="indie games 2", provider="mock", result_position=2
    )
    mock_process.return_value = CandidateProcessingResponse(
        accepted=[candidate1, candidate2], rejected=[], duplicates=[], accepted_count=2, rejected_count=0, duplicate_count=0
    )

    fetched_page = FetchedPage(
        requested_url="https://example.com", final_url="https://example.com", registered_domain="example.com",
        status_code=200, content_type="text/html", content_length=1000, html="<html></html>", title="Test",
        fetched_at=datetime.now(timezone.utc), redirect_chain=[], redirect_count=0, elapsed_ms=100, success=True,
        error_code=None, safe_error=None
    )
    mock_fetch_service.fetch_pages.return_value = ([fetched_page], 0)

    ver_res = VerificationResult(
        requested_url="https://example.com", final_url="https://example.com", registered_domain="example.com",
        score=85, verification_status="verified", confidence=0.9, gaming_relevance_score=80,
        editorial_structure_score=90, activity_score=80, publication_identity_score=90, negative_penalty=0,
        activity_status="active", article_count_estimate=10, classifier_version="v1",
        analysed_at=datetime.now(timezone.utc), fetch_success=True
    )
    mock_verification_service._verify_page_sync.return_value = ver_res

    summary = await orchestrator.run_job(pending_job.id)

    assert summary.websites_discovered == 1  # Deduped to 1
    assert db_session.query(Website).count() == 1
    assert db_session.query(DiscoverySource).count() == 10  # 5 queries * 2 candidates

@patch("app.services.discovery_orchestrator.get_search_provider")
@pytest.mark.asyncio
async def test_orchestrator_passes_generated_search_query(mock_get_provider, orchestrator, pending_job, db_session):
    mock_provider = AsyncMock()
    mock_provider.search.return_value = []
    mock_get_provider.return_value = mock_provider

    await orchestrator.run_job(pending_job.id)

    # Verify the provider received a GeneratedSearchQuery, not a string
    assert mock_provider.search.call_count == 5
    first_call_args = mock_provider.search.call_args_list[0][0]
    provider_query = first_call_args[0]

    from app.schemas.search import GeneratedSearchQuery
    assert isinstance(provider_query, GeneratedSearchQuery)
    assert provider_query.market == "US"
    assert provider_query.language == "en"
    assert provider_query.query_text != ""

    limit = first_call_args[1]
    assert limit == 10

@patch("app.services.discovery_orchestrator.get_search_provider")
@pytest.mark.asyncio
async def test_failed_query_is_retried(mock_get_provider, orchestrator, pending_job, db_session):
    mock_provider = AsyncMock()
    # First attempt: search fails
    mock_provider.search.side_effect = Exception("Provider timeout")
    mock_get_provider.return_value = mock_provider

    summary_1 = await orchestrator.run_job(pending_job.id)
    assert summary_1.final_status == "completed_with_errors"
    assert summary_1.queries_executed == 5 # Failed counts as executed in attempt

    queries = db_session.query(SearchQuery).filter_by(discovery_job_id=pending_job.id).all()
    assert all(q.status == "failed" for q in queries)
    assert all(q.attempt_count == 1 for q in queries)

    # Second attempt: search succeeds
    mock_provider.search.side_effect = None
    mock_provider.search.return_value = []

    # We must mark the job back to pending or failed so we can start it again
    from sqlalchemy import update
    db_session.execute(update(DiscoveryJob).where(DiscoveryJob.id == pending_job.id).values(status=DiscoveryJobStatus.failed))
    db_session.commit()

    summary_2 = await orchestrator.run_job(pending_job.id)
    # The job had errors on attempt 1, so the final status of the job will be "completed_with_errors"
    assert summary_2.final_status == "completed_with_errors"

    queries_after = db_session.query(SearchQuery).filter_by(discovery_job_id=pending_job.id).all()
    assert all(q.status == "completed" for q in queries_after)
    assert all(q.attempt_count == 2 for q in queries_after)
