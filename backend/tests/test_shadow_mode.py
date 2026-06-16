"""
Shadow-mode integration tests for v2_shadow classifier_version.

Verifies:
  - Baseline is the returned production decision.
  - v2 result is attached only under v2_shadow, not at top level.
  - v2 exception does not fail or alter the baseline result.
  - v2 timeout returns baseline plus a shadow error status.
  - Requesting 'baseline' never instantiates ClassifierV2.
  - Requesting 'v2_shadow' does not modify Phase 6 artifacts.
  - v2_shadow field is optional and defaults to None (API backwards-compat).
"""
import asyncio
import hashlib
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.schemas.verification import (
    VerificationRequest, VerificationResult, V2ShadowResult, VerificationResultV2,
    NormalizedMultilingualEvidence,
)
from app.schemas.search import NormalizedCandidate
from app.schemas.acquisition import AcquisitionResult
from app.schemas.fetch import FetchedPage
from app.config import get_settings
from app.services.verification_service import VerificationService

NOW = datetime.now(timezone.utc)


# ── helpers ─────────────────────────────────────────────────────────────────

def _nc(domain="shadow-test.com"):
    return NormalizedCandidate(
        original_url=f"http://{domain}", normalized_url=f"http://{domain}",
        homepage_url=f"http://{domain}", registered_domain=domain,
        title="Test", query_text="test", provider="test", result_position=1,
    )


def _req(domain="shadow-test.com", mode="v2_shadow"):
    return VerificationRequest(candidates=[_nc(domain)], classifier_version=mode)


def _page(domain="shadow-test.com"):
    return FetchedPage(
        requested_url=f"http://{domain}", final_url=f"http://{domain}",
        registered_domain=domain, status_code=200,
        html="<html><title>Game Reviews</title></html>",
        fetched_at=NOW, success=True,
        content_type="text/html", content_length=100,
    )


def _acq(domain="shadow-test.com"):
    acq = AcquisitionResult(domain=domain, transport_success=True, usable_evidence_found=True)
    acq.primary_page = _page(domain)
    return acq


def _baseline_result(domain="shadow-test.com", status="verified"):
    from app.verification.classifier import CLASSIFIER_VERSION
    return VerificationResult(
        requested_url=f"http://{domain}", final_url=f"http://{domain}",
        registered_domain=domain, score=75,
        verification_status=status, confidence=0.8,
        gaming_relevance_score=20, editorial_structure_score=15,
        activity_score=10, publication_identity_score=5, negative_penalty=0,
        activity_status="active", article_count_estimate=5,
        classifier_version=CLASSIFIER_VERSION,
        analysed_at=NOW, fetch_success=True, market_evidence=[],
    )


def _v2_result(domain="shadow-test.com", status="verified"):
    return VerificationResultV2(
        requested_url=f"http://{domain}", final_url=f"http://{domain}",
        registered_domain=domain,
        classifier_version="v2_multilingual_explainable",
        gaming_score=20, media_score=18, market_score=10,
        activity_score=8, technical_score=3,
        component_sum=59, contextual_deductions=0, total_score=59,
        predicted_status=status,
        relevance_label="gaming_media" if status == "verified" else "uncertain",
        market_status="confirmed",
        decision_reason="Score meets verified threshold.",
        analysed_at=NOW, fetch_success=True,
    )


# ── Test 1: Baseline is the production decision ──────────────────────────────

@pytest.mark.asyncio
async def test_shadow_baseline_is_production_decision():
    """Top-level verification_status must reflect the baseline, not v2."""
    svc = VerificationService()
    baseline_res = _baseline_result(status="verified")
    v2_res = _v2_result(status="uncertain")  # v2 disagrees; baseline must win

    with patch.object(svc.fetch_service, "acquire_evidence_batch",
                      new_callable=AsyncMock, return_value=([_acq()], 0)):
        with patch.object(svc, "_verify_page_sync", return_value=baseline_res):
            with patch("app.verification.classifier_v2.ClassifierV2") as MockV2:
                MockV2.return_value.classify_acquisition.return_value = v2_res
                resp = await svc.verify_candidates(_req())

    assert resp.verified_count == 1
    result = resp.results[0]
    assert result.verification_status == "verified"   # baseline decision preserved
    assert result.score == 75                         # baseline score preserved


