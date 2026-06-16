import os
import csv
import json
import subprocess
from tempfile import NamedTemporaryFile

def _get_canonical_domain(url_or_domain: str) -> str:
    d = url_or_domain.replace("https://", "").replace("http://", "").split("/")[0]
    return d.removeprefix("www.")

DATASET_PATH = "evaluation/gaming_media_evaluation.csv"

def test_dataset_exists():
    assert os.path.exists(DATASET_PATH)

def test_dataset_requirements():
    expected_columns = [
        "domain", "homepage_url", "expected_label", "website_type",
        "target_market", "language", "activity_status", "label_reason",
        "evidence_summary", "reviewer_notes", "dataset_split",
        "evidence_url_1", "evidence_url_2", "reviewed_at", "review_method"
    ]

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == expected_columns

        records = list(reader)
        assert len(records) == 50

        dev_count = 0
        test_count = 0
        domains = set()

        for row in records:
            assert len(row) == len(expected_columns)
            r = dict(zip(expected_columns, row))

            canon = _get_canonical_domain(r["domain"])
            assert canon not in domains
            domains.add(canon)
            
            assert r["evidence_url_1"].startswith("http")
            assert r["reviewed_at"] != ""
            assert r["review_method"] == "manual_public_web_review"

def test_validator_succeeds_on_real_dataset():
    result = subprocess.run(["python", "evaluation/validate_dataset.py"], capture_output=True, text=True)
    assert result.returncode == 0

def _run_modified_validator(csv_content):
    with open("evaluation/validate_dataset.py", "r", encoding="utf-8") as f:
        val_code = f.read()

    with NamedTemporaryFile(mode='w', delete=False, suffix=".csv", encoding="utf-8", newline='') as temp_csv:
        temp_csv.write(csv_content)
        temp_path = temp_csv.name

    mod_val_code = val_code.replace('"evaluation/gaming_media_evaluation.csv"', f'r"{temp_path}"')
    
    with NamedTemporaryFile(mode='w', delete=False, suffix=".py", encoding="utf-8") as temp_py:
        temp_py.write(mod_val_code)
        py_path = temp_py.name

    result = subprocess.run(["python", py_path], capture_output=True, text=True)
    os.remove(temp_path)
    os.remove(py_path)
    return result

def _get_base_content():
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        return f.read()

def test_validator_detects_duplicate_domain():
    lines = _get_base_content().splitlines()
    lines[-1] = lines[-2]
    result = _run_modified_validator("\n".join(lines))
    assert result.returncode != 0 and "Duplicate canonical domain" in result.stdout

def test_validator_detects_invalid_label():
    result = _run_modified_validator(_get_base_content().replace("gaming_media", "super_gaming_media", 1))
    assert result.returncode != 0 and "Invalid label" in result.stdout

def test_validator_detects_invalid_website_type():
    result = _run_modified_validator(_get_base_content().replace("gaming_publication", "fake_type", 1))
    assert result.returncode != 0 and "Invalid website_type" in result.stdout

def test_validator_detects_invalid_activity():
    result = _run_modified_validator(_get_base_content().replace(",active,", ",super_active,", 1))
    assert result.returncode != 0 and "Invalid activity_status" in result.stdout

def test_validator_detects_incorrect_split_count():
    result = _run_modified_validator(_get_base_content().replace("development", "test", 1))
    assert result.returncode != 0 and "Expected 35 development records" in result.stdout

def test_validator_detects_blank_label_reason():
    # Replace the reason in the first record with blank. We'll do it naively.
    lines = _get_base_content().splitlines()
    header = lines[0]
    row = list(csv.reader([lines[1]]))[0]
    row[7] = " " # label_reason
    
    with NamedTemporaryFile(mode='w', delete=False, suffix=".csv", encoding="utf-8", newline='') as temp_csv:
        writer = csv.writer(temp_csv)
        writer.writerow(header.split(","))
        writer.writerow(row)
        for line in lines[2:]:
            writer.writerow(list(csv.reader([line]))[0])
        temp_path = temp_csv.name
        
    with open(temp_path, "r", encoding="utf-8") as f:
        content = f.read()
    os.remove(temp_path)
    
    result = _run_modified_validator(content)
    assert result.returncode != 0 and "Blank label_reason" in result.stdout

