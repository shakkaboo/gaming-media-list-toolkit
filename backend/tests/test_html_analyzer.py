import pytest
from app.verification.html_analyzer import HtmlAnalyzer

def test_html_analyzer_extracts_metadata():
    html = """
    <html lang="en-US">
    <head>
        <title>Gaming News - IGN</title>
        <meta name="description" content="Latest gaming news and reviews">
        <meta property="og:title" content="IGN Open Graph Title">
        <meta property="og:description" content="IGN Open Graph Desc">
        <meta property="og:site_name" content="IGN">
        <link rel="canonical" href="https://www.ign.com/">
    </head>
    <body>
        <h1>Main Heading</h1>
        <nav><a href="/news">News</a> <button>Reviews</button></nav>
        <footer><p>Copyright 2026</p></footer>
    </body>
    </html>
    """
    analyzer = HtmlAnalyzer(html)
    signals = analyzer.analyze()
    
    assert signals.page_title == "Gaming News - IGN"
    assert signals.meta_description == "Latest gaming news and reviews"
    assert signals.og_title == "IGN Open Graph Title"
    assert signals.og_site_name == "IGN"
    assert signals.html_language == "en-US"
    assert signals.canonical_url == "https://www.ign.com/"
    assert "Main Heading" in signals.headings
    assert "News" in signals.navigation_labels
    assert "Reviews" in signals.navigation_labels
    assert "Copyright 2026" in signals.footer_text

def test_html_analyzer_extracts_links():
    html = """
    <html><body>
        <a href="/news/article-1">Article 1</a>
        <a href="/author/john-doe" rel="author">John Doe</a>
        <a href="/contact">Contact</a>
    </body></html>
    """
    analyzer = HtmlAnalyzer(html)
    signals = analyzer.analyze()
    
    assert "/news/article-1" in signals.article_links
    assert "/author/john-doe" in signals.author_links
    assert "/contact" not in signals.article_links

def test_html_analyzer_extracts_json_ld():
    html = """
    <html><head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "NewsArticle",
            "headline": "Game Review",
            "datePublished": "2026-06-12T12:00:00Z"
        }
        </script>
    </head><body></body></html>
    """
    analyzer = HtmlAnalyzer(html)
    signals = analyzer.analyze()
    
    assert "NewsArticle" in signals.json_ld_types
    assert "2026-06-12T12:00:00Z" in signals.detected_publication_dates

def test_html_analyzer_detects_challenges():
    html = """<html><head><title>Just a moment...</title></head><body></body></html>"""
    analyzer = HtmlAnalyzer(html)
    signals = analyzer.analyze()
    
    assert "cloudflare_challenge" in signals.challenge_indicators
