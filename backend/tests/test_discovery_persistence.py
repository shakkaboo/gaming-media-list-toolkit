import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock

from app.models.base import Base
from app.services.discovery_persistence import (
    DiscoveryPersistenceService, JobNotFound, InvalidJobTransition, IncompleteJobFinalization
)
from app.models.discovery_job import DiscoveryJob
from app.models.search_query import SearchQuery
from app.models.website import Website
from app.models.discovery_source import DiscoverySource
from app.models.website_verification import WebsiteVerification
from app.models.contact import Contact
from app.models.processing_error import ProcessingError
from app.models.enums import DiscoveryJobStatus, ProcessingStage, VerificationStatus
from app.schemas.search import GeneratedSearchQuery, NormalizedCandidate

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()

@pytest.fixture
def service(db_session):
    return DiscoveryPersistenceService(db_session)

@pytest.fixture
def job(db_session):
    j = DiscoveryJob(
        target_market="US",
        language="en",
        categories=["gaming"],
        minimum_pageviews=1000,
        maximum_queries=5,
        results_per_query=10,
        search_provider="mock",
        traffic_provider="mock",
        status=DiscoveryJobStatus.pending
    )
    db_session.add(j)
    db_session.commit()
    return j

def mock_verification_result(status="verified"):
    m = MagicMock()
    m.status = status
    m.score = 80
    m.confidence = 0.9

    pos = MagicMock()
    pos.code = "pos1"
    pos.evidence = "evidence1"
    m.positive_reasons = [pos]

    neg = MagicMock()
    neg.code = "neg1"
    neg.evidence = "evidence2"
    m.negative_reasons = [neg]

    m.detected_categories = ["gaming"]
    m.is_active = True
    m.classifier_version = "v1"

    m.metadata = MagicMock()
    m.metadata.title = "A"
    m.metadata.description = "B"
    return m

def mock_contact_discovery_result(emails=[], forms=[]):
    m = MagicMock()
    m.emails = emails
    m.forms = forms
    return m

def test_start_job_pending(service, db_session, job):
    started_job = service.start_job(job.id)
    assert started_job.status == DiscoveryJobStatus.running
    assert started_job.attempt_number == 1
    assert started_job.started_at is not None

def test_start_job_running_rejected(service, db_session, job):
    job.status = DiscoveryJobStatus.running
    db_session.commit()
    with pytest.raises(InvalidJobTransition):
        service.start_job(job.id)

def test_start_job_completed_rejected(service, db_session, job):
    job.status = DiscoveryJobStatus.completed
    db_session.commit()
    with pytest.raises(InvalidJobTransition):
        service.start_job(job.id)

def test_start_job_cancelled_rejected(service, db_session, job):
    job.status = DiscoveryJobStatus.cancelled
    db_session.commit()
    with pytest.raises(InvalidJobTransition):
        service.start_job(job.id)

def test_start_job_failed_retry_allowed(service, db_session, job):
    job.status = DiscoveryJobStatus.failed
    job.attempt_number = 1
    db_session.commit()
    started = service.start_job(job.id)
    assert started.status == DiscoveryJobStatus.running
    assert started.attempt_number == 2

def test_start_job_completed_with_errors_retry_allowed(service, db_session, job):
    job.status = DiscoveryJobStatus.completed_with_errors
    job.attempt_number = 2
    db_session.commit()
    started = service.start_job(job.id)
    assert started.status == DiscoveryJobStatus.running
    assert started.attempt_number == 3

def test_start_job_missing(service):
    with pytest.raises(JobNotFound):
        service.start_job(uuid.uuid4())

def test_persist_generated_queries_duplicate_reused(service, db_session, job):
    gq = GeneratedSearchQuery(query_text="test query", category="gaming", market="US", language="en", template_name="t1")
    q1 = service.persist_generated_queries(job.id, [gq])
    assert len(q1) == 1
    q2 = service.persist_generated_queries(job.id, [gq])
    assert len(q2) == 1
    assert q1[0].id == q2[0].id

def test_query_completed_not_downgraded(service, db_session, job):
    gq = GeneratedSearchQuery(query_text="test query", category="gaming", market="US", language="en", template_name="t1")
    queries = service.persist_generated_queries(job.id, [gq])
    q_id = queries[0].id

    service.mark_query_completed(q_id, 5)
    service.mark_query_failed(q_id, "Some error")

    db_session.refresh(queries[0])
    assert queries[0].status == "completed"
    assert queries[0].result_count == 5

