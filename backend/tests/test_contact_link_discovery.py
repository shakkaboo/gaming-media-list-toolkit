import pytest
from app.contacts.link_discovery import LinkDiscoverer
from app.schemas.search import NormalizedCandidate

def test_discover_links():
    discoverer = LinkDiscoverer()
    html = """
    <html>
        <body>
            <a href="/contact">Contact Us</a>
            <a href="/about-us">About</a>
            <a href="/advertise">Advertise with us</a>
            <a href="/editorial">Meet the editors</a>
            <a href="/privacy">Privacy Policy</a>
            <a href="/login">Login</a>
            <a href="https://external.com/contact">External Contact</a>
        </body>
    </html>
    """
    
    candidate = NormalizedCandidate(
        requested_url="http://example.com",
        normalized_url="http://example.com",
        homepage_url="http://example.com",
        registered_domain="example.com",
        is_multitenant=False,
        original_url="http://example.com",
        title="",
        query_text="",
        provider="",
        result_position=1
    )
    
    links = discoverer.discover_links(html, "http://example.com", candidate)
    
    # external.com/contact should be skipped because of registered_domain
    # privacy, login should be rejected
    urls = [l.url for l in links]
    
    assert "http://example.com/contact" in urls
    assert "http://example.com/advertise" in urls
    assert "http://example.com/editorial" in urls
    assert "http://example.com/about-us" in urls
    assert "http://example.com/privacy" not in urls
    assert "http://example.com/login" not in urls
    assert "https://external.com/contact" not in urls
    
    # check types
    types = {l.url: l.page_type for l in links}
    assert types["http://example.com/contact"] == "contact"
    assert types["http://example.com/advertise"] == "advertising"
    assert types["http://example.com/editorial"] == "editorial"
    assert types["http://example.com/about-us"] == "about"

def test_japanese_links():
    discoverer = LinkDiscoverer()
    html = """
    <html>
        <body>
            <a href="/inquiry">お問い合わせ</a>
            <a href="/company">会社概要</a>
        </body>
    </html>
    """
    candidate = NormalizedCandidate(
        requested_url="http://example.com",
        normalized_url="http://example.com",
        homepage_url="http://example.com",
        registered_domain="example.com",
        is_multitenant=False,
        original_url="http://example.com",
        title="",
        query_text="",
        provider="",
        result_position=1
    )
    
    links = discoverer.discover_links(html, "http://example.com", candidate)
    urls = [l.url for l in links]
    assert "http://example.com/inquiry" in urls
    assert "http://example.com/company" in urls
