import pytest
from decimal import Decimal
from app.services.traffic_service import calculate_estimated_pageviews, determine_qualification_status
from app.models.enums import VerificationStatus, QualificationStatus

def test_calculate_estimated_pageviews():
    res = calculate_estimated_pageviews(Decimal("500000"), Decimal("3"))
    assert res == Decimal("1500000.00")
    
    res = calculate_estimated_pageviews(Decimal("100"), Decimal("2.125"))
    assert res == Decimal("212.50")
    
    with pytest.raises(ValueError):
        calculate_estimated_pageviews(Decimal("-100"), Decimal("2"))

def test_determine_qualification_status():
    threshold = Decimal("1000000")
    
    # 1. Rejected verification
    assert determine_qualification_status(Decimal("2000000"), VerificationStatus.rejected, threshold) == QualificationStatus.rejected
    
    # 2. Uncertain / fetch_failed
    assert determine_qualification_status(Decimal("2000000"), VerificationStatus.uncertain, threshold) == QualificationStatus.needs_review
    assert determine_qualification_status(Decimal("2000000"), VerificationStatus.fetch_failed, threshold) == QualificationStatus.needs_review
    
    # 3. Missing estimated pageviews
    assert determine_qualification_status(None, VerificationStatus.verified, threshold) == QualificationStatus.traffic_missing
    
    # 4. Strictly greater than threshold
    assert determine_qualification_status(Decimal("1000000.01"), VerificationStatus.verified, threshold) == QualificationStatus.qualified
    
    # 5. Exactly threshold -> upcoming
    assert determine_qualification_status(Decimal("1000000.00"), VerificationStatus.verified, threshold) == QualificationStatus.upcoming
    
    # 6. Below threshold -> upcoming
    assert determine_qualification_status(Decimal("999999.99"), VerificationStatus.verified, threshold) == QualificationStatus.upcoming
