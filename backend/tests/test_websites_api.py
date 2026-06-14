import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db
from app.models.base import Base
from app.models.website import Website
from app.models.traffic_metric import TrafficMetric
from app.models.enums import VerificationStatus, QualificationStatus

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_test_env():
    # Set override
    app.dependency_overrides[get_db] = override_get_db
    # Clear DB
    db = TestingSessionLocal()
    db.query(TrafficMetric).delete()
    db.query(Website).delete()
    db.commit()
    db.close()
    
    yield
    
    # Clean up override
    app.dependency_overrides.clear()

client = TestClient(app)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def mock_websites(db_session):
    now = datetime.now(timezone.utc)
    w1 = Website(
        id=uuid4(), domain="domain1.com", canonical_key="domain1.com", name="Domain One", homepage_url="https://domain1.com", country="US", language="en",
        current_verification_status=VerificationStatus.verified, current_qualification_status=QualificationStatus.qualified,
        is_active=True, created_at=now - timedelta(days=2)
    )
    w2 = Website(
        id=uuid4(), domain="domain2.com", canonical_key="domain2.com", name="Domain Two", homepage_url="https://domain2.com", country="UK", language="en",
        current_verification_status=VerificationStatus.rejected, current_qualification_status=QualificationStatus.rejected,
        is_active=True, created_at=now - timedelta(days=1)
    )
    w3 = Website(
        id=uuid4(), domain="domain3.com", canonical_key="domain3.com", name="Other Name", homepage_url="https://domain3.com", country="US", language="es",
        current_verification_status=VerificationStatus.uncertain, current_qualification_status=QualificationStatus.traffic_missing,
        is_active=True, created_at=now
    )
    
    db_session.add_all([w1, w2, w3])
    db_session.commit()
    
    t1_old = TrafficMetric(
        id=uuid4(), website_id=w1.id, provider="test", metric_type="monthly_pageviews", monthly_visits=100, monthly_pageviews=500,
        estimated_pageviews=500, retrieved_at=now - timedelta(days=5)
    )
    t1_new = TrafficMetric(
        id=uuid4(), website_id=w1.id, provider="test2", metric_type="monthly_pageviews", monthly_visits=200, monthly_pageviews=1000,
        estimated_pageviews=1000, retrieved_at=now - timedelta(days=1)
    )
    t1_same_time = TrafficMetric(
        id=uuid4(), website_id=w1.id, provider="test3", metric_type="monthly_pageviews", monthly_visits=300, monthly_pageviews=1500,
        estimated_pageviews=1500, retrieved_at=now - timedelta(days=1)
    )
    
    db_session.add_all([t1_old, t1_new, t1_same_time])
    db_session.commit()
    
    return [w1, w2, w3], [t1_old, t1_new, t1_same_time]

def test_list_websites_basic(mock_websites):
    websites, traffic = mock_websites
    response = client.get("/api/websites")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3
    assert data["pagination"]["total_items"] == 3
    assert data["pagination"]["page"] == 1

def test_list_websites_latest_traffic(mock_websites):
    websites, traffic = mock_websites
    response = client.get("/api/websites")
    data = response.json()
    
    w1_res = next(i for i in data["items"] if i["domain"] == "domain1.com")
    
    sorted_traffic = sorted([traffic[1], traffic[2]], key=lambda r: (r.retrieved_at, str(r.id)), reverse=True)
    expected_traffic = sorted_traffic[0]
    
    assert float(w1_res["latest_monthly_pageviews"]) == float(expected_traffic.monthly_pageviews)
    assert w1_res["latest_traffic_provider"] == expected_traffic.provider

def test_list_websites_no_traffic(mock_websites):
    response = client.get("/api/websites")
    data = response.json()
    w2_res = next(i for i in data["items"] if i["domain"] == "domain2.com")
    assert w2_res["latest_monthly_pageviews"] is None
    assert w2_res["latest_traffic_provider"] is None

def test_list_websites_search_domain(mock_websites):
    response = client.get("/api/websites?search=domain2")
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["domain"] == "domain2.com"

def test_list_websites_search_name(mock_websites):
    response = client.get("/api/websites?search=Other")
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "Other Name"

def test_list_websites_filters(mock_websites):
    res1 = client.get("/api/websites?verification_status=verified")
    assert len(res1.json()["items"]) == 1
    
    res2 = client.get("/api/websites?qualification_status=rejected")
    assert len(res2.json()["items"]) == 1
    
    res3 = client.get("/api/websites?country=US")
    assert len(res3.json()["items"]) == 2
    
    res4 = client.get("/api/websites?language=es")
    assert len(res4.json()["items"]) == 1

def test_list_websites_pagination(mock_websites):
    res = client.get("/api/websites?page=1&page_size=2")
    data = res.json()
    assert len(data["items"]) == 2
    assert data["pagination"]["total_items"] == 3
    assert data["pagination"]["has_next"] is True
    
    res2 = client.get("/api/websites?page=2&page_size=2")
    data2 = res2.json()
    assert len(data2["items"]) == 1
    assert data2["pagination"]["has_next"] is False

def test_list_websites_invalid_filter():
    response = client.get("/api/websites?verification_status=not_a_status")
    assert response.status_code == 422
    assert "verification_status" in response.text
