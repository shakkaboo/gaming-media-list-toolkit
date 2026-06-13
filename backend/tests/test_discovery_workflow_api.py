import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

from app.main import app
from app.database import get_db
from app.models.discovery_job import DiscoveryJob
from app.models.enums import DiscoveryJobStatus, VerificationStatus
from app.models.website import Website
from app.models.search_query import SearchQuery
from app.models.discovery_source import DiscoverySource
from app.models.website_verification import WebsiteVerification
from app.schemas.search import SearchResult, NormalizedCandidate, CandidateProcessingResponse
from app.schemas.fetch import FetchedPage
from app.schemas.verification import VerificationResult

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base

from sqlalchemy.pool import StaticPool

@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={'check_same_thread': False},
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

@pytest.fixture(autouse=True)
def override_get_db(db_session, session_factory):
    def _override():
        yield db_session
    app.dependency_overrides[get_db] = _override
    with patch("app.database.SessionLocal", session_factory):
        yield
    app.dependency_overrides.clear()

client = TestClient(app)

@pytest.fixture
def test_job(db_session):
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
        traffic_provider="mock",
        attempt_number=0,
        queries_generated=0,
        queries_completed=0,
        candidates_found=0,
        duplicates_removed=0,
        candidates_filtered=0,
        sites_fetched=0,
        sites_verified=0,
        websites_uncertain=0,
        sites_rejected=0,
        sites_qualified=0,
        sites_upcoming=0,
        sites_traffic_missing=0,
        contacts_found=0,
        errors_count=0
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job

# 1-7. Run endpoint tests
@patch("app.services.discovery_orchestrator.DiscoveryOrchestrator.run_job")
def test_run_endpoint_pending_job(mock_run, test_job):
    from app.schemas.discovery_orchestration import DiscoveryRunSummary
    mock_run.return_value = DiscoveryRunSummary(
        job_id=test_job.id, attempt_number=1, final_status="completed",
        queries_total=5, queries_executed=5, queries_skipped=0,
        websites_discovered=1, websites_processed=1, websites_verified=1,
        websites_uncertain=0, websites_rejected=0, errors_count=0
    )
    resp = client.post(f"/api/discovery/jobs/{test_job.id}/run")
    assert resp.status_code == 200
    data = resp.json()
    assert data["job_id"] == str(test_job.id)
    assert data["final_status"] == "completed"

def test_run_endpoint_missing_job():
    resp = client.post(f"/api/discovery/jobs/{uuid4()}/run")
    assert resp.status_code == 404

@patch("app.services.discovery_orchestrator.DiscoveryOrchestrator.run_job")
def test_run_endpoint_already_running(mock_run, test_job):
    from app.services.discovery_persistence import InvalidJobTransition
    mock_run.side_effect = InvalidJobTransition("Job is running")
    resp = client.post(f"/api/discovery/jobs/{test_job.id}/run")
    assert resp.status_code == 409

@patch("app.services.discovery_orchestrator.DiscoveryOrchestrator.run_job")
def test_run_endpoint_persistence_failure(mock_run, test_job):
    from app.services.discovery_persistence import PersistenceFailure
    mock_run.side_effect = PersistenceFailure("DB died")
    resp = client.post(f"/api/discovery/jobs/{test_job.id}/run")
    assert resp.status_code == 500
    data = resp.json()
    assert "detail" in data
    assert "DB died" not in data["detail"] # Safe generic message
    assert "traceback" not in data.get("detail", "").lower()

# 8-20. Results endpoint tests
def test_results_endpoint_missing_job():
    resp = client.get(f"/api/discovery/jobs/{uuid4()}/results")
    assert resp.status_code == 404

def test_results_endpoint_zero_websites(test_job):
    resp = client.get(f"/api/discovery/jobs/{test_job.id}/results")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["items"] == []

