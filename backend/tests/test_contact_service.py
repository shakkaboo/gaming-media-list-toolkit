import pytest
import respx
from datetime import datetime, timezone
from app.services.contact_service import ContactService
from app.schemas.search import NormalizedCandidate
from app.schemas.contact_discovery import ContactDiscoveryRequest
import socket

@pytest.fixture
def patch_dns(monkeypatch):
    async def mock_resolve_and_check(self, hostname: str):
        pass
    monkeypatch.setattr("app.fetching.dns_resolver.DNSResolver.resolve_and_check", mock_resolve_and_check)

@pytest.mark.asyncio
async def test_contact_discovery_success(patch_dns, monkeypatch):
    service = ContactService()
    
    monkeypatch.setattr(
        "app.verification.classifier.evaluate_gaming_relevance",
        lambda signals: (50, []),
    )

    monkeypatch.setattr(
        "app.verification.classifier.evaluate_editorial_structure",
        lambda signals: (50, []),
    )
    
    candidate = NormalizedCandidate(
        requested_url="http://example.com/",
        normalized_url="http://example.com/",
        homepage_url="http://example.com/",
        registered_domain="example.com",
        original_url="http://example.com/",
        title="Example Gaming",
        query_text="gaming media",
        provider="mock",
        result_position=1,
        is_multitenant=False
    )
    
    with respx.mock:
        # Mock homepage (verified)
        respx.get("http://example.com/").respond(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            text="""
            <html lang="en">
                <head>
                    <title>Gaming News and Video Game Reviews</title>
                    <meta name="description" content="Latest esports, daily news, and game reviews.">
                </head>
                <body>
                    <nav>
                        <a href="/news">News</a>
                        <a href="/reviews">Reviews</a>
                        <a href="/about">About Us</a>
                        <a href="/contact">Contact Us</a>
                    </nav>
                    <main>
                        <h1>Top Video Games of the Year</h1>
                        <article>
                            <h2>PlayStation 5 Review</h2>
                            <p>An in-depth game review of the latest RPG.</p>
                            <time datetime="2026-06-12">June 12, 2026</time>
                            <a href="/author/john">By John Doe</a>
                            <a href="/author/jane">By Jane Smith</a>
                            <a href="/articles/review1">Review 1</a>
                            <a href="/articles/review2">Review 2</a>
                            <a href="/articles/review3">Review 3</a>
                        </article>
                    </main>
                </body>
            </html>
            """
        )
        
        # Mock robots.txt
        respx.get("http://example.com/robots.txt").respond(
            200,
            headers={"Content-Type": "text/plain; charset=utf-8"},
            text="User-agent: *\nAllow: /"
        )
        
        # Mock contact page
        respx.get("http://example.com/contact").respond(
            200,
            headers={"Content-Type": "text/html; charset=utf-8"},
            text="""
            <html>
                <body>
                    <h1>Contact</h1>
                    <p>Email: editor@example.com</p>
                    <a href="mailto:ads@example.com">Advertising</a>
                </body>
            </html>
            """
        )
        

        
        req = ContactDiscoveryRequest(
            candidates=[candidate],
            allow_uncertain=True
        )
        

        
        req = ContactDiscoveryRequest(
            candidates=[candidate],
            allow_uncertain=True
        )
        
        resp = await service.discover_contacts_batch(req)
        
        if resp.failed_count > 0:
            print("DEBUG RESULT:", resp.results[0])
            
        assert resp.sites_processed == 1
        assert resp.failed_count == 0
        result = resp.results[0]
        if result.verification_status != "verified":
            print("DEBUG VERIFICATION:", result)
        assert result.success is True
        assert result.verification_status == "verified"
        assert len(result.contacts) == 2
        
        emails = {c.normalized_email for c in result.contacts}
        assert "editor@example.com" in emails
        assert "ads@example.com" in emails
        
        best = result.best_contact
        assert best is not None
