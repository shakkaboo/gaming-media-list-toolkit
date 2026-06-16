import os

def test_labeling_guideline_files_exist():
    assert os.path.exists("evaluation/labeling_guidelines.md")
    assert os.path.exists("evaluation/evaluation_dataset_schema.md")
    assert os.path.exists("evaluation/current_verifier_mapping.md")

def test_guidelines_contain_all_labels():
    with open("evaluation/labeling_guidelines.md", "r", encoding="utf-8") as f:
        content = f.read()
    assert "gaming_media" in content
    assert "not_gaming_media" in content
    assert "uncertain" in content

def test_guidelines_contain_all_website_types():
    with open("evaluation/labeling_guidelines.md", "r", encoding="utf-8") as f:
        content = f.read()
    types = [
        "gaming_publication",
        "general_media_gaming_section",
        "game_developer",
        "game_publisher",
        "gaming_retailer",
        "esports_organization",
        "forum_or_community",
        "hardware_or_technology",
        "creator_or_streaming_profile",
        "single_game_site",
        "inactive_or_archived_media",
        "unrelated",
        "ambiguous"
    ]
    for t in types:
        assert t in content

def test_dataset_schema_fields_documented():
    with open("evaluation/evaluation_dataset_schema.md", "r", encoding="utf-8") as f:
        content = f.read()
    fields = [
        "domain", "homepage_url", "expected_label", "website_type",
        "target_market", "language", "activity_status", "label_reason",
        "evidence_summary", "reviewer_notes", "dataset_split"
    ]
    for f in fields:
        assert f in content
        
    assert "development" in content
    assert "test" in content

def test_gaming_media_requires_gaming_and_editorial_evidence():
    with open("evaluation/labeling_guidelines.md", "r", encoding="utf-8") as f:
        content = f.read()
    assert "Meaningful gaming relevance" in content
    assert "Meaningful editorial or publication structure" in content
    assert "Gaming terminology alone is not sufficient." in content

def test_traffic_is_not_relevance_ground_truth():
    with open("evaluation/labeling_guidelines.md", "r", encoding="utf-8") as f:
        content = f.read()
    assert "Do not use traffic metrics to decide whether the site is gaming media" in content or "traffic metrics" in content
