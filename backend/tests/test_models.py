import pytest
from app.models import (
    Base,
    Website,
    DiscoveryJob,
    SearchQuery,
    DiscoverySource,
    WebsiteVerification,
    TrafficMetric,
    Contact,
    ProcessingError,
    DiscoveryJobStatus,
    VerificationStatus,
    QualificationStatus,
    ManualReviewStatus,
    ContactType,
    ProcessingStage,
)

def test_models_importable_without_circular_errors():
    # If this file runs, imports succeeded.
    assert True

def test_all_expected_tables_registered():
    expected_tables = {
        "discovery_jobs",
        "search_queries",
        "websites",
        "discovery_sources",
        "website_verifications",
        "traffic_metrics",
        "contacts",
        "processing_errors",
    }
    registered_tables = set(Base.metadata.tables.keys())
    for table in expected_tables:
        assert table in registered_tables, f"Missing table: {table}"

def test_websites_canonical_key_is_unique():
    table = Website.__table__
    col = table.columns["canonical_key"]
    assert col.unique or any(
        idx.unique and [c.name for c in idx.columns] == ["canonical_key"]
        for idx in table.indexes
    ), "canonical_key must be unique"

def test_required_foreign_keys_exist():
    # Check a few critical FKs
    assert SearchQuery.__table__.columns["discovery_job_id"].foreign_keys
    assert DiscoverySource.__table__.columns["website_id"].foreign_keys
    assert DiscoverySource.__table__.columns["discovery_job_id"].foreign_keys
    assert WebsiteVerification.__table__.columns["website_id"].foreign_keys
    assert TrafficMetric.__table__.columns["website_id"].foreign_keys
    assert Contact.__table__.columns["website_id"].foreign_keys
    assert ProcessingError.__table__.columns["website_id"].foreign_keys

def test_check_constraints_exist():
    # Job counters non-negative
    job_table = DiscoveryJob.__table__
    job_checks = [c for c in job_table.constraints if type(c).__name__ == "CheckConstraint"]
    assert any("minimum_pageviews" in c.sqltext.text.lower() for c in job_checks)
    assert any("candidates_found" in c.sqltext.text.lower() for c in job_checks)

    # Verification score 0-100
    ver_table = WebsiteVerification.__table__
    ver_checks = [c for c in ver_table.constraints if type(c).__name__ == "CheckConstraint"]
    assert any("score" in c.sqltext.text.lower() and "100" in c.sqltext.text.lower() for c in ver_checks)

    # Confidence 0-1
    assert any("confidence" in c.sqltext.text.lower() and "1" in c.sqltext.text.lower() for c in ver_checks)

    # Contact requires one method
    contact_table = Contact.__table__
    contact_checks = [c for c in contact_table.constraints if type(c).__name__ == "CheckConstraint"]
    assert any("email" in c.sqltext.text.lower() and "contact_form_url" in c.sqltext.text.lower() for c in contact_checks)

def test_history_allows_multiple_rows_per_website():
    # Ensure there is NO unique constraint on website_id alone in TrafficMetric
    traffic_table = TrafficMetric.__table__
    for idx in traffic_table.indexes:
        if idx.unique:
            assert [c.name for c in idx.columns] != ["website_id"]
            
    # Same for WebsiteVerification
    ver_table = WebsiteVerification.__table__
    for idx in ver_table.indexes:
        if idx.unique:
            assert [c.name for c in idx.columns] != ["website_id"]

def test_status_enum_values():
    assert DiscoveryJobStatus.pending == "pending"
    assert VerificationStatus.verified == "verified"
    assert QualificationStatus.qualified == "qualified"
    assert ManualReviewStatus.approved == "approved"
    assert ContactType.unknown == "unknown"
    assert ProcessingStage.search == "search"