# ── Test 2: v2 attached only under v2_shadow ────────────────────────────────

@pytest.mark.asyncio
async def test_shadow_v2_result_attached_under_v2_shadow():
    """v2 output populates v2_shadow; it does not overwrite top-level baseline fields."""
    svc = VerificationService()
    baseline_res = _baseline_result(status="uncertain")
    v2_res = _v2_result(status="verified")

    with patch.object(svc.fetch_service, "acquire_evidence_batch",
                      new_callable=AsyncMock, return_value=([_acq()], 0)):
        with patch.object(svc, "_verify_page_sync", return_value=baseline_res):
            with patch("app.verification.classifier_v2.ClassifierV2") as MockV2:
                MockV2.return_value.classify_acquisition.return_value = v2_res
                resp = await svc.verify_candidates(_req())

    result = resp.results[0]
    assert result.verification_status == "uncertain"   # baseline status
    assert result.v2_shadow is not None
    assert isinstance(result.v2_shadow, V2ShadowResult)
    assert result.v2_shadow.v2_predicted_status == "verified"
    assert result.v2_shadow.gaming_score == 20
    assert result.v2_shadow.media_score == 18
    assert result.v2_shadow.total_score == 59
    assert result.v2_shadow.review_recommendation == "review_v2_positive"


# ── Test 3: v2 exception does not fail or alter baseline ────────────────────

@pytest.mark.asyncio
async def test_shadow_v2_exception_does_not_affect_baseline():
    """RuntimeError from v2 returns baseline result with shadow error status; no crash."""
    svc = VerificationService()
    baseline_res = _baseline_result(status="verified")

    with patch.object(svc.fetch_service, "acquire_evidence_batch",
                      new_callable=AsyncMock, return_value=([_acq()], 0)):
        with patch.object(svc, "_verify_page_sync", return_value=baseline_res):
            with patch("app.verification.classifier_v2.ClassifierV2") as MockV2:
                MockV2.return_value.classify_acquisition.side_effect = RuntimeError("v2 crashed")
                resp = await svc.verify_candidates(_req())

    assert len(resp.results) == 1
    result = resp.results[0]
    assert result.verification_status == "verified"     # baseline unaffected
    assert result.score == 75                           # baseline score intact
    assert result.v2_shadow is not None
    assert result.v2_shadow.v2_predicted_status == "error"
    assert result.v2_shadow.review_recommendation == "v2_error"
    assert "RuntimeError" in result.v2_shadow.v2_explanation


# ── Test 4: v2 timeout returns baseline plus shadow error/review status ──────

@pytest.mark.asyncio
async def test_shadow_v2_timeout_returns_baseline_with_error_shadow():
    """asyncio.TimeoutError from v2 returns baseline cleanly; v2_shadow shows error."""
    svc = VerificationService()
    baseline_res = _baseline_result(status="verified")

    with patch.object(svc.fetch_service, "acquire_evidence_batch",
                      new_callable=AsyncMock, return_value=([_acq()], 0)):
        with patch.object(svc, "_verify_page_sync", return_value=baseline_res):
            with patch("app.verification.classifier_v2.ClassifierV2") as MockV2:
                MockV2.return_value.classify_acquisition.side_effect = asyncio.TimeoutError()
                resp = await svc.verify_candidates(_req())

    result = resp.results[0]
    assert result.verification_status == "verified"
    assert result.v2_shadow is not None
    assert result.v2_shadow.v2_predicted_status == "error"
    assert result.v2_shadow.review_recommendation == "v2_error"
    assert "timed out" in result.v2_shadow.v2_explanation


# ── Test 5: Requesting 'baseline' never runs v2 ──────────────────────────────

@pytest.mark.asyncio
async def test_baseline_mode_never_instantiates_classifier_v2():
    """When classifier_version='baseline', ClassifierV2 must not be instantiated or called."""
    svc = VerificationService()
    baseline_res = _baseline_result(status="verified")

    with patch.object(svc.fetch_service, "acquire_evidence_batch",
                      new_callable=AsyncMock, return_value=([_acq()], 0)):
        with patch.object(svc, "_verify_page_sync", return_value=baseline_res):
            with patch("app.verification.classifier_v2.ClassifierV2") as MockV2:
                resp = await svc.verify_candidates(_req(mode="baseline"))
                MockV2.assert_not_called()

    result = resp.results[0]
    assert result.v2_shadow is None                    # no shadow field in baseline mode


