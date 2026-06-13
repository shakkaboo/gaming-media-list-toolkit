import pytest
from typing import Optional
from decimal import Decimal
from uuid import uuid4
from fastapi.testclient import TestClient
from datetime import date
from sqlalchemy.orm import Session

from app.main import app
from app.models.website import Website
from app.models.discovery_job import DiscoveryJob
from app.models.enums import VerificationStatus, QualificationStatus
from app.database import get_db
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.base import Base

from sqlalchemy.pool import StaticPool

@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
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

@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

from app.models.discovery_source import DiscoverySource

def make_website(
    db_session: Session,
    domain: str,
    verification_status: VerificationStatus = VerificationStatus.verified,
    job: Optional[DiscoveryJob] = None,
) -> Website:
    website = Website(
        domain=domain,
        canonical_key=domain,
        homepage_url=f"http://{domain}/",
        current_verification_status=verification_status,
    )
    db_session.add(website)
    db_session.commit()
    db_session.refresh(website)
    
    if job:
        source = DiscoverySource(
            website_id=website.id,
            discovery_job_id=job.id,
            provider="mock",
            query_text="test",
            result_url=website.homepage_url
        )
        db_session.add(source)
        db_session.commit()
        
    return website

def test_traffic_evidence_api_monthly_pageviews(client, db_session: Session):
    job = DiscoveryJob(target_market="US", language="en", categories=[], minimum_pageviews=1000, maximum_queries=10, results_per_query=10, search_provider="mock", traffic_provider="mock")
    db_session.add(job)
    db_session.commit()
    website = make_website(db_session, "test1.com", job=job)

    payload = {
        "metric_type": "monthly_pageviews",
        "monthly_pageviews": 1500,
        "evidence_url": "https://evidence.com",
        "notes": "some notes"
    }
    
    response = client.post(f"/api/websites/{website.id}/traffic-evidence?discovery_job_id={job.id}", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["monthly_pageviews"] == "1500.00"
    assert data["estimated_pageviews"] == "1500.00"
    assert data["metric_type"] == "monthly_pageviews"
    assert data["evidence_url"] == "https://evidence.com"
    
    db_session.refresh(website)
    assert website.current_qualification_status == QualificationStatus.qualified

def test_traffic_evidence_api_estimated_pageviews(client, db_session: Session):
    job = DiscoveryJob(target_market="US", language="en", categories=[], minimum_pageviews=1000, maximum_queries=10, results_per_query=10, search_provider="mock", traffic_provider="mock")
    db_session.add(job)
    db_session.commit()
    website = make_website(db_session, "test2.com", job=job)

    payload = {
        "metric_type": "estimated_monthly_pageviews",
        "monthly_visits": 400,
        "pages_per_visit": 2.0
    }
    
    response = client.post(f"/api/websites/{website.id}/traffic-evidence?discovery_job_id={job.id}", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["estimated_pageviews"] == "800.00"
    
    db_session.refresh(website)
    assert website.current_qualification_status == QualificationStatus.upcoming

def test_traffic_evidence_api_monthly_visits_only(client, db_session: Session):
    job = DiscoveryJob(target_market="US", language="en", categories=[], minimum_pageviews=1000, maximum_queries=10, results_per_query=10, search_provider="mock", traffic_provider="mock")
    db_session.add(job)
    db_session.commit()
    website = make_website(db_session, "test3.com", job=job)

    payload = {
        "metric_type": "monthly_visits",
        "monthly_visits": 5000
    }
    
    response = client.post(f"/api/websites/{website.id}/traffic-evidence?discovery_job_id={job.id}", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["estimated_pageviews"] is None
    
    db_session.refresh(website)
    assert website.current_qualification_status == QualificationStatus.traffic_missing

def test_traffic_evidence_api_rejected_site(client, db_session: Session):
    job = DiscoveryJob(target_market="US", language="en", categories=[], minimum_pageviews=1000, maximum_queries=10, results_per_query=10, search_provider="mock", traffic_provider="mock")
    db_session.add(job)
    db_session.commit()
    website = make_website(db_session, "test4.com", VerificationStatus.rejected, job=job)

    payload = {
        "metric_type": "monthly_pageviews",
        "monthly_pageviews": 5000000
    }
    
    response = client.post(f"/api/websites/{website.id}/traffic-evidence?discovery_job_id={job.id}", json=payload)
    assert response.status_code == 201
    
    db_session.refresh(website)
    assert website.current_qualification_status == QualificationStatus.rejected

def test_traffic_evidence_api_invalid_data(client, db_session: Session):
    website = make_website(db_session, "test5.com")

    payload = {
        "metric_type": "monthly_pageviews",
        "monthly_pageviews": -500
    }
    
    response = client.post(f"/api/websites/{website.id}/traffic-evidence", json=payload)
    assert response.status_code == 422

def test_traffic_evidence_api_unrelated_job(client, db_session: Session):
    job_a = DiscoveryJob(target_market="US", language="en", categories=[], minimum_pageviews=1000, maximum_queries=10, results_per_query=10, search_provider="mock", traffic_provider="mock")
    job_b = DiscoveryJob(target_market="UK", language="en", categories=[], minimum_pageviews=5000, maximum_queries=10, results_per_query=10, search_provider="mock", traffic_provider="mock")
    db_session.add_all([job_a, job_b])
    db_session.commit()
    
    # website belongs to job A
    website = make_website(db_session, "test_unrelated.com", job=job_a)
    
    payload = {
        "metric_type": "monthly_pageviews",
        "monthly_pageviews": 1500
    }
    
    # Try to submit with job B
    response = client.post(f"/api/websites/{website.id}/traffic-evidence?discovery_job_id={job_b.id}", json=payload)
    assert response.status_code == 404
    assert response.json()["error"] == "resource_not_found"

def test_traffic_evidence_api_missing_job(client, db_session: Session):
    website = make_website(db_session, "test_missing_job.com")
    fake_job_id = "00000000-0000-0000-0000-000000000000"
    
    payload = {
        "metric_type": "monthly_pageviews",
        "monthly_pageviews": 1500
    }
    
    response = client.post(f"/api/websites/{website.id}/traffic-evidence?discovery_job_id={fake_job_id}", json=payload)
    assert response.status_code == 404
    assert response.json()["error"] == "resource_not_found"

def test_traffic_evidence_api_missing_website(client, db_session: Session):
    fake_website_id = "00000000-0000-0000-0000-000000000000"
    
    payload = {
        "metric_type": "monthly_pageviews",
        "monthly_pageviews": 1500
    }
    
    response = client.post(f"/api/websites/{fake_website_id}/traffic-evidence", json=payload)
    assert response.status_code == 404
    assert response.json()["error"] == "resource_not_found"

def test_traffic_evidence_api_repeated_evidence(client, db_session: Session):
    job = DiscoveryJob(target_market="US", language="en", categories=[], minimum_pageviews=1000, maximum_queries=10, results_per_query=10, search_provider="mock", traffic_provider="mock")
    db_session.add(job)
    db_session.commit()
    website = make_website(db_session, "test_repeat.com", job=job)

    # First submission: below threshold -> upcoming
    payload1 = {
        "metric_type": "monthly_pageviews",
        "monthly_pageviews": 500
    }
    response1 = client.post(f"/api/websites/{website.id}/traffic-evidence?discovery_job_id={job.id}", json=payload1)
    assert response1.status_code == 201
    db_session.refresh(website)
    assert website.current_qualification_status == QualificationStatus.upcoming
    
    # Second submission: above threshold -> qualified
    payload2 = {
        "metric_type": "monthly_pageviews",
        "monthly_pageviews": 1500
    }
    response2 = client.post(f"/api/websites/{website.id}/traffic-evidence?discovery_job_id={job.id}", json=payload2)
    assert response2.status_code == 201
    db_session.refresh(website)
    assert website.current_qualification_status == QualificationStatus.qualified
    
    # Verify history
    from app.models.traffic_metric import TrafficMetric
    metrics = db_session.query(TrafficMetric).filter_by(website_id=website.id).order_by(TrafficMetric.retrieved_at.asc()).all()
    assert len(metrics) == 2
    assert metrics[0].monthly_pageviews == Decimal("500")
    assert metrics[1].monthly_pageviews == Decimal("1500")
