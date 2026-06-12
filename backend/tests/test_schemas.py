import pytest
from pydantic import ValidationError
from decimal import Decimal

from app.schemas.discovery_job import DiscoveryJobCreate
from app.schemas.traffic_metric import ManualTrafficCreate
from app.schemas.website import WebsiteSummary
from app.models.enums import VerificationStatus, QualificationStatus, ManualReviewStatus
from uuid import uuid4
from datetime import datetime

def test_discovery_job_create_trim_and_dedup():
    job = DiscoveryJobCreate(
        target_market="  US  ",
        language=" en ",
        categories=[" RPG ", "Action", " rpg", "FPS", "action "],
        minimum_pageviews=500,
        maximum_queries=50,
        results_per_query=20
    )
    assert job.target_market == "US"
    assert job.language == "en"
    assert job.categories == ["RPG", "Action", "FPS"]

def test_discovery_job_create_invalid_blank():
    with pytest.raises(ValidationError):
        DiscoveryJobCreate(
            target_market="   ",
            language="en",
            categories=["RPG"]
        )
        
    with pytest.raises(ValidationError):
        DiscoveryJobCreate(
            target_market="US",
            language="  ",
            categories=["RPG"]
        )
        
    with pytest.raises(ValidationError):
        DiscoveryJobCreate(
            target_market="US",
            language="en",
            categories=["  ", ""]
        )

def test_discovery_job_bounds():
    with pytest.raises(ValidationError):
        DiscoveryJobCreate(target_market="US", language="en", categories=["A"], maximum_queries=101)
    
    with pytest.raises(ValidationError):
        DiscoveryJobCreate(target_market="US", language="en", categories=["A"], maximum_queries=0)
        
    with pytest.raises(ValidationError):
        DiscoveryJobCreate(target_market="US", language="en", categories=["A"], results_per_query=51)

def test_manual_traffic_create_bounds():
    with pytest.raises(ValidationError):
        ManualTrafficCreate(monthly_visits=Decimal("-1"), pages_per_visit=Decimal("2"))
        
    with pytest.raises(ValidationError):
        ManualTrafficCreate(monthly_visits=Decimal("100"), pages_per_visit=Decimal("-0.5"))
        
    with pytest.raises(ValidationError):
        ManualTrafficCreate(monthly_visits=Decimal("100"), pages_per_visit=Decimal("2"), confidence=Decimal("1.5"))

    with pytest.raises(ValidationError):
        ManualTrafficCreate(monthly_visits=Decimal('NaN'), pages_per_visit=Decimal("2"))
        
    with pytest.raises(ValidationError):
        ManualTrafficCreate(monthly_visits=Decimal("100"), pages_per_visit=Decimal('Infinity'))

    with pytest.raises(ValidationError):
        ManualTrafficCreate(monthly_visits=Decimal("10"), pages_per_visit=Decimal("2"), notes="a" * 2001)

def test_website_summary_computed_fields():
    data = {
        "id": uuid4(),
        "domain": "test.com",
        "homepage_url": "https://test.com",
        "current_verification_status": VerificationStatus.verified,
        "current_qualification_status": QualificationStatus.qualified,
        "manual_review_status": ManualReviewStatus.pending,
        "is_active": True,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
        "latest_monthly_visits": Decimal("1000"),
        "best_contact_email": "test@test.com"
    }
    summary = WebsiteSummary.model_validate(data)
    assert summary.latest_monthly_visits == Decimal("1000")
    assert summary.best_contact_email == "test@test.com"