def test_validator_detects_blank_evidence_summary():
    lines = _get_base_content().splitlines()
    row = list(csv.reader([lines[1]]))[0]
    row[8] = " " # evidence_summary
    
    with NamedTemporaryFile(mode='w', delete=False, suffix=".csv", encoding="utf-8", newline='') as temp_csv:
        writer = csv.writer(temp_csv)
        writer.writerow(lines[0].split(","))
        writer.writerow(row)
        for line in lines[2:]:
            writer.writerow(list(csv.reader([line]))[0])
        temp_path = temp_csv.name
        
    with open(temp_path, "r", encoding="utf-8") as f:
        content = f.read()
    os.remove(temp_path)
    result = _run_modified_validator(content)
    assert result.returncode != 0 and "Blank evidence_summary" in result.stdout

def test_validator_detects_missing_evidence_url():
    lines = _get_base_content().splitlines()
    row = list(csv.reader([lines[1]]))[0]
    row[11] = " " # evidence_url_1
    
    with NamedTemporaryFile(mode='w', delete=False, suffix=".csv", encoding="utf-8", newline='') as temp_csv:
        writer = csv.writer(temp_csv)
        writer.writerow(lines[0].split(","))
        writer.writerow(row)
        for line in lines[2:]:
            writer.writerow(list(csv.reader([line]))[0])
        temp_path = temp_csv.name
        
    with open(temp_path, "r", encoding="utf-8") as f:
        content = f.read()
    os.remove(temp_path)
    result = _run_modified_validator(content)
    assert result.returncode != 0 and "Missing evidence_url_1" in result.stdout

def test_validator_detects_invalid_url_scheme():
    lines = _get_base_content().splitlines()
    row = list(csv.reader([lines[1]]))[0]
    row[11] = "ftp://bad.com" 
    
    with NamedTemporaryFile(mode='w', delete=False, suffix=".csv", encoding="utf-8", newline='') as temp_csv:
        writer = csv.writer(temp_csv)
        writer.writerow(lines[0].split(","))
        writer.writerow(row)
        for line in lines[2:]:
            writer.writerow(list(csv.reader([line]))[0])
        temp_path = temp_csv.name
        
    with open(temp_path, "r", encoding="utf-8") as f:
        content = f.read()
    os.remove(temp_path)
    result = _run_modified_validator(content)
    assert result.returncode != 0 and "Invalid evidence URL scheme" in result.stdout

def test_validator_detects_fictitious_domain():
    result = _run_modified_validator(_get_base_content().replace("famitsu.com", "example.com", 1))
    assert result.returncode != 0 and "Fictitious domain" in result.stdout

def test_validator_detects_missing_review_date():
    lines = _get_base_content().splitlines()
    row = list(csv.reader([lines[1]]))[0]
    row[13] = " " # reviewed_at
    
    with NamedTemporaryFile(mode='w', delete=False, suffix=".csv", encoding="utf-8", newline='') as temp_csv:
        writer = csv.writer(temp_csv)
        writer.writerow(lines[0].split(","))
        writer.writerow(row)
        for line in lines[2:]:
            writer.writerow(list(csv.reader([line]))[0])
        temp_path = temp_csv.name
        
    with open(temp_path, "r", encoding="utf-8") as f:
        content = f.read()
    os.remove(temp_path)
    result = _run_modified_validator(content)
    assert result.returncode != 0 and "Blank reviewed_at" in result.stdout

def test_validator_detects_invalid_review_method():
    result = _run_modified_validator(_get_base_content().replace("manual_public_web_review", "fake_method", 1))
    assert result.returncode != 0 and "Invalid review_method" in result.stdout

def test_validator_detects_no_positive_examples():
    result = _run_modified_validator(_get_base_content().replace(",gaming_media,", ",not_gaming_media,"))
    assert result.returncode != 0 and "missing positive or negative" in result.stdout

def test_validator_detects_no_negative_examples():
    result = _run_modified_validator(_get_base_content().replace(",not_gaming_media,", ",gaming_media,").replace(",uncertain,", ",gaming_media,"))
    assert result.returncode != 0 and "missing positive or negative" in result.stdout

def test_validator_detects_only_one_website_type():
    # Make everything gaming_publication
    content = _get_base_content()
    import re
    content = re.sub(r',(general_media_gaming_section|game_developer|game_publisher|gaming_retailer|esports_organization|forum_or_community|hardware_or_technology|creator_or_streaming_profile|single_game_site|inactive_or_archived_media|ambiguous),', ',gaming_publication,', content)
    result = _run_modified_validator(content)
    assert result.returncode != 0 and "must contain more than one website type" in result.stdout
