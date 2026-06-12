import pytest
from app.schemas.verification import ExtractedSiteSignals
from app.verification.classifier import Classifier
from app.config import get_settings

def test_classifier_verified():
    classifier = Classifier(get_settings())
    signals = ExtractedSiteSignals(
        page_title="Gaming News & Reviews",
        meta_description="The best video games coverage and esports.",
        navigation_labels=["News", "Reviews", "Features", "PC", "PS5", "Xbox"],
        article_links=["/news/1", "/news/2", "/reviews/1", "/reviews/2"],
        json_ld_types=["NewsArticle", "VideoGame"]
    )
    result = classifier.classify("http://test.com", "http://test.com/", "test.com", signals)
    
    # Needs 18 gaming and 18 editorial
    assert result.gaming_relevance_score >= 18
    assert result.editorial_structure_score >= 18
    assert result.score >= classifier.settings.GAMING_MEDIA_VERIFIED_THRESHOLD
    assert result.verification_status == "verified"

def test_classifier_cloudflare_challenge():
    classifier = Classifier(get_settings())
    signals = ExtractedSiteSignals(
        page_title="Just a moment...",
        challenge_indicators=["cloudflare_challenge"]
    )
    result = classifier.classify("http://test.com", "http://test.com/", "test.com", signals)
    
    assert result.verification_status == "uncertain"
    assert result.score == 0
    assert result.confidence == 0.1
    assert any(r.code == "challenge_page" for r in result.negative_reasons)

def test_classifier_parked_domain():
    classifier = Classifier(get_settings())
    signals = ExtractedSiteSignals(
        page_title="Domain for sale",
        parking_indicators=["domain_parked_or_for_sale"]
    )
    result = classifier.classify("http://test.com", "http://test.com/", "test.com", signals)
    
    assert result.verification_status == "rejected"
    assert result.score == 0
    assert result.confidence == 0.9
    assert any(r.code == "parked_domain" for r in result.negative_reasons)
