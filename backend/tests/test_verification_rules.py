import pytest
from datetime import datetime, timezone, timedelta
from app.schemas.verification import ExtractedSiteSignals
from app.verification.rules import (
    evaluate_gaming_relevance,
    evaluate_editorial_structure,
    evaluate_activity,
    evaluate_publication_identity,
    evaluate_negative_penalties,
    detect_categories
)

def test_evaluate_gaming_relevance():
    signals = ExtractedSiteSignals(
        page_title="PC Gaming News and Esports",
        headings=["Latest PlayStation 5 Games", "Xbox Reviews"],
        json_ld_types=["VideoGame"]
    )
    score, reasons = evaluate_gaming_relevance(signals)
    assert score > 0
    assert any(r.code == "gaming_meta" for r in reasons)
    assert any(r.code == "platform_nav" for r in reasons)
    assert any(r.code == "gaming_structured_data" for r in reasons)

def test_evaluate_editorial_structure():
    signals = ExtractedSiteSignals(
        navigation_labels=["News", "Reviews", "Features"],
        article_links=["/news/game-delayed", "/reviews/halo", "/guides/zelda"],
        json_ld_types=["NewsArticle"]
    )
    score, reasons = evaluate_editorial_structure(signals)
    assert score > 0
    assert any(r.code == "editorial_nav" for r in reasons)
    assert any(r.code == "article_links" for r in reasons)
    assert any(r.code == "editorial_schema" for r in reasons)

def test_evaluate_activity():
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(days=10)).isoformat()
    signals = ExtractedSiteSignals(
        detected_publication_dates=[recent]
    )
    score, status, newest_str, reasons = evaluate_activity(signals, now)
    assert score == 15
    assert status == "active_recently"
    assert newest_str is not None

def test_evaluate_negative_penalties():
    signals = ExtractedSiteSignals(
        page_title="Buy Now - Shopping Cart",
        footer_text=["Developed by Awesome Studio"],
        headings=["Play online casino slots"]
    )
    penalty, reasons = evaluate_negative_penalties(signals)
    assert penalty >= 80
    assert any(r.code == "store_signals" for r in reasons)
    assert any(r.code == "developer_signals" for r in reasons)
    assert any(r.code == "casino_signals" for r in reasons)

def test_detect_categories():
    signals = ExtractedSiteSignals(
        page_title="PC and Mobile Esports News",
        headings=["Hardware reviews", "Indie games"]
    )
    cats = detect_categories(signals)
    assert "esports" in cats
    assert "gaming_news" in cats
    assert "pc_gaming" in cats
    assert "mobile_gaming" in cats
    assert "hardware" in cats
    assert "indie_games" in cats
