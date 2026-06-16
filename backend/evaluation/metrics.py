from typing import Dict, Any

def safe_div(num: float, den: float) -> float:
    if den == 0:
        return 0.0
    return float(num) / float(den)

def calculate_precision(tp: int, fp: int) -> float:
    return safe_div(tp, tp + fp)

def calculate_recall(tp: int, fn: int) -> float:
    return safe_div(tp, tp + fn)

def calculate_f1(precision: float, recall: float) -> float:
    return safe_div(2 * precision * recall, precision + recall)

def calculate_specificity(tn: int, fp: int) -> float:
    return safe_div(tn, tn + fp)

def calculate_accuracy(correct: int, total: int) -> float:
    return safe_div(correct, total)

def calculate_fpr(fp: int, tn: int) -> float:
    return safe_div(fp, fp + tn)

def calculate_fnr(fn: int, tp: int) -> float:
    return safe_div(fn, fn + tp)

def get_binary_outcome(expected_label: str, raw_verifier_status: str) -> str:
    """
    Returns one of: 'TP', 'TN', 'FP', 'FN', 'ABSTAIN', 'IGNORE'
    'IGNORE' is used when expected_label is 'uncertain'.
    """
    if expected_label == "uncertain":
        return "IGNORE"
        
    if raw_verifier_status in ["uncertain", "fetch_failed"]:
        return "ABSTAIN"
        
    if expected_label == "gaming_media":
        if raw_verifier_status == "verified":
            return "TP"
        else:
            return "FN"
            
    if expected_label == "not_gaming_media":
        if raw_verifier_status == "rejected":
            return "TN"
        else:
            return "FP"
            
    return "IGNORE"

def calculate_strict_correctness(expected_label: str, raw_verifier_status: str) -> bool:
    if expected_label == "gaming_media" and raw_verifier_status == "verified":
        return True
    if expected_label == "not_gaming_media" and raw_verifier_status == "rejected":
        return True
    if expected_label == "uncertain" and raw_verifier_status in ["uncertain", "fetch_failed"]:
        return True
    return False

def generate_binary_confusion_matrix(tp: int, fp: int, tn: int, fn: int, abstentions: int) -> Dict[str, Any]:
    return {
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "abstentions": abstentions
    }
