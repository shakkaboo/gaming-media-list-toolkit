import pytest
from app.contacts.contact_classifier import ContactClassifier
from app.schemas.contact_discovery import ExtractedContact, ContactEvidence

def test_classify_contact():
    classifier = ContactClassifier()
    
    # 1. Local part match
    contact = ExtractedContact(
        email="editor@example.com",
        normalized_email="editor@example.com",
        primary_type="unknown",
        is_role_based=True,
        is_named_contact=False,
        is_placeholder_suspected=False,
        confidence=0.9,
        rank_score=50,
        evidence=[]
    )
    res = classifier.classify(contact)
    assert res.primary_type == "editorial"
    
    # 2. Context match overrides weak local part
    contact2 = ExtractedContact(
        email="hello@example.com",
        normalized_email="hello@example.com",
        primary_type="unknown",
        is_role_based=True,
        is_named_contact=False,
        is_placeholder_suspected=False,
        confidence=0.9,
        rank_score=50,
        evidence=[
            ContactEvidence(
                source_url="http://example.com/advertise",
                extraction_method="mailto",
                source_page_type="advertising",
                nearby_text="For sponsorship opportunities email us",
                first_seen_order=0
            )
        ]
    )
    res2 = classifier.classify(contact2)
    # hello gives 'general', but context gives 'advertising'
    # advertising has higher priority than general
    assert res2.primary_type == "advertising"
    assert "general" in res2.secondary_types