def test_website_upsert_ordinary_key(service):
    cand = NormalizedCandidate(
        original_url="https://example.com/page", normalized_url="https://example.com/", homepage_url="https://example.com/",
        registered_domain="example.com", title="Example", query_text="test", provider="mock", result_position=1
    )
    res = service.upsert_website(cand)
    assert res.created is True
    assert res.website.canonical_key == "example.com"
    assert res.website.is_multitenant is False

def test_website_upsert_multitenant_key(service):
    cand = NormalizedCandidate(
        original_url="https://sub.substack.com/page", normalized_url="https://sub.substack.com/", homepage_url="https://sub.substack.com/",
        registered_domain="substack.com", subdomain="sub", title="Sub", query_text="test", provider="mock", result_position=1
    )
    res = service.upsert_website(cand)
    assert res.created is True
    assert res.website.canonical_key == "sub.substack.com"
    assert res.website.is_multitenant is True

def test_website_upsert_duplicate_reused_empty_not_overwrite(service):
    cand1 = NormalizedCandidate(
        original_url="https://example.com/", normalized_url="https://example.com/", homepage_url="https://example.com/",
        registered_domain="example.com", title="Example", snippet="Snip", query_text="t1", provider="mock", result_position=1
    )
    res1 = service.upsert_website(cand1)

    cand2 = NormalizedCandidate(
        original_url="https://example.com/", normalized_url="https://example.com/", homepage_url="https://example.com/",
        registered_domain="example.com", title="", snippet="", query_text="t2", provider="mock", result_position=1
    )
    res2 = service.upsert_website(cand2)

    assert res2.created is False
    assert res2.website.id == res1.website.id
    assert res2.website.name == "Example"
    assert res2.website.description == "Snip"

def test_discovery_source_duplicate_reused(service, db_session, job):
    cand = NormalizedCandidate(
        original_url="https://example.com/article", normalized_url="https://example.com/", homepage_url="https://example.com/",
        registered_domain="example.com", title="Ex", query_text="test", provider="mock", result_position=1
    )
    web_res = service.upsert_website(cand)
    gq = GeneratedSearchQuery(query_text="test", category="gaming", market="US", language="en", template_name="t")
    q = service.persist_generated_queries(job.id, [gq])[0]

    src1 = service.persist_discovery_source(job, q, web_res.website, cand)
    src2 = service.persist_discovery_source(job, q, web_res.website, cand)

    assert src1.id == src2.id

def test_verification_same_attempt_idempotent(service, job):
    cand = NormalizedCandidate(
        original_url="https://example.com/", normalized_url="https://example.com/", homepage_url="https://example.com/",
        registered_domain="example.com", title="Ex", query_text="test", provider="mock", result_position=1
    )
    web = service.upsert_website(cand).website

    res = mock_verification_result(status="verified")

    job.attempt_number = 1
    v1 = service.persist_verification(job, web, res)
    v2 = service.persist_verification(job, web, res)
    assert v1.id == v2.id

def test_verification_later_attempt_creates_history(service, job, db_session):
    cand = NormalizedCandidate(
        original_url="https://example.com/", normalized_url="https://example.com/", homepage_url="https://example.com/",
        registered_domain="example.com", title="Ex", query_text="test", provider="mock", result_position=1
    )
    web = service.upsert_website(cand).website
    res = mock_verification_result(status="verified")

    job.attempt_number = 1
    v1 = service.persist_verification(job, web, res)

    job.attempt_number = 2
    v2 = service.persist_verification(job, web, res)

    assert v1.id != v2.id
    assert v1.attempt_number == 1
    assert v2.attempt_number == 2

def test_contacts_case_insensitive_reused(service, job):
    cand = NormalizedCandidate(
        original_url="https://example.com/", normalized_url="https://example.com/", homepage_url="https://example.com/",
        registered_domain="example.com", title="Ex", query_text="test", provider="mock", result_position=1
    )
    web = service.upsert_website(cand).website

    c1 = MagicMock()
    c1.email = "Info@Example.com"
    c1.confidence = 0.8
    c1.primary_type = "general"
    c1.source_url = "https://example.com/contact"
    c1.is_primary = True

    r1 = mock_contact_discovery_result(emails=[c1])
    service.persist_contacts(job, web, r1)

    c2 = MagicMock()
    c2.email = "info@example.com"
    c2.confidence = 0.9
    c2.primary_type = "editorial"
    c2.source_url = "https://example.com/contact"
    c2.is_primary = True

    r2 = mock_contact_discovery_result(emails=[c2])
    sum2 = service.persist_contacts(job, web, r2)

    assert sum2.created == 0
    assert sum2.reused == 1

