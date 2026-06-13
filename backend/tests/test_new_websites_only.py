import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from datetime import datetime, timezone

from app.models.website import Website
from app.models.discovery_job import DiscoveryJob
from app.models.enums import DiscoveryJobStatus, VerificationStatus
from app.models.base import Base
from app.schemas.search import NormalizedCandidate, CandidateProcessingResponse
from app.schemas.verification import VerificationResult
from app.services.discovery_orchestrator import DiscoveryOrchestrator
from app.services.fetch_service import FetchService
from app.services.verification_service import VerificationService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return engine

@pytest.fixture
def session_factory(db_engine):
    return sessionmaker(bind=db_engine)

@pytest.fixture
def db_session(session_factory):
    with session_factory() as session:
        yield session

from unittest.mock import AsyncMock, patch, MagicMock

@pytest.fixture
def mock_fetch_service():
    return MagicMock(spec=FetchService)

@pytest.fixture
def mock_verification_service():
    return MagicMock(spec=VerificationService)

@pytest.fixture
def orchestrator(db_session, mock_fetch_service, mock_verification_service):
    from app.config import get_settings
    return DiscoveryOrchestrator(
        session_factory=lambda: db_session,
        settings=get_settings(),
        fetch_service=mock_fetch_service,
        verification_service=mock_verification_service
    )

@pytest.fixture
def common_setup(db_session):
    known_website = Website(
        domain="known.com",
        canonical_key="known.com",
        homepage_url="https://known.com"
    )
    db_session.add(known_website)
    db_session.commit()

    cand_known = NormalizedCandidate(
        original_url="https://known.com",
        normalized_url="known.com",
        homepage_url="https://known.com",
        registered_domain="known.com",
        title="Known",
        query_text="esports",
        provider="mock",
        result_position=1
    )

    cand_known_dup = NormalizedCandidate(
        original_url="https://www.known.com/news",
        normalized_url="known.com/news",
        homepage_url="https://known.com",
        registered_domain="known.com",
        title="Known Duplicate",
        query_text="esports",
        provider="mock",
        result_position=2
    )

    cand_new = NormalizedCandidate(
        original_url="https://newsite.com",
        normalized_url="newsite.com",
        homepage_url="https://newsite.com",
        registered_domain="newsite.com",
        title="New",
        query_text="esports",
        provider="mock",
        result_position=3
    )

    mock_process = CandidateProcessingResponse(
        accepted=[cand_known, cand_known_dup, cand_new],
        rejected=[], duplicates=[], accepted_count=3, rejected_count=0, duplicate_count=0
    )

    vr = VerificationResult(
        requested_url="https://newsite.com",
        final_url="https://newsite.com",
        registered_domain="newsite.com",
        score=100.0,
        confidence=1.0,
        gaming_relevance_score=100.0,
        editorial_structure_score=100.0,
        activity_score=100.0,
        publication_identity_score=100.0,
        negative_penalty=0.0,
        activity_status="active",
        article_count_estimate=100,
        classifier_version="1.0",
        analysed_at=datetime.now(timezone.utc),
        fetch_success=True,
        verification_status=VerificationStatus.verified,
        extracted_title="New",
        has_gaming_keywords=True,
        contact_page_urls=[],
        about_page_urls=[],
        email_addresses=[],
        social_links={}
    )

    from app.schemas.fetch import FetchedPage
    fetched_page = FetchedPage(
        requested_url="https://newsite.com",
        final_url="https://newsite.com",
        registered_domain="newsite.com",
        success=True,
        title="New Site",
        html="<html></html>",
        text_content="New Site",
        status_code=200,
        content_length=13,
        content_type="text/html",
        fetched_at=datetime.now(timezone.utc),
        redirect_chain=[],
        redirect_count=0,
        elapsed_ms=100,
        error_code=None,
        safe_error=None
    )

    return cand_known, cand_known_dup, cand_new, mock_process, vr, fetched_page

@pytest.mark.asyncio
async def test_known_domain_skipped_when_enabled(db_session, orchestrator, common_setup):
    cand_known, cand_known_dup, cand_new, mock_process, vr, fetched_page = common_setup

    job_new = DiscoveryJob(
        id=uuid4(),
        status=DiscoveryJobStatus.pending,
        target_market="US",
        language="en",
        categories=["esports"],
        minimum_pageviews=1000,
        maximum_queries=1,
        results_per_query=10,
        search_provider="mock",
        traffic_provider="mock",
        new_websites_only=True
    )
    db_session.add(job_new)
    db_session.commit()

    with patch('app.services.discovery_orchestrator.get_search_provider') as mock_get_provider, \
         patch('app.services.discovery_orchestrator.process_search_results', return_value=mock_process):

        provider_mock = AsyncMock()
        provider_mock.search.return_value = []
        mock_get_provider.return_value = provider_mock

        orchestrator.fetch_service.fetch_pages.return_value = ([fetched_page], 0)
        orchestrator.verification_service._verify_page_sync.return_value = vr

        summary = await orchestrator.run_job(job_new.id)

        assert summary.known_domains_skipped == 1
        assert summary.duplicate_candidates_skipped == 1
        assert summary.websites_processed == 1

        # Check bypasses
        assert orchestrator.fetch_service.fetch_pages.call_count == 1 # Only for newsite.com
        assert orchestrator.verification_service._verify_page_sync.call_count == 1 # Only for newsite.com

        from app.models.website import Website
        from app.models.discovery_source import DiscoverySource
        from app.models.traffic_metric import TrafficMetric

        # Check known domain got no new discovery source
        known_sources = db_session.query(DiscoverySource).join(Website).filter(Website.domain == "known.com").all()
        assert len(known_sources) == 0

        # known domain gets no traffic metric
        known_metrics = db_session.query(TrafficMetric).join(Website).filter(Website.domain == "known.com").all()
        assert len(known_metrics) == 0

@pytest.mark.asyncio
async def test_existing_domain_processed_when_disabled(db_session, orchestrator, common_setup):
    cand_known, cand_known_dup, cand_new, mock_process, vr, fetched_page = common_setup

    job_old = DiscoveryJob(
        id=uuid4(),
        status=DiscoveryJobStatus.pending,
        target_market="US",
        language="en",
        categories=["esports"],
        minimum_pageviews=1000,
        maximum_queries=1,
        results_per_query=10,
        search_provider="mock",
        traffic_provider="mock",
        new_websites_only=False
    )
    db_session.add(job_old)
    db_session.commit()

    with patch('app.services.discovery_orchestrator.get_search_provider') as mock_get_provider, \
         patch('app.services.discovery_orchestrator.process_search_results', return_value=mock_process):

        provider_mock = AsyncMock()
        provider_mock.search.return_value = []
        mock_get_provider.return_value = provider_mock

        orchestrator.fetch_service.fetch_pages.return_value = ([fetched_page], 0)
        orchestrator.verification_service._verify_page_sync.return_value = vr

        summary_old = await orchestrator.run_job(job_old.id)

        assert summary_old.known_domains_skipped == 0
        assert summary_old.duplicate_candidates_skipped == 1
        assert summary_old.websites_processed == 2

        assert orchestrator.fetch_service.fetch_pages.call_count == 2
        assert orchestrator.verification_service._verify_page_sync.call_count == 2
