import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone
from decimal import Decimal

from app.models.enums import DiscoveryJobStatus, VerificationStatus, QualificationStatus, ProcessingStage
from app.models.discovery_job import DiscoveryJob
from app.models.search_query import SearchQuery
from app.models.website import Website
from app.models.discovery_source import DiscoverySource
from app.models.website_verification import WebsiteVerification
from app.models.processing_error import ProcessingError
from app.models.traffic_metric import TrafficMetric
from app.schemas.search import NormalizedCandidate
from app.schemas.fetch import FetchedPage

from app.services.discovery_orchestrator import DiscoveryOrchestrator
from app.services.fetch_service import FetchService
from app.services.verification_service import VerificationService
from app.schemas.verification import VerificationRequest, VerificationResult
from app.providers.traffic.manual import ManualTrafficProvider
from app.schemas.traffic_estimate import TrafficEstimate
from app.config import get_settings
from app.models.base import Base
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
def orchestrator(session_factory):
    mock_fetch_service = AsyncMock(spec=FetchService)
    mock_verification_service = AsyncMock(spec=VerificationService)
    return DiscoveryOrchestrator(
        session_factory=session_factory,
        settings=get_settings(),
        fetch_service=mock_fetch_service,
        verification_service=mock_verification_service
    )

@pytest.fixture
def pending_job(db_session):
    job = DiscoveryJob(
        status=DiscoveryJobStatus.pending,
        target_market="US",
        language="en",
        categories=["gaming"],
        minimum_pageviews=1000000,
        maximum_queries=1,
        results_per_query=10,
        search_provider="mock",
        traffic_provider="manual"
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job

@patch("app.services.discovery_orchestrator.get_search_provider")
@patch("app.services.discovery_orchestrator.process_search_results")
@pytest.mark.asyncio
async def test_traffic_verification_flows(mock_process, mock_get_provider, orchestrator, pending_job, db_session):
    # Setup mock search provider
    mock_provider = AsyncMock()
    mock_provider.search.return_value = []
    mock_get_provider.return_value = mock_provider

    # We provide 5 candidates to test different traffic flows
    cand_qualified = NormalizedCandidate(normalized_url="kotaku.com", registered_domain="kotaku.com", homepage_url="https://kotaku.com", original_url="https://kotaku.com", title="Kotaku", query_text="gaming", provider="mock", result_position=1)
    cand_upcoming = NormalizedCandidate(normalized_url="example-small-site.com", registered_domain="example-small-site.com", homepage_url="https://example-small-site.com", original_url="https://example-small-site.com", title="Small", query_text="gaming", provider="mock", result_position=2)
    cand_no_data = NormalizedCandidate(normalized_url="example-no-data.com", registered_domain="example-no-data.com", homepage_url="https://example-no-data.com", original_url="https://example-no-data.com", title="No Data", query_text="gaming", provider="mock", result_position=3)
    cand_error = NormalizedCandidate(normalized_url="error.com", registered_domain="error.com", homepage_url="https://error.com", original_url="https://error.com", title="Error", query_text="gaming", provider="mock", result_position=4)
    cand_crash = NormalizedCandidate(normalized_url="crash.com", registered_domain="crash.com", homepage_url="https://crash.com", original_url="https://crash.com", title="Crash", query_text="gaming", provider="mock", result_position=5)
    cand_rejected = NormalizedCandidate(normalized_url="rejected.com", registered_domain="rejected.com", homepage_url="https://rejected.com", original_url="https://rejected.com", title="Rejected", query_text="gaming", provider="mock", result_position=6)

    from app.schemas.search import CandidateProcessingResponse
    mock_process.return_value = CandidateProcessingResponse(
        accepted=[cand_qualified, cand_upcoming, cand_no_data, cand_error, cand_crash, cand_rejected],
        rejected=[], duplicates=[], accepted_count=6, rejected_count=0, duplicate_count=0
    )

    async def fetch_pages_side_effect(req):
        pages = []
        for cand in req.candidates:
            domain = cand.registered_domain
            pages.append(FetchedPage(
                requested_url=f"https://{domain}", final_url=f"https://{domain}", registered_domain=domain,
                status_code=200, content_type="text/html", content_length=10, html="...", title=domain,
                success=True, error_code=None, safe_error=None, elapsed_ms=100, fetched_at=datetime.now(timezone.utc),
                redirect_chain=[], redirect_count=0
            ))
        return pages, 0
    orchestrator.fetch_service.fetch_pages.side_effect = fetch_pages_side_effect

    # Verifier behavior
    def verify_side_effect(page, dt, req):
        if page.registered_domain == "rejected.com":
            status = VerificationStatus.rejected
        else:
            status = VerificationStatus.verified

        return VerificationResult(
            requested_url=page.requested_url, final_url=page.final_url, registered_domain=page.registered_domain,
            score=100, verification_status=status, confidence=1.0, gaming_relevance_score=100,
            editorial_structure_score=100, activity_score=100, publication_identity_score=100,
            negative_penalty=0, negative_reasons=[], activity_status="active", article_count_estimate=10,
            classifier_version="v1", analysed_at=datetime.now(timezone.utc), fetch_success=True
        )
    orchestrator.verification_service._verify_page_sync.side_effect = verify_side_effect

    # Run the orchestrator
    summary = await orchestrator.run_job(pending_job.id)

    # Assertions
    assert summary.final_status == "completed_with_errors"
    assert summary.sites_qualified == 1
    assert summary.sites_upcoming == 1
    assert summary.sites_traffic_missing == 2 # no_data and error (error returns needs_review but wait, if it errors, traffic missing!) Wait, my logic sets it to traffic_missing or needs_review.

    websites = db_session.query(Website).all()
    assert len(websites) == 6

    # 1. Kotaku (Qualified)
    w_kotaku = next(w for w in websites if w.domain == "kotaku.com")
    assert w_kotaku.current_qualification_status == QualificationStatus.qualified
    metrics = db_session.query(TrafficMetric).filter_by(website_id=w_kotaku.id).all()
    assert len(metrics) == 1
    assert metrics[0].estimated_pageviews == Decimal("2500000.00")

    # 2. Example Small (Upcoming)
    w_small = next(w for w in websites if w.domain == "example-small-site.com")
    assert w_small.current_qualification_status == QualificationStatus.upcoming

    # 3. No Data (Traffic Missing)
    w_nodata = next(w for w in websites if w.domain == "example-no-data.com")
    assert w_nodata.current_qualification_status == QualificationStatus.traffic_missing

    # 4. Error (Rate limit, isolated, Traffic Missing)
    w_error = next(w for w in websites if w.domain == "error.com")
    assert w_error.current_qualification_status == QualificationStatus.traffic_missing
    errors = db_session.query(ProcessingError).filter_by(website_id=w_error.id, stage=ProcessingStage.traffic).all()
    assert len(errors) == 1
    assert errors[0].error_type == "rate_limit"

    # 5. Crash (Isolated, Needs Review)
    w_crash = next(w for w in websites if w.domain == "crash.com")
    assert w_crash.current_qualification_status == QualificationStatus.needs_review
    crash_errors = db_session.query(ProcessingError).filter_by(website_id=w_crash.id, stage=ProcessingStage.traffic).all()
    assert len(crash_errors) == 1
    assert crash_errors[0].error_type == "traffic_crash"

    # 6. Rejected (Skipped traffic check)
    w_rejected = next(w for w in websites if w.domain == "rejected.com")
    assert w_rejected.current_qualification_status == QualificationStatus.rejected
    rejected_metrics = db_session.query(TrafficMetric).filter_by(website_id=w_rejected.id).all()
    assert len(rejected_metrics) == 0
