import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from uuid import uuid4
from decimal import Decimal
from datetime import datetime

from app.main import app
from app.exceptions import ResourceNotFoundError, DuplicateResourceError, InvalidOperationError
from app.models.enums import DiscoveryJobStatus, VerificationStatus, QualificationStatus, ManualReviewStatus
from app.schemas.discovery_job import DiscoveryJobSummary, DiscoveryJobDetail
from app.schemas.website import WebsiteSummary, WebsiteDetail
from app.schemas.traffic_metric import TrafficMetricResponse

client = TestClient(app)
client_safe = TestClient(app, raise_server_exceptions=False)

def override_get_db():
    yield MagicMock()

from app.database import get_db
app.dependency_overrides[get_db] = override_get_db

@patch("app.api.discovery_jobs.create_job")
def test_create_job_201(mock_create_job):
    job_id = uuid4()
    mock_create_job.return_value = DiscoveryJobDetail(
        id=job_id,
        status=DiscoveryJobStatus.pending,
        target_market="US",
        language="en",
        categories=["RPG"],
        minimum_pageviews=1000000,
        maximum_queries=10,
        results_per_query=10,
        search_provider="mock",
        traffic_provider="mock",
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
        errors_count=0,
        attempt_number=0,
        created_at=datetime.now(),
        updated_at=datetime.now()
    )

    response = client.post("/api/discovery/jobs", json={
        "target_market": "US",
        "language": "en",
        "categories": ["RPG"]
    })

    assert response.status_code == 201
    assert response.json()["target_market"] == "US"

def test_create_job_invalid_422():
    response = client.post("/api/discovery/jobs", json={
        "target_market": "",
        "language": "en",
        "categories": ["RPG"]
    })
    assert response.status_code == 422

@patch("app.api.discovery_jobs.list_jobs")
def test_list_jobs(mock_list_jobs):
    mock_list_jobs.return_value = ([], 0)
    response = client.get("/api/discovery/jobs")
    assert response.status_code == 200
    assert response.json()["pagination"]["total_items"] == 0

@patch("app.api.discovery_jobs.get_job")
def test_get_job_missing_404(mock_get_job):
    mock_get_job.side_effect = ResourceNotFoundError("Job not found")
    response = client.get(f"/api/discovery/jobs/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"] == "resource_not_found"

@patch("app.api.websites.list_websites")
def test_list_websites(mock_list_websites):
    mock_list_websites.return_value = ([], 0)
    response = client.get("/api/websites")
    assert response.status_code == 200

@patch("app.api.websites.get_website")
def test_get_website_missing_404(mock_get_website):
    mock_get_website.side_effect = ResourceNotFoundError("Website not found")
    response = client.get(f"/api/websites/{uuid4()}")
    assert response.status_code == 404

def test_update_review_validation():
    response = client.patch(f"/api/websites/{uuid4()}/review", json={
        "manual_review_status": "invalid_status"
    })
    assert response.status_code == 422

@patch("app.api.websites.add_manual_traffic")
def test_add_manual_traffic_201(mock_add_traffic):
    mock_add_traffic.return_value = TrafficMetricResponse(
        id=uuid4(),
        website_id=uuid4(),
        provider="manual",
        metric_type="estimated_monthly_pageviews",
        monthly_visits=Decimal("1000"),
        pages_per_visit=Decimal("2"),
        is_manual=True,
        retrieved_at=datetime.now()
    )

    response = client.post(f"/api/websites/{uuid4()}/traffic-evidence", json={
        "metric_type": "estimated_monthly_pageviews",
        "monthly_visits": "1000",
        "pages_per_visit": "2"
    })
    assert response.status_code == 201

def test_add_manual_traffic_invalid_data():
    response = client.post(f"/api/websites/{uuid4()}/traffic-evidence", json={
        "monthly_visits": "1000",
        "pages_per_visit": "2"
    })
    assert response.status_code == 422

@patch("app.api.discovery_jobs.get_job")
def test_duplicate_resource_409(mock_get_job):
    mock_get_job.side_effect = DuplicateResourceError("Duplicate exists")
    response = client.get(f"/api/discovery/jobs/{uuid4()}")
    assert response.status_code == 409
    assert response.json()["error"] == "duplicate_resource"

@patch("app.api.discovery_jobs.get_job")
def test_invalid_operation_400(mock_get_job):
    mock_get_job.side_effect = InvalidOperationError("Invalid state")
    response = client.get(f"/api/discovery/jobs/{uuid4()}")
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_operation"

@patch("app.api.discovery_jobs.get_job")
def test_unknown_error_500(mock_get_job):
    mock_get_job.side_effect = Exception("System failure")
    response = client_safe.get(f"/api/discovery/jobs/{uuid4()}")
    assert response.status_code == 500
    assert response.json()["detail"] == "An unexpected internal server error occurred."