# ── Test 6: v2_shadow does not modify Phase 6 artifacts ─────────────────────

@pytest.mark.asyncio
async def test_shadow_does_not_modify_phase6_artifacts():
    """Running v2_shadow must not alter the Phase 6 lock or predictions CSV."""
    def _hash(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            h.update(f.read())
        return h.hexdigest()

    lock = Path("evaluation/results/phase6_protected_test.lock.json")
    pred = Path("evaluation/results/phase6_test_predictions.csv")
    lock_hash_before = _hash(lock) if lock.exists() else None
    pred_hash_before = _hash(pred) if pred.exists() else None

    svc = VerificationService()
    with patch.object(svc.fetch_service, "acquire_evidence_batch",
                      new_callable=AsyncMock, return_value=([_acq()], 0)):
        with patch.object(svc, "_verify_page_sync", return_value=_baseline_result()):
            with patch("app.verification.classifier_v2.ClassifierV2") as MockV2:
                MockV2.return_value.classify_acquisition.return_value = _v2_result()
                await svc.verify_candidates(_req())

    if lock_hash_before is not None:
        assert _hash(lock) == lock_hash_before, "Phase 6 lock file was modified!"
    if pred_hash_before is not None:
        assert _hash(pred) == pred_hash_before, "Phase 6 predictions CSV was modified!"


# ── Test 7: v2_shadow field defaults to None (API backwards-compat) ──────────

def test_v2_shadow_field_optional_defaults_none():
    """VerificationResult.v2_shadow defaults to None; serialization is unchanged
    for existing baseline callers that do not set it."""
    from app.verification.classifier import CLASSIFIER_VERSION
    r = VerificationResult(
        requested_url="http://x", final_url="http://x",
        registered_domain="x", score=0,
        verification_status="uncertain", confidence=0.0,
        gaming_relevance_score=0, editorial_structure_score=0,
        activity_score=0, publication_identity_score=0, negative_penalty=0,
        activity_status="unknown", article_count_estimate=0,
        classifier_version=CLASSIFIER_VERSION,
        analysed_at=NOW, fetch_success=False, market_evidence=[],
    )
    assert r.v2_shadow is None
    dumped = r.model_dump()
    assert "v2_shadow" in dumped
    assert dumped["v2_shadow"] is None


# ── Test 8: review_recommendation logic coverage ─────────────────────────────

@pytest.mark.asyncio
async def test_shadow_agree_when_both_verified():
    """review_recommendation is 'agree' when baseline and v2 both produce 'verified'."""
    svc = VerificationService()
    baseline_res = _baseline_result(status="verified")
    v2_res = _v2_result(status="verified")

    with patch.object(svc.fetch_service, "acquire_evidence_batch",
                      new_callable=AsyncMock, return_value=([_acq()], 0)):
        with patch.object(svc, "_verify_page_sync", return_value=baseline_res):
            with patch("app.verification.classifier_v2.ClassifierV2") as MockV2:
                MockV2.return_value.classify_acquisition.return_value = v2_res
                resp = await svc.verify_candidates(_req())

    assert resp.results[0].v2_shadow.review_recommendation == "agree"


@pytest.mark.asyncio
async def test_shadow_v2_abstained_when_v2_uncertain():
    """review_recommendation is 'v2_abstained' when v2 status is 'uncertain'."""
    svc = VerificationService()
    baseline_res = _baseline_result(status="verified")
    v2_res = _v2_result(status="uncertain")

    with patch.object(svc.fetch_service, "acquire_evidence_batch",
                      new_callable=AsyncMock, return_value=([_acq()], 0)):
        with patch.object(svc, "_verify_page_sync", return_value=baseline_res):
            with patch("app.verification.classifier_v2.ClassifierV2") as MockV2:
                MockV2.return_value.classify_acquisition.return_value = v2_res
                resp = await svc.verify_candidates(_req())

    assert resp.results[0].v2_shadow.review_recommendation == "v2_abstained"
