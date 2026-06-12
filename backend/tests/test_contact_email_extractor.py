import pytest
from app.contacts.email_extractor import EmailExtractor

def test_is_valid_email():
    extractor = EmailExtractor()
    assert extractor.is_valid_email("test@example.com") is True
    assert extractor.is_valid_email("test.name+alias@example.co.uk") is True
    assert extractor.is_valid_email("a"*64 + "@example.com") is True
    assert extractor.is_valid_email("a"*65 + "@example.com") is False
    assert extractor.is_valid_email("test@example.com") is True
    assert extractor.is_valid_email("test@.com") is False
    assert extractor.is_valid_email("test@example") is False
    assert extractor.is_valid_email("test\x00@example.com") is False

def test_validate_and_normalize():
    extractor = EmailExtractor()
    # Good
    assert extractor.validate_and_normalize("John.Doe@Example.com")[1] == "John.Doe@example.com"
    # Placeholders
    assert extractor.validate_and_normalize("example@example.com") is None
    assert extractor.validate_and_normalize("email@example.com") is None
    assert extractor.validate_and_normalize("name@domain.com") is None
    
    # Ambiguous placeholder flagged
    res = extractor.validate_and_normalize("test@test.com")
    assert res is not None
    assert res[3] is True # is_placeholder
    
    res2 = extractor.validate_and_normalize("admin@example.org")
    assert res2 is not None
    assert res2[3] is True # is_placeholder

def test_extract_from_text():
    extractor = EmailExtractor()
    text = "Contact us at info@example.com or reach out to john.doe [at] example [dot] com."
    contacts = extractor._extract_from_text(text, "visible_text", "http://example.com", "contact", 0)
    
    emails = [c.normalized_email for c in contacts]
    assert "info@example.com" in emails
    assert "john.doe@example.com" in emails
    
    info_c = next(c for c in contacts if c.normalized_email == "info@example.com")
    assert info_c.is_role_based is True
    
    john_c = next(c for c in contacts if c.normalized_email == "john.doe@example.com")
    assert john_c.is_role_based is False
    assert john_c.is_named_contact is True

def test_extract_from_html():
    extractor = EmailExtractor()
    html = """
    <html>
        <body>
            <a href="mailto:tips@example.com">Send Tips</a>
            <p>Email: PR@example.com</p>
            <script type="application/ld+json">
                {"@type": "ContactPoint", "email": "support@example.com", "contactType": "customer support"}
            </script>
        </body>
    </html>
    """
    contacts = extractor.extract_from_html(html, "http://example.com", "contact", 0)
    emails = {c.normalized_email: c.evidence[0].extraction_method for c in contacts}
    
    assert "tips@example.com" in emails
    assert emails["tips@example.com"] == "mailto"
    
    assert "PR@example.com" in emails
    assert emails["PR@example.com"] == "visible_text"
    
    assert "support@example.com" in emails
    assert emails["support@example.com"] == "json_ld"