def test_results_endpoint_complex_data(db_session, test_job):
    # Setup 1 website, 2 discovery sources with different queries, 2 verification attempts
    w = Website(id=uuid4(), domain="example.com", homepage_url="https://example.com", canonical_key="example.com")
    db_session.add(w)
    db_session.commit()

    q1 = SearchQuery(id=uuid4(), discovery_job_id=test_job.id, query_text="query 1", status="completed", provider="mock", requested_limit=10)
    q2 = SearchQuery(id=uuid4(), discovery_job_id=test_job.id, query_text="query 2", status="completed", provider="mock", requested_limit=10)
    db_session.add_all([q1, q2])
    db_session.commit()

    ds1 = DiscoverySource(website_id=w.id, search_query_id=q1.id, discovery_job_id=test_job.id, provider="mock", query_text="query 1", result_url="https://example.com/1", result_position=1)
    ds2 = DiscoverySource(website_id=w.id, search_query_id=q2.id, discovery_job_id=test_job.id, provider="mock", query_text="query 2", result_url="https://example.com/2", result_position=2)
    db_session.add_all([ds1, ds2])
    db_session.commit()

    wv_old = WebsiteVerification(
        website_id=w.id, discovery_job_id=test_job.id, attempt_number=1, status=VerificationStatus.uncertain,
        score=50, confidence=0.5, classifier_version="v1",
        verified_at=datetime(2020, 1, 1, tzinfo=timezone.utc)
    )
    wv_new = WebsiteVerification(
        website_id=w.id, discovery_job_id=test_job.id, attempt_number=2, status=VerificationStatus.verified,
        score=90, confidence=0.9, classifier_version="v1",
        verified_at=datetime(2021, 1, 1, tzinfo=timezone.utc)
    )
    db_session.add_all([wv_old, wv_new])
    db_session.commit()

    # 10, 11, 12, 13, 14, 15
    resp = client.get(f"/api/discovery/jobs/{test_job.id}/results")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    items = data["items"]
    assert len(items) == 1

    item = items[0]
    assert item["website_id"] == str(w.id)
    assert item["source_count"] == 2
    assert set(item["source_queries"]) == {"query 1", "query 2"}
    assert item["verification_status"] == "verified"
    assert item["verification_score"] == 90.0

    # 16, 17, 18
    resp = client.get(f"/api/discovery/jobs/{test_job.id}/results?page=2")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 0

    resp = client.get(f"/api/discovery/jobs/{test_job.id}/results?page=0")
    assert resp.status_code == 422

    resp = client.get(f"/api/discovery/jobs/{test_job.id}/results?page_size=200")
    assert resp.status_code == 422

    # 19, 20
    resp = client.get(f"/api/discovery/jobs/{test_job.id}/results?verification_status=verified")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1

    resp = client.get(f"/api/discovery/jobs/{test_job.id}/results?verification_status=uncertain")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 0

