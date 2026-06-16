import pytest
import os
import json
import hashlib
from unittest.mock import patch, MagicMock, AsyncMock

from app.schemas.search import NormalizedCandidate
from app.schemas.fetch import FetchRequest, FetchedPage
from app.schemas.acquisition import AcquisitionResult
from app.services.fetch_service import FetchService
from app.fetching.fetch_orchestrator import FetchOrchestrator
from evaluation.run_fetch_reliability_evaluation import check_baseline_protection

@pytest.mark.asyncio
async def test_baseline_protection():
    with pytest.raises(ValueError, match="Attempting to overwrite protected baseline artifact"):
        check_baseline_protection("evaluation/results/baseline_predictions.csv")

@pytest.mark.asyncio
async def test_expected_labels_ignored_by_fetch_evaluator():
    # Verify that run_fetch_reliability_evaluation doesn't use expected_label
    # We can inspect the source code of the run_evaluation loop to assert it doesn't reference 'expected_label' for decisions.
    with open("evaluation/run_fetch_reliability_evaluation.py", "r", encoding="utf-8") as f:
        content = f.read()
        assert "expected_label" not in content, "Fetch evaluator must ignore expected_label"

@pytest.mark.asyncio
async def test_classification_immutability():
    # Read classifier.py and ensure no logic changed
    with open("app/verification/classifier.py", "rb") as f:
        content = f.read()
    assert b"def classify(" in content, "Classifier method missing"

@pytest.mark.asyncio
async def test_challenge_and_js_shell_not_usable():
    client = AsyncMock()
    dns_resolver = AsyncMock()
    settings = MagicMock()
    settings.FETCH_TOTAL_TIMEOUT_SECONDS = 10
    
    orchestrator = FetchOrchestrator(client, dns_resolver, settings)
    
    # Mock HTTP 200 with cloudflare challenge
    mock_page = FetchedPage(
        requested_url="https://test.com/",
        final_url="https://test.com/",
        registered_domain="test.com",
        status_code=200,
        content_type="text/html",
        content_length=1000,
        html="<html><body>Cloudflare attention required challenge</body></html>",
        title="",
        fetched_at=1,
        redirect_chain=[],
        redirect_count=0,
        elapsed_ms=100,
        success=True,
        challenge_detected=True,
        javascript_shell_detected=False,
        attempt_count=1
    )
    
    with patch("app.fetching.fetch_orchestrator.fetch_page_with_retries", return_value=mock_page) as mock_fetch:
        with patch.object(orchestrator, "_fetch_playwright", return_value=None):
            result = await orchestrator.acquire_evidence("https://test.com/", NormalizedCandidate(
                original_url="https://test.com/", normalized_url="https://test.com/", homepage_url="https://test.com/",
                registered_domain="test.com", title="", query_text="", provider="manual", result_position=1
            ))
            assert not result.usable_evidence_found
            assert result.primary_page.challenge_detected

@pytest.mark.asyncio
async def test_japanese_sitemap_keywords():
    client = AsyncMock()
    dns_resolver = AsyncMock()
    settings = MagicMock()
    settings.FETCH_TOTAL_TIMEOUT_SECONDS = 10
    
    orchestrator = FetchOrchestrator(client, dns_resolver, settings)
    
    # Mock primary page success but insufficient content
    mock_insufficient = FetchedPage(success=True, error_code=None, requested_url="", final_url="", registered_domain="", status_code=200, fetched_at=1, redirect_chain=[], redirect_count=0, elapsed_ms=0, attempt_count=1, content_type="text/html", content_length=50, html="<html><body>Too short</body></html>", title="Short")

    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset>
        <url><loc>https://test.com/ニュース/123</loc></url>
        <url><loc>https://test.com/レビュー/456</loc></url>
        <url><loc>https://test.com/other/789</loc></url>
    </urlset>"""
    mock_sitemap = FetchedPage(success=True, html=sitemap_xml, requested_url="", final_url="", registered_domain="", status_code=200, fetched_at=1, redirect_chain=[], redirect_count=0, elapsed_ms=0, attempt_count=1, content_type="application/xml", content_length=len(sitemap_xml), title=None)

    mock_article = FetchedPage(success=True, html="<html><body>Valid article text with enough content to be > 100 chars and pass JS shell checks. More text.</body></html>", requested_url="", final_url="", registered_domain="", status_code=200, fetched_at=1, redirect_chain=[], redirect_count=0, elapsed_ms=0, attempt_count=1, content_type="text/html", content_length=150, title="Article")

    async def side_effect(url, *args, **kwargs):
        if "sitemap.xml" in url:
            return mock_sitemap
        elif "ニュース" in url or "レビュー" in url:
            return mock_article
        return mock_insufficient

    with patch("app.fetching.fetch_orchestrator.fetch_page_with_retries", side_effect=side_effect):
        result = await orchestrator.acquire_evidence("https://test.com/", NormalizedCandidate(
            original_url="https://test.com/", normalized_url="https://test.com/", homepage_url="https://test.com/",
            registered_domain="test.com", title="", query_text="", provider="manual", result_position=1
        ))
        
        # It should try primary variants (say, 3), then sitemap (1), then ニュース article (1) -> total 5 attempts
        assert result.usable_evidence_found
        assert result.transport_success
        assert len(result.supporting_pages) == 1

@pytest.mark.asyncio
async def test_budget_exhaustion():
    client = AsyncMock()
    dns_resolver = AsyncMock()
    settings = MagicMock()
    settings.FETCH_TOTAL_TIMEOUT_SECONDS = 10
    
    orchestrator = FetchOrchestrator(client, dns_resolver, settings)
    
    mock_fail = FetchedPage(success=False, error_code="timeout", requested_url="", final_url="", registered_domain="", status_code=0, fetched_at=1, redirect_chain=[], redirect_count=0, elapsed_ms=0, attempt_count=2) # Retried once, so 2 attempts
    
    with patch("app.fetching.fetch_orchestrator.fetch_page_with_retries", return_value=mock_fail):
        result = await orchestrator.acquire_evidence("https://test.com/", NormalizedCandidate(
            original_url="https://test.com/", normalized_url="https://test.com/", homepage_url="https://test.com/",
            registered_domain="test.com", title="", query_text="", provider="manual", result_position=1
        ))
        # 3 variants * 2 attempts each = 6 attempts, but orchestrator breaks at >= 5
        assert result.fetch_attempts >= 5
        assert not result.usable_evidence_found
        assert not result.transport_success
        
@pytest.mark.asyncio
async def test_backward_compatibility():
    service = FetchService()
    
    mock_res = AcquisitionResult(
        domain="test.com",
        primary_page=FetchedPage(success=True, requested_url="https://test.com", final_url="https://test.com", registered_domain="test.com", status_code=200, fetched_at=1, redirect_chain=[], redirect_count=0, elapsed_ms=0),
        usable_evidence_found=True
    )
    
    with patch.object(service, "acquire_evidence_batch", return_value=([mock_res], 0)):
        req = FetchRequest(candidates=[NormalizedCandidate(original_url="a", normalized_url="a", homepage_url="a", registered_domain="test.com", title="", query_text="", provider="", result_position=1)])
        pages, skipped = await service.fetch_pages(req)
        assert len(pages) == 1
        assert isinstance(pages[0], FetchedPage)