def test_contacts_same_email_different_websites_allowed(service, job):
    w1 = service.upsert_website(NormalizedCandidate(original_url="https://a.com/", normalized_url="https://a.com/", homepage_url="https://a.com/", registered_domain="a.com", title="A", query_text="t", provider="m", result_position=1)).website
    w2 = service.upsert_website(NormalizedCandidate(original_url="https://b.com/", normalized_url="https://b.com/", homepage_url="https://b.com/", registered_domain="b.com", title="B", query_text="t", provider="m", result_position=1)).website

    c = MagicMock()
    c.email = "info@example.com"
    c.confidence = 0.8
    c.primary_type = "general"
    c.source_url = "https://example.com/contact"
    c.is_primary = True

    r = mock_contact_discovery_result(emails=[c])

    sum1 = service.persist_contacts(job, w1, r)
    sum2 = service.persist_contacts(job, w2, r)

    assert sum1.created == 1
    assert sum2.created == 1

def test_contacts_duplicate_form_reused(service, job):
    web = service.upsert_website(NormalizedCandidate(original_url="https://a.com/", normalized_url="https://a.com/", homepage_url="https://a.com/", registered_domain="a.com", title="A", query_text="t", provider="m", result_position=1)).website

    f1 = MagicMock()
    f1.form_url = "https://a.com/contact"
    f1.confidence = 0.5
    f1.purpose = "general"
    f1.page_url = "https://example.com/contact"
    f1.is_primary = False

    r1 = mock_contact_discovery_result(forms=[f1])
    service.persist_contacts(job, web, r1)

    f2 = MagicMock()
    f2.form_url = "https://a.com/contact"
    f2.confidence = 0.9
    f2.purpose = "editorial"
    f2.page_url = "https://example.com/contact"
    f2.is_primary = True

    r2 = mock_contact_discovery_result(forms=[f2])
    sum2 = service.persist_contacts(job, web, r2)

    assert sum2.created == 0
    assert sum2.reused == 1

def test_processing_error_isolated(db_session, job):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    job.attempt_number = 1
    db_session.commit()
    err = DiscoveryPersistenceService.record_processing_error_isolated(
        session_factory, job.id, 1, ProcessingStage.fetching, "ERR", "Safe", False
    )
    assert err.id is not None
    assert err.stage == ProcessingStage.fetching

def test_counters_candidates_distinct_websites(service, job):
    w1 = service.upsert_website(NormalizedCandidate(original_url="https://a.com/", normalized_url="https://a.com/", homepage_url="https://a.com/", registered_domain="a.com", title="A", query_text="t", provider="m", result_position=1)).website
    q = service.persist_generated_queries(job.id, [GeneratedSearchQuery(query_text="t", category="c", market="m", language="l", template_name="t")])[0]

    service.persist_discovery_source(job, q, w1, NormalizedCandidate(original_url="https://a.com/1", normalized_url="https://a.com/1", homepage_url="https://a.com/", registered_domain="a.com", title="A", query_text="t", provider="m", result_position=1))
    service.persist_discovery_source(job, q, w1, NormalizedCandidate(original_url="https://a.com/2", normalized_url="https://a.com/2", homepage_url="https://a.com/", registered_domain="a.com", title="A", query_text="t", provider="m", result_position=2))

    j = service.recalculate_job_counters(job.id)
    assert j.candidates_found == 1

def test_counters_only_latest_verification_counts(service, job, db_session):
    w = service.upsert_website(NormalizedCandidate(original_url="https://a.com/", normalized_url="https://a.com/", homepage_url="https://a.com/", registered_domain="a.com", title="A", query_text="t", provider="m", result_position=1)).website

    job.attempt_number = 1
    service.persist_verification(job, w, mock_verification_result(status="uncertain"))

    j = service.recalculate_job_counters(job.id)
    assert j.websites_uncertain == 1
    assert j.sites_verified == 0

    job.attempt_number = 2
    service.persist_verification(job, w, mock_verification_result(status="verified"))

    j = service.recalculate_job_counters(job.id)
    assert j.websites_uncertain == 0
    assert j.sites_verified == 1

