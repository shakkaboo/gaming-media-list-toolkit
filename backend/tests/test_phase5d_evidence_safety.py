import pytest
from datetime import datetime, timezone
from app.schemas.acquisition import AcquisitionResult, FeedEntry
from app.schemas.fetch import FetchedPage
from app.schemas.verification import VerificationRequest
from app.verification.classifier_v2 import ClassifierV2
from app.config import get_settings

@pytest.fixture
def classifier():
    return ClassifierV2(get_settings())

@pytest.fixture
def current_time():
    return datetime.now(timezone.utc)

@pytest.fixture
def base_request():
    return VerificationRequest(
        candidates=[{
            "original_url": "https://example.com",
            "normalized_url": "https://example.com",
            "homepage_url": "https://example.com",
            "registered_domain": "example.com",
            "title": "Example",
            "query_text": "example",
            "provider": "test",
            "result_position": 1
        }],
        classifier_version="v2_multilingual_explainable",
        verified_threshold=58,
        uncertain_threshold=40,
        gaming_minimum=14,
        media_minimum=10,
        technical_minimum=0,
        market_minimum=0
    )

def _page(url, current_time, html="", status=200, success=True, err=""):
    return FetchedPage(
        requested_url=url,
        final_url=url,
        registered_domain=url.replace("https://", "").replace("http://", "").split("/")[0],
        status_code=status,
        content_type="text/html",
        content_length=len(html),
        html=html,
        title="",
        fetched_at=current_time,
        redirect_count=0,
        elapsed_ms=100,
        success=success,
        error_code=err,
        safe_error="true" if not success else None
    )

