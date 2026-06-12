import pytest
from app.schemas.search import SearchResult
from app.services.candidate_processor import process_search_results

def create_result(url, query_text="q", position=1, provider="mock"):
    return SearchResult(
        url=url,
        title="Test",
        snippet="Snippet",
        query_text=query_text,
        provider=provider,
        position=position,
        language="en"
    )

def test_article_urls_from_same_publisher_collapse():
    r1 = create_result("https://ign.com/news/1", position=1)
    r2 = create_result("https://ign.com/news/2", position=2)
    resp = process_search_results([r1, r2])
    assert resp.accepted_count == 1
    assert resp.duplicate_count == 1
    assert resp.accepted[0].normalized_url == "https://ign.com/news/1"

def test_http_https_duplicates_collapse_with_https_preference():
    r1 = create_result("http://example.com/a", position=1)
    r2 = create_result("https://example.com/a", position=1)
    resp = process_search_results([r1, r2])
    assert resp.accepted_count == 1
    assert resp.accepted[0].normalized_url == "https://example.com/a"

def test_www_and_non_www_collapse():
    r1 = create_result("https://www.example.com/a", position=1)
    r2 = create_result("https://example.com/b", position=2)
    resp = process_search_results([r1, r2])
    assert resp.accepted_count == 1
    assert resp.accepted[0].normalized_url == "https://example.com/a"

def test_earliest_query_wins():
    r1 = create_result("https://example.com/1", query_text="first", position=1)
    r2 = create_result("https://example.com/2", query_text="second", position=1)
    resp = process_search_results([r1, r2])
    assert resp.accepted_count == 1
    assert resp.accepted[0].query_text == "first"

def test_lowest_position_wins():
    r1 = create_result("https://example.com/1", query_text="q", position=1)
    r2 = create_result("https://example.com/2", query_text="q", position=2)
    resp = process_search_results([r1, r2])
    assert resp.accepted_count == 1
    assert resp.accepted[0].result_position == 1

def test_duplicate_provenance_preserved():
    r1 = create_result("https://example.com/1", position=1)
    r2 = create_result("https://example.com/2", position=2)
    resp = process_search_results([r1, r2])
    assert resp.duplicate_count == 1
    assert resp.duplicates[0].duplicate_url == "https://example.com/2"
    assert resp.duplicates[0].kept_url == "https://example.com/1"
    assert resp.duplicates[0].deduplication_key == "example.com"

def test_two_substack_subdomains_remain_separate():
    r1 = create_result("https://a.substack.com", position=1)
    r2 = create_result("https://b.substack.com", position=2)
    resp = process_search_results([r1, r2])
    assert resp.accepted_count == 2
    assert resp.accepted[0].registered_domain == "substack.com"
    assert resp.accepted[1].registered_domain == "substack.com"

def test_two_wordpress_com_subdomains_remain_separate():
    r1 = create_result("https://a.wordpress.com", position=1)
    r2 = create_result("https://b.wordpress.com", position=2)
    resp = process_search_results([r1, r2])
    assert resp.accepted_count == 2

def test_two_blogspot_subdomains_remain_separate():
    r1 = create_result("https://a.blogspot.com", position=1)
    r2 = create_result("https://b.blogspot.com", position=2)
    resp = process_search_results([r1, r2])
    assert resp.accepted_count == 2

def test_self_hosted_wordpress_behaves_normally():
    r1 = create_result("https://news.example.com", position=1)
    r2 = create_result("https://reviews.example.com", position=2)
    resp = process_search_results([r1, r2])
    assert resp.accepted_count == 1
    assert resp.accepted[0].registered_domain == "example.com"