def test_finalize_unfinished_query(service, job):
    q = service.persist_generated_queries(job.id, [GeneratedSearchQuery(query_text="t", category="c", market="m", language="l", template_name="t")])[0]
    with pytest.raises(IncompleteJobFinalization):
        service.finalize_job(job.id)

def test_finalize_website_without_verification_or_error(service, job):
    w1 = service.upsert_website(NormalizedCandidate(original_url="https://a.com/", normalized_url="https://a.com/", homepage_url="https://a.com/", registered_domain="a.com", title="A", query_text="t", provider="m", result_position=1)).website
    q = service.persist_generated_queries(job.id, [GeneratedSearchQuery(query_text="t", category="c", market="m", language="l", template_name="t")])[0]
    service.mark_query_completed(q.id, 1)

    service.persist_discovery_source(job, q, w1, NormalizedCandidate(original_url="https://a.com/1", normalized_url="https://a.com/1", homepage_url="https://a.com/", registered_domain="a.com", title="A", query_text="t", provider="m", result_position=1))

    with pytest.raises(IncompleteJobFinalization):
        service.finalize_job(job.id)

def test_finalize_all_complete(service, job):
    w1 = service.upsert_website(NormalizedCandidate(original_url="https://a.com/", normalized_url="https://a.com/", homepage_url="https://a.com/", registered_domain="a.com", title="A", query_text="t", provider="m", result_position=1)).website
    q = service.persist_generated_queries(job.id, [GeneratedSearchQuery(query_text="t", category="c", market="m", language="l", template_name="t")])[0]
    service.mark_query_completed(q.id, 1)

    service.persist_discovery_source(job, q, w1, NormalizedCandidate(original_url="https://a.com/1", normalized_url="https://a.com/1", homepage_url="https://a.com/", registered_domain="a.com", title="A", query_text="t", provider="m", result_position=1))

    job.attempt_number = 1
    service.persist_verification(job, w1, mock_verification_result(status="verified"))

    j = service.finalize_job(job.id)
    assert j.status == DiscoveryJobStatus.completed

def test_finalize_complete_with_errors(service, job):
    w1 = service.upsert_website(NormalizedCandidate(original_url="https://a.com/", normalized_url="https://a.com/", homepage_url="https://a.com/", registered_domain="a.com", title="A", query_text="t", provider="m", result_position=1)).website
    q = service.persist_generated_queries(job.id, [GeneratedSearchQuery(query_text="t", category="c", market="m", language="l", template_name="t")])[0]
    service.mark_query_completed(q.id, 1)

    service.persist_discovery_source(job, q, w1, NormalizedCandidate(original_url="https://a.com/1", normalized_url="https://a.com/1", homepage_url="https://a.com/", registered_domain="a.com", title="A", query_text="t", provider="m", result_position=1))

    job.attempt_number = 1
    service.record_processing_error(job.id, job.attempt_number, ProcessingStage.verification, "ERR", "err", False, website_id=w1.id)

    j = service.finalize_job(job.id)
    assert j.status == DiscoveryJobStatus.completed_with_errors

def test_no_infinite_retry_on_integrity_error(service, job):
    w = service.upsert_website(NormalizedCandidate(original_url="https://a.com/", normalized_url="https://a.com/", homepage_url="https://a.com/", registered_domain="a.com", title="A", query_text="t", provider="m", result_position=1)).website

    c = MagicMock()
    c.email = "bad@example.com"
    c.confidence = 0.8
    c.primary_type = "general"
    c.source_url = "https://example.com/contact"
    c.is_primary = True

    r = mock_contact_discovery_result(emails=[c])

    from sqlalchemy.exc import IntegrityError
    original_flush = service.session.flush
    def mock_flush():
        raise IntegrityError("Fake NOT NULL constraint", params=[], orig=Exception("NOT NULL constraint failed"))
    service.session.flush = mock_flush

    from app.services.discovery_persistence import PersistenceFailure
    try:
        with pytest.raises(PersistenceFailure):
            service.persist_contacts(job, w, r)
    finally:
        service.session.flush = original_flush
