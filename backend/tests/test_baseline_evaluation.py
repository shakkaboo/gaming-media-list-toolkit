import os
import json
import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from evaluation.metrics import (
    calculate_precision, calculate_recall, calculate_f1, calculate_specificity,
    calculate_fpr, calculate_fnr, safe_div, get_binary_outcome, calculate_strict_correctness,
    generate_binary_confusion_matrix
)
from app.schemas.verification import VerificationResult, VerificationPreviewResponse

def test_safe_div():
    assert safe_div(10, 2) == 5.0
    assert safe_div(10, 0) == 0.0

def test_get_binary_outcome():
    # True Positive
    assert get_binary_outcome("gaming_media", "verified") == "TP"
    # False Negative
    assert get_binary_outcome("gaming_media", "rejected") == "FN"
    assert get_binary_outcome("gaming_media", "uncertain") == "ABSTAIN"
    assert get_binary_outcome("gaming_media", "fetch_failed") == "ABSTAIN"
    
    # True Negative
    assert get_binary_outcome("not_gaming_media", "rejected") == "TN"
    # False Positive
    assert get_binary_outcome("not_gaming_media", "verified") == "FP"
    assert get_binary_outcome("not_gaming_media", "uncertain") == "ABSTAIN"
    assert get_binary_outcome("not_gaming_media", "fetch_failed") == "ABSTAIN"
    
    # Ignore expected uncertain
    assert get_binary_outcome("uncertain", "verified") == "IGNORE"
    assert get_binary_outcome("uncertain", "uncertain") == "IGNORE"

def test_strict_correctness():
    assert calculate_strict_correctness("gaming_media", "verified") is True
    assert calculate_strict_correctness("not_gaming_media", "rejected") is True
    assert calculate_strict_correctness("uncertain", "uncertain") is True
    assert calculate_strict_correctness("uncertain", "fetch_failed") is True
    
    assert calculate_strict_correctness("gaming_media", "rejected") is False
    assert calculate_strict_correctness("not_gaming_media", "fetch_failed") is False

def test_metric_calculations():
    # TP=8, FP=2, TN=10, FN=5
    precision = calculate_precision(8, 2)
    assert precision == 0.8
    
    recall = calculate_recall(8, 5)
    assert round(recall, 3) == 0.615
    
    f1 = calculate_f1(precision, recall)
    assert round(f1, 3) == 0.696
    
    specificity = calculate_specificity(10, 2)
    assert specificity == 0.8333333333333334
    
    fpr = calculate_fpr(2, 10)
    assert fpr == 0.16666666666666666
    
    fnr = calculate_fnr(5, 8)
    assert fnr == 0.38461538461538464

def test_confusion_matrix_generation():
    res = generate_binary_confusion_matrix(8, 2, 10, 5, 3)
    assert res["true_positives"] == 8
    assert res["false_positives"] == 2
    assert res["true_negatives"] == 10
    assert res["false_negatives"] == 5
    assert res["abstentions"] == 3

@pytest.mark.asyncio
@patch('evaluation.run_baseline_evaluation.VerificationService')
async def test_run_baseline_evaluation_mocked(MockService):
    from evaluation.run_baseline_evaluation import run_evaluation
    
    # Setup mock to return a default result for everything
    instance = MockService.return_value
    
    def create_mock_result(req):
        return VerificationPreviewResponse(
            results=[VerificationResult(
                requested_url="http://test.com",
                final_url="http://test.com",
                registered_domain="test.com",
                score=80,
                verification_status="verified",
                confidence=1.0,
                gaming_relevance_score=30,
                editorial_structure_score=30,
                activity_score=20,
                publication_identity_score=10,
                negative_penalty=0,
                positive_reasons=[],
                negative_reasons=[],
                detected_categories=[],
                activity_status="active",
                newest_detected_publication_date=None,
                article_count_estimate=0,
                classifier_version="test",
                analysed_at=datetime.now(timezone.utc),
                fetch_success=True,
                fetch_error_code=None,
                safe_error=None,
                market_evidence=[]
            )],
            verified_count=1,
            uncertain_count=0,
            rejected_count=0,
            failed_count=0,
            skipped_count=0
        )
    instance.verify_candidates = AsyncMock(side_effect=create_mock_result)
    
    # Run a fresh evaluation
    await run_evaluation(resume=False, fresh=True)
    
    # Check that output files exist
    assert os.path.exists("evaluation/results/baseline_predictions.csv")
    assert os.path.exists("evaluation/results/baseline_raw_results.json")
    assert os.path.exists("evaluation/results/baseline_metrics.json")
    assert os.path.exists("evaluation/results/baseline_report.md")
    assert os.path.exists("evaluation/results/baseline_error_analysis.md")
    
    with open("evaluation/results/baseline_metrics.json", "r") as f:
        metrics = json.load(f)
        
    assert "development" in metrics
    assert "test" in metrics
    assert "overall" in metrics
    
    # Because we mocked everything to return "verified", TP and FP should populate, FN and TN should be 0.
    assert metrics["overall"]["total_rows"] == 50
