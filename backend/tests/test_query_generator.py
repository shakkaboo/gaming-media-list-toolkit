from app.discovery.query_generator import generate_search_queries

def test_jp_jobs_contain_japanese_and_english_queries():
    queries = generate_search_queries(
        market="JP",
        language="ja",
        categories=["gaming news"],
        keywords=[],
        maximum_queries=None
    )
    texts = [q.query_text for q in queries]
    
    # Check JP_JA template (Japanese queries)
    assert any("日本のゲームニュースサイト" in text for text in texts)
    
    # Check JP_EN template (English queries)
    assert any("Japanese gaming news news websites" in text or "Japanese gaming news media" in text for text in texts)

def test_japanese_output_does_not_contain_malformed_strings():
    queries = generate_search_queries(
        market="JP",
        language="ja",
        categories=["gaming news"],
        keywords=[],
        maximum_queries=None
    )
    texts = [q.query_text for q in queries]
    
    for text in texts:
        assert "日本 gaming news ニュース" not in text

def test_recognized_categories_use_mapped_japanese_terms():
    queries = generate_search_queries(
        market="JP",
        language="ja",
        categories=["esports"],
        keywords=[],
        maximum_queries=None
    )
    texts = [q.query_text for q in queries]
    assert any("日本のeスポーツ" in text for text in texts)
    assert any("eスポーツ業界ニュース 日本" in text for text in texts)

def test_unknown_categories_fallback_safely():
    queries = generate_search_queries(
        market="JP",
        language="ja",
        categories=["weird_unknown_category"],
        keywords=[],
        maximum_queries=None
    )
    texts = [q.query_text for q in queries]
    # Fallback is "ゲームメディア"
    assert any("日本のゲームメディアサイト" in text or "日本のゲームメディアメディア" in text for text in texts)

def test_non_jp_jobs_do_not_receive_jp_templates():
    queries = generate_search_queries(
        market="US",
        language="en",
        categories=["gaming news"],
        keywords=[],
        maximum_queries=None
    )
    texts = [q.query_text for q in queries]
    
    for text in texts:
        assert "日本" not in text
        assert "Japanese" not in text
        assert "independent gaming news publication" in text or "regional gaming news news website" in text or "gaming news editorial media" in text or "gaming news review publication" in text or "gaming news magazine" in text or "emerging gaming news media outlet" in text or "local gaming news news site" in text

def test_generated_query_order_is_deterministic():
    queries1 = generate_search_queries(
        market="JP",
        language="ja",
        categories=["esports", "gaming news"],
        keywords=[],
        maximum_queries=10
    )
    queries2 = generate_search_queries(
        market="JP",
        language="ja",
        categories=["esports", "gaming news"],
        keywords=[],
        maximum_queries=10
    )
    assert [q.query_text for q in queries1] == [q.query_text for q in queries2]

def test_the_word_top_is_not_inserted():
    queries = generate_search_queries(
        market="US",
        language="en",
        categories=["gaming news"],
        keywords=[],
        maximum_queries=None
    )
    for q in queries:
        assert "top" not in q.query_text.lower()
        assert "best" not in q.query_text.lower()

def test_pagination_and_max_queries():
    queries = generate_search_queries(
        market="US",
        language="en",
        categories=["gaming news"],
        keywords=[],
        maximum_queries=10
    )
    assert len(queries) == 10
    pages = [q.page for q in queries]
    assert 1 in pages
    assert 2 in pages

    unique_combos = set((q.query_text, q.page) for q in queries)
    assert len(unique_combos) == len(queries)

    page1_count = sum(1 for q in queries if q.page == 1)
    assert page1_count == 7
    page2_count = sum(1 for q in queries if q.page == 2)
    assert page2_count == 3

def test_maximum_queries_none_terminates():
    queries = generate_search_queries(
        market="US",
        language="en",
        categories=["gaming news"],
        keywords=[],
        maximum_queries=None
    )
    assert len(queries) == 7
    for q in queries:
        assert q.page == 1
