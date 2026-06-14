from app.schemas.search import GeneratedSearchQuery
from typing import Optional, List

CATEGORY_JA_TERMS = {
    "gaming news": "ゲームニュース",
    "video game media": "ゲームメディア",
    "game reviews": "ゲームレビュー",
    "esports": "eスポーツ",
    "indie games": "インディーゲーム",
    "pc gaming": "PCゲーム",
    "console gaming": "コンソールゲーム",
    "mobile gaming": "モバイルゲーム",
}

NON_JP_TEMPLATES = [
    "independent {category} publication {market}",
    "regional {category} news website {market}",
    "{category} editorial media {market}",
    "{category} review publication {market}",
    "{category} magazine {market}",
    "emerging {category} media outlet {market}",
    "local {category} news site {market}",
]

JP_EN_TEMPLATES = [
    "Japanese {category} news websites",
    "Japanese {category} media",
    "Japanese {category} review publications",
    "Japan {category} news websites",
    "Japan independent {category} media",
]

JP_JA_TEMPLATES = [
    "日本の{category_ja}サイト",
    "日本の{category_ja}メディア",
    "日本の{category_ja}レビューサイト",
    "日本の{category_ja}ニュース",
    "日本のインディー{category_ja}メディア",
    "{category_ja}業界ニュース 日本",
    "{category_ja}雑誌 オンライン",
]

def generate_search_queries(
    market: str,
    language: str,
    categories: List[str],
    keywords: Optional[List[str]],
    maximum_queries: Optional[int],
) -> List[GeneratedSearchQuery]:
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

    is_jp = (market.strip().upper() == "JP" or language.strip().lower() == "ja")

    for category in categories:
        cat_lower = category.strip().lower()
        if is_jp:
            cat_ja = CATEGORY_JA_TERMS.get(cat_lower, "ゲームメディア")
            
            for idx, template in enumerate(JP_EN_TEMPLATES):
                text = template.format(category=category, market=market, language=language)
                add_base_query(text, category, f"jp_en_template_{idx}")
                
            for idx, template in enumerate(JP_JA_TEMPLATES):
                text = template.format(category_ja=cat_ja, market=market, language=language)
                add_base_query(text, category, f"jp_ja_template_{idx}")
        else:
            for idx, template in enumerate(NON_JP_TEMPLATES):
                text = template.format(category=category, market=market, language=language)
                add_base_query(text, category, f"non_jp_template_{idx}")

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