def test_403_alone_produces_uncertain(classifier, current_time, base_request):
    acq = AcquisitionResult(
        domain="example.com",
        transport_success=True,
        usable_evidence_found=False,
        primary_page=_page("https://example.com", current_time, status=403, success=False, err="http_403")
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "uncertain"

def test_401_alone_produces_uncertain(classifier, current_time, base_request):
    acq = AcquisitionResult(
        domain="example.com",
        transport_success=True,
        usable_evidence_found=False,
        primary_page=_page("https://example.com", current_time, status=401, success=False, err="http_401")
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "uncertain"

def test_timeout_alone_produces_uncertain(classifier, current_time, base_request):
    acq = AcquisitionResult(
        domain="example.com",
        transport_success=False,
        usable_evidence_found=False,
        primary_page=_page("https://example.com", current_time, status=0, success=False, err="timeout")
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "uncertain"

def test_dns_failure_alone_produces_uncertain(classifier, current_time, base_request):
    acq = AcquisitionResult(
        domain="example.com",
        transport_success=False,
        usable_evidence_found=False,
        primary_page=_page("https://example.com", current_time, status=0, success=False, err="dns_error")
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "uncertain"

def test_challenge_page_alone_produces_uncertain(classifier, current_time, base_request):
    acq = AcquisitionResult(
        domain="example.com",
        transport_success=True,
        usable_evidence_found=False,
        primary_page=_page("https://example.com", current_time, html="Please verify you are human", status=200)
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "uncertain"
    
def test_js_shell_without_supporting_produces_uncertain(classifier, current_time, base_request):
    acq = AcquisitionResult(
        domain="example.com",
        transport_success=True,
        usable_evidence_found=True,
        primary_page=_page("https://example.com", current_time, html="<script>app.mount()</script>")
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "uncertain"

def test_generic_text_alone_cannot_produce_verified(classifier, current_time, base_request):
    acq = AcquisitionResult(
        domain="example.com",
        transport_success=True,
        usable_evidence_found=True,
        primary_page=_page("https://example.com", current_time, html="<html><body><h1>Hello World</h1></body></html>")
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "uncertain"
    
def test_generic_text_alone_cannot_produce_rejected(classifier, current_time, base_request):
    acq = AcquisitionResult(
        domain="example.com",
        transport_success=True,
        usable_evidence_found=True,
        primary_page=_page("https://example.com", current_time, html="<html><body><h1>Hello World</h1></body></html>")
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "uncertain"

def test_domain_name_alone_cannot_establish_relevance(classifier, current_time, base_request):
    acq = AcquisitionResult(
        domain="gamingnews.com",
        transport_success=True,
        usable_evidence_found=True,
        primary_page=_page("https://gamingnews.com", current_time, html="<html><body><h1>Hello World</h1></body></html>")
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "uncertain"

def test_target_market_alone_cannot_establish_relevance(classifier, current_time, base_request):
    base_request.expected_market = "Japan"
    acq = AcquisitionResult(
        domain="example.com",
        transport_success=True,
        usable_evidence_found=True,
        primary_page=_page("https://example.com", current_time, html="<html><body><h1>Hello World</h1></body></html>")
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "uncertain"

def test_language_alone_cannot_establish_relevance(classifier, current_time, base_request):
    base_request.expected_language = "ja"
    acq = AcquisitionResult(
        domain="example.com",
        transport_success=True,
        usable_evidence_found=True,
        primary_page=_page("https://example.com", current_time, html="<html lang='ja'><body><h1>Hello World</h1></body></html>")
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "uncertain"

def test_expected_label_never_enters_acquisition_or_scoring(base_request):
    assert not hasattr(base_request, "expected_label")

def test_website_type_never_enters_scoring(base_request):
    assert not hasattr(base_request, "website_type")

def test_activity_status_never_enters_scoring(base_request):
    assert not hasattr(base_request, "activity_status")

def test_reviewer_notes_never_enter_scoring(base_request):
    assert not hasattr(base_request, "reviewer_notes")

def test_manual_evidence_urls_never_enter_scoring(base_request):
    assert not hasattr(base_request, "evidence_url_1")

def test_usable_primary_html_with_meaningful_signals_can_satisfy_gate(classifier, current_time, base_request):
    base_request.verified_threshold = 0
    base_request.gaming_minimum = 0
    base_request.media_minimum = 0
    acq = AcquisitionResult(
        domain="gamingnews.com",
        transport_success=True,
        usable_evidence_found=True,
        primary_page=_page("https://gamingnews.com", current_time, html="<html><nav><a href='/ps5'>PS5 News</a><a href='/reviews'>Reviews</a></nav><article><h1>The Best PS5 Games of 2024</h1></article><article><h1>Elden Ring DLC Review</h1></article><footer><a href='/about'>About GamingNews</a></footer></body></html>")
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "verified"

def test_usable_supporting_html_with_meaningful_signals_can_satisfy_gate(classifier, current_time, base_request):
    base_request.verified_threshold = 0
    base_request.gaming_minimum = 0
    base_request.media_minimum = 0
    acq = AcquisitionResult(
        domain="gamingnews.com",
        transport_success=True,
        usable_evidence_found=True,
        primary_page=_page("https://gamingnews.com", current_time, html="<html><body><a href='/news'>Enter Site</a></body></html>"),
        supporting_pages=[
            _page("https://gamingnews.com/news", current_time, html="<html><nav><a href='/ps5'>PS5 News</a><a href='/reviews'>Reviews</a></nav><article><h1>The Best PS5 Games of 2024</h1></article><article><h1>Elden Ring DLC Review</h1></article><footer><a href='/about'>About GamingNews</a></footer></body></html>")
        ]
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "verified"

def test_two_valid_feed_entries_plus_independent_identity_can_satisfy_gate(classifier, current_time, base_request):
    base_request.verified_threshold = 0
    base_request.gaming_minimum = 0
    base_request.media_minimum = 0
    acq = AcquisitionResult(
        domain="gamingnews.com",
        transport_success=True,
        usable_evidence_found=True,
        primary_page=_page("https://gamingnews.com", current_time, html="<html><head><meta property='og:site_name' content='GamingNews - Video Game Reviews'/></head><body></body></html>"),
        feed_entries=[
            FeedEntry(title="GTA 6 Trailer Analysis", url="https://gamingnews.com/gta6"),
            FeedEntry(title="Elden Ring DLC Review", url="https://gamingnews.com/eldenring")
        ]
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "verified"

def test_feed_url_without_entries_cannot_satisfy_gate(classifier, current_time, base_request):
    acq = AcquisitionResult(
        domain="gamingnews.com",
        transport_success=True,
        usable_evidence_found=True,
        primary_page=_page("https://gamingnews.com", current_time, html="<html><head><meta property='og:site_name' content='GamingNews - Video Game Reviews'/></head><body></body></html>"),
        feed_entries=[]
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "uncertain"

def test_sitemap_urls_alone_cannot_satisfy_gate(classifier, current_time, base_request):
    acq = AcquisitionResult(
        domain="gamingnews.com",
        transport_success=True,
        usable_evidence_found=True,
        primary_page=_page("https://gamingnews.com", current_time, html="<html><body></body></html>"),
        sitemap_candidates=[
            {"url": "https://gamingnews.com/article1"},
            {"url": "https://gamingnews.com/article2"}
        ]
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "uncertain"

def test_strong_structured_retailer_identity_can_support_rejection(classifier, current_time, base_request):
    base_request.uncertain_threshold = 100
    base_request.technical_minimum = 0
    html = '''<html>
            <script type="application/ld+json">
            {"@type": "Product", "name": "PS5 Console", "offers": {"@type": "Offer", "price": "499"}}
            </script>
            <nav><a href="/cart">Shopping Cart</a>
            <a href="/checkout">Checkout</a></nav>
            </body></html>'''
    acq = AcquisitionResult(
        domain="gamestore.com",
        transport_success=True,
        usable_evidence_found=True,
        primary_page=_page("https://gamestore.com", current_time, html=html)
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "rejected"

def test_missing_positive_evidence_alone_cannot_support_rejection(classifier, current_time, base_request):
    acq = AcquisitionResult(
        domain="example.com",
        transport_success=True,
        usable_evidence_found=True,
        primary_page=_page("https://example.com", current_time, html="<html><body>Welcome to my personal blog.</body></html>")
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "uncertain"

def test_technical_minimum_zero_does_not_disable_gate(classifier, current_time, base_request):
    base_request.technical_minimum = 0
    acq = AcquisitionResult(
        domain="gamingnews.com",
        transport_success=True,
        usable_evidence_found=False,
        primary_page=_page("https://gamingnews.com", current_time, status=403, success=False, html="")
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "uncertain"

def test_v2_without_evidence_context_returns_uncertain(classifier, current_time, base_request):
    acq = AcquisitionResult(
        domain="example.com",
        transport_success=False,
        usable_evidence_found=False
    )
    res = classifier.classify_acquisition(acq, current_time, base_request)
    assert res.predicted_status == "uncertain"

def test_baseline_classifier_remains_backward_compatible():
    from app.verification.classifier import Classifier
    c = Classifier(get_settings())
    assert hasattr(c, "classify")
