import pytest
from app.contacts.form_detector import FormDetector

def test_detect_contact_form():
    detector = FormDetector()
    html = """
    <html>
        <body>
            <form action="/submit" method="post">
                <h2>Contact Us</h2>
                <input type="text" name="name" />
                <input type="email" name="email" />
                <textarea name="message"></textarea>
                <input type="submit" value="Send" />
            </form>
        </body>
    </html>
    """
    forms = detector.detect_forms(html, "http://example.com/contact", "example.com")
    assert len(forms) == 1
    form = forms[0]
    assert form.purpose == "contact"
    assert "message" in form.field_names
    assert form.action_url == "http://example.com/submit"
    assert form.is_external is False

def test_reject_login_form():
    detector = FormDetector()
    html = """
    <html>
        <body>
            <form action="/login" method="post">
                <input type="text" name="username" />
                <input type="password" name="password" />
                <input type="submit" value="Login" />
            </form>
        </body>
    </html>
    """
    forms = detector.detect_forms(html, "http://example.com", "example.com")
    assert len(forms) == 0 # Rejected due to password and action='login'

def test_detect_external_form():
    detector = FormDetector()
    html = """
    <html>
        <body>
            <form action="https://docs.google.com/forms/d/e/1FAIpQLSxyz/formResponse">
                <input type="text" name="entry.123" />
                <p>Send us a message</p>
                <input type="submit" />
            </form>
        </body>
    </html>
    """
    forms = detector.detect_forms(html, "http://example.com/contact", "example.com")
    assert len(forms) == 1
    assert forms[0].is_external is True
