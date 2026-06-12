from app.discovery.query_generator import generate_search_queries

def test_generate_search_queries_basic():
    queries = generate_search_queries(
        market="US",
        language="en",
        categories=["RPG"],
        keywords=["custom keyword"],
        maximum_queries=None
    )
    assert len(queries) > 0
    assert queries[0].market == "US"
    assert queries[0].language == "en"
    
    # Check that whitespace is normalized and deduplication works
    queries_ws = generate_search_queries(
        market=" US ",
        language=" en ",
        categories=["  RPG  "],
        keywords=["  custom   keyword  "],
        maximum_queries=None
    )
    
    # "custom keyword" is the normalized form of "  custom   keyword  "
    assert any(q.query_text == "custom keyword" for q in queries_ws)
    assert len(queries) == len(queries_ws)

def test_generate_search_queries_limit():
    queries = generate_search_queries(
        market="US",
        language="en",
        categories=["RPG", "FPS", "Action"],
        keywords=["a", "b", "c"],
        maximum_queries=3
    )
    assert len(queries) == 3

def test_generate_search_queries_dedup():
    queries = generate_search_queries(
        market="US",
        language="en",
        categories=["RPG"],
        keywords=["RPG websites in US"], # This will match the generated output for 'basic_website'
        maximum_queries=None
    )
    texts = [q.query_text for q in queries]
    assert len(texts) == len(set(texts))

def test_no_country_code_restriction():
    queries = generate_search_queries(
        market="India",
        language="English",
        categories=["RPG"],
        keywords=[],
        maximum_queries=None
    )
    for q in queries:
        assert "site:.in" not in q.query_text
