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
    TEMPLATES = [
        "independent {category} publication {market}",
        "regional {category} news website {market}",
        "{category} editorial media {market}",
        "{category} review publication {market}",
        "{category} magazine {market}",
        "emerging {category} media outlet {market}",
        "local {category} news site {market}",
    ]

    base_queries = []
    seen_texts = set()

    def add_base_query(text: str, category: str, template_name: str):
        clean_text = " ".join(text.split())
        clean_lower = clean_text.lower()
        if clean_lower not in seen_texts and len(clean_text) <= 500:
            seen_texts.add(clean_lower)
            base_queries.append({
                "text": clean_text,
                "category": category,
                "template": template_name
            })

    for category in categories:
        for idx, template in enumerate(TEMPLATES):
            text = template.format(category=category, market=market, language=language)
            add_base_query(text, category, f"template_{idx}")

    if keywords:
        for keyword in keywords:
            add_base_query(keyword, "custom", "keyword")

    queries = []
    seen_combinations = set()
    page = 1

    max_q = maximum_queries if maximum_queries is not None else len(base_queries)

    # Allocate page 1, then page 2, etc.
    while base_queries and len(queries) < max_q:
        added_in_round = False
        for bq in base_queries:
            if len(queries) >= max_q:
                break
            combo_key = (bq["text"].lower(), page)
            if combo_key not in seen_combinations:
                seen_combinations.add(combo_key)
                queries.append(GeneratedSearchQuery(
                    query_text=bq["text"],
                    category=bq["category"],
                    market=market,
                    language=language,
                    template_name=bq["template"],
                    page=page
                ))
                added_in_round = True

        if not added_in_round:
            break
        page += 1

    return queries
