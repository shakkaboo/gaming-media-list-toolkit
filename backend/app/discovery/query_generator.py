from app.schemas.search import GeneratedSearchQuery
from app.discovery.templates import CATEGORY_TEMPLATES
from typing import Optional, List

def generate_search_queries(
    market: str,
    language: str,
    categories: List[str],
    keywords: Optional[List[str]],
    maximum_queries: Optional[int],
) -> List[GeneratedSearchQuery]:
    queries = []
    seen = set()

    def add_query(text: str, category: str, template_name: str):
        if maximum_queries and len(queries) >= maximum_queries:
            return
        clean_text = " ".join(text.split())
        clean_lower = clean_text.lower()
        if clean_lower not in seen and len(clean_text) <= 500:
            seen.add(clean_lower)
            queries.append(GeneratedSearchQuery(
                query_text=clean_text,
                category=category,
                market=market,
                language=language,
                template_name=template_name
            ))

    for category in categories:
        for template_name, template in CATEGORY_TEMPLATES.items():
            text = template.format(category=category, market=market, language=language)
            add_query(text, category, template_name)
            if maximum_queries and len(queries) >= maximum_queries:
                return queries

    if keywords:
        for keyword in keywords:
            add_query(keyword, "custom", "keyword")
            if maximum_queries and len(queries) >= maximum_queries:
                return queries

    return queries