# 21, 22. Job detail endpoint
def test_job_detail_endpoint(test_job):
    resp = client.get(f"/api/discovery/jobs/{test_job.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "websites_uncertain" in data
    assert "contacts_found" in data
    assert "attempt_number" in data
    assert "keywords" not in data
    assert "websites_discovered" not in data

# 17. Minimal workflow integration test
@patch("app.services.discovery_orchestrator.get_search_provider")
@patch("app.services.discovery_orchestrator.process_search_results")
@patch("app.services.fetch_service.FetchService.fetch_pages")
@patch("app.services.verification_service.VerificationService._verify_page_sync")
def test_minimal_workflow_integration(mock_verify, mock_fetch, mock_process, mock_search_prov):
    # Setup mocks
    mock_provider = AsyncMock()
    mock_provider.search.return_value = [SearchResult(url="https://example.com/indie", title="Example", snippet="...", domain="example.com", query_text="indie games", provider="mock", position=1)]
    mock_search_prov.return_value = mock_provider

    candidate = NormalizedCandidate(
        normalized_url="example.com", registered_domain="example.com", homepage_url="https://example.com",
        original_url="https://example.com/indie", title="Example", query_text="indie games", provider="mock", result_position=1
    )
    mock_process.return_value = CandidateProcessingResponse(
        accepted=[candidate], rejected=[], duplicates=[], accepted_count=1, rejected_count=0, duplicate_count=0
    )

    fetched_page = FetchedPage(
        requested_url="https://example.com", final_url="https://example.com", registered_domain="example.com",
        status_code=200, content_type="text/html", content_length=1000, html="<html></html>", title="Test",
        fetched_at=datetime.now(timezone.utc), redirect_chain=[], redirect_count=0, elapsed_ms=100, success=True,
        error_code=None, safe_error=None
    )
    mock_fetch.return_value = ([fetched_page], 0)

    ver_res = VerificationResult(
        requested_url="https://example.com", final_url="https://example.com", registered_domain="example.com",
        score=85, verification_status="verified", confidence=0.9, gaming_relevance_score=80,
        editorial_structure_score=90, activity_score=80, publication_identity_score=90, negative_penalty=0,
        activity_status="active", article_count_estimate=10, classifier_version="v1",
        analysed_at=datetime.now(timezone.utc), fetch_success=True
    )
    mock_verify.return_value = ver_res

    # 1. Create job
    create_resp = client.post("/api/discovery/jobs", json={
        "target_market": "US", "language": "en", "categories": ["indie"],
        "minimum_pageviews": 0, "maximum_queries": 1, "results_per_query": 10
    })
    assert create_resp.status_code == 201
    job_id = create_resp.json()["id"]

    # 2. Run endpoint
    run_resp = client.post(f"/api/discovery/jobs/{job_id}/run")
    assert run_resp.status_code == 200
    assert run_resp.json()["final_status"] == "completed"

    # 3. Results endpoint
    results_resp = client.get(f"/api/discovery/jobs/{job_id}/results")
    assert results_resp.status_code == 200
    res_data = results_resp.json()
    assert res_data["total"] == 1
    assert res_data["items"][0]["verification_status"] == "verified"

    # 4. Detail endpoint
    detail_resp = client.get(f"/api/discovery/jobs/{job_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["candidates_found"] == 1
    assert detail_data["sites_verified"] == 1

@patch("app.services.discovery_orchestrator.get_search_provider")
@patch("app.services.discovery_orchestrator.process_search_results")
@patch("app.services.fetch_service.FetchService.fetch_pages")
def test_workflow_integration_fetch_failure(mock_fetch, mock_process, mock_search_prov):
    # Setup mocks
    mock_provider = AsyncMock()
    mock_provider.search.return_value = [SearchResult(url="https://example.com/indie", title="Example", snippet="...", domain="example.com", query_text="indie games", provider="mock", position=1)]
    mock_search_prov.return_value = mock_provider

    candidate = NormalizedCandidate(
        normalized_url="example.com", registered_domain="example.com", homepage_url="https://example.com",
        original_url="https://example.com/indie", title="Example", query_text="indie games", provider="mock", result_position=1
    )
    mock_process.return_value = CandidateProcessingResponse(
        accepted=[candidate], rejected=[], duplicates=[], accepted_count=1, rejected_count=0, duplicate_count=0
    )

    # Fetch fails
    fetched_page = FetchedPage(
        requested_url="https://example.com", final_url="https://example.com", registered_domain="example.com",
        status_code=500, content_type=None, content_length=None, html=None, title=None,
        fetched_at=datetime.now(timezone.utc), redirect_chain=[], redirect_count=0, elapsed_ms=100, success=False,
        error_code="http_500", safe_error="Server error"
    )
    mock_fetch.return_value = ([fetched_page], 0)

    # 1. Create job
    create_resp = client.post("/api/discovery/jobs", json={
        "target_market": "US", "language": "en", "categories": ["indie"],
        "minimum_pageviews": 0, "maximum_queries": 1, "results_per_query": 10
    })
    job_id = create_resp.json()["id"]

    # 2. Run endpoint
    run_resp = client.post(f"/api/discovery/jobs/{job_id}/run")
    assert run_resp.status_code == 200
    assert run_resp.json()["final_status"] == "completed_with_errors"

    # 3. Results endpoint
    results_resp = client.get(f"/api/discovery/jobs/{job_id}/results")
    assert results_resp.status_code == 200
    res_data = results_resp.json()
    assert res_data["total"] == 1

    # Assert verification status is NOT null, it's the fallback "uncertain"
    item = res_data["items"][0]
    assert item["verification_status"] == "uncertain"
    assert item["classifier_version"] == "fallback_v1"
