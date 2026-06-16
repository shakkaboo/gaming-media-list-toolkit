import re
import hashlib
import unicodedata
from typing import List, Dict, Set, Tuple, Optional
from app.schemas.verification import (
    ExtractedSiteSignals,
    NormalizedMultilingualEvidence,
    EvidenceItem
)
from app.schemas.acquisition import AcquisitionResult

VOCABULARY_VERSION = "v2.0"

class MultilingualVocab:
    def __init__(self):
        self.gaming_identity = {
            "en": ["game", "games", "gaming", "video game", "pc gaming", "console", "steam", "indie game", "esports"],
            "ja": ["ゲーム", "ビデオゲーム", "pcゲーム", "インディーゲーム", "eスポーツ", "新作ゲーム", "ゲームニュース", "ゲーム情報"],
            "fr": ["jeu vidéo", "jeux vidéo", "gaming", "esport", "actualité jeu vidéo"]
        }
        self.gaming_article = {
            "en": ["review", "walkthrough", "gameplay", "guide", "preview"],
            "ja": ["レビュー", "攻略", "実況", "発売", "アップデート"],
            "fr": ["test de jeu", "critique de jeu"]
        }
        self.editorial = {
            "en": ["news", "reviews", "features", "articles", "guides", "interviews", "editorial"],
            "ja": ["ニュース", "レビュー", "特集", "記事", "攻略", "インタビュー"],
            "fr": ["actualités", "tests", "critiques", "articles", "dossiers", "guides", "entrevues"]
        }
        self.author = {
            "en": ["author", "by", "published", "updated", "written by", "editorial staff", "journalism"],
            "ja": ["編集部", "ライター", "著者", "公開", "更新"],
            "fr": ["auteur", "publié", "mis à jour"]
        }
        
        self.store = ["product catalogue", "cart", "checkout", "prices", "purchase", "add to cart", "buy now", "merchandise"]
        self.developer = ["our games", "game portfolio", "investor relations", "careers in game development", "corporate company description", "support/download", "official product marketing"]
        self.hardware = ["manufacturer", "retail", "hardware store"]
        self.casino = ["casino", "betting", "gambling", "slots", "poker", "sportsbook", "online casino"]

    def _flat(self, d: Dict[str, List[str]]) -> List[str]:
        res = []
        for v in d.values():
            res.extend(v)
        return res

    def get_all_gaming_identity(self) -> List[str]: return self._flat(self.gaming_identity)
    def get_all_gaming_article(self) -> List[str]: return self._flat(self.gaming_article)
    def get_all_editorial(self) -> List[str]: return self._flat(self.editorial)
    def get_all_author(self) -> List[str]: return self._flat(self.author)

VOCAB = MultilingualVocab()

def get_vocabulary_hash() -> str:
    all_terms = sorted(VOCAB.get_all_gaming_identity() + VOCAB.get_all_gaming_article() + VOCAB.get_all_editorial() + VOCAB.get_all_author() + VOCAB.store + VOCAB.developer + VOCAB.hardware + VOCAB.casino)
    return hashlib.sha256(str(all_terms).encode('utf-8')).hexdigest()[:8]

def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = unicodedata.normalize('NFKC', text)
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def _extract_matches(texts: List[str], keywords: List[str], source: str, page_type: str) -> List[EvidenceItem]:
    items = []
    seen = set()
    norm_keywords = [_normalize_text(k) for k in keywords]
    for text in texts:
        norm_text = _normalize_text(text)
        if not norm_text:
            continue
        for idx, k in enumerate(norm_keywords):
            # Check if keyword is a whole word or significant part
            # For CJK we just check if it's in the text. For english we might want word boundaries, but simple 'in' is fine if normalized cleanly.
            # To avoid "game" matching "games" as separate? Actually 'in' is fine since we dedup by keyword.
            if k in norm_text:
                orig_k = keywords[idx]
                if orig_k not in seen:
                    seen.add(orig_k)
                    items.append(EvidenceItem(
                        source=source,
                        matched_term=orig_k,
                        page_type=page_type,
                        reason=f"Matched term '{orig_k}' in {source}"
                    ))
    return items

def normalize_evidence(signals_list: List[ExtractedSiteSignals], expected_language: Optional[str] = None, expected_market: Optional[str] = None) -> NormalizedMultilingualEvidence:
    evidence = NormalizedMultilingualEvidence()
    
    seen_identity = set()
    seen_nav = set()
    seen_article = set()
    seen_edit_nav = set()
    seen_author = set()
    seen_article_links = set()
    seen_categories = set()
    
    for signals in signals_list:
        ptype = signals.page_type
        src = signals.source_url
        
        # 1. Gaming identity in title/site name
        title_texts = [t for t in [signals.page_title, signals.og_site_name, signals.og_title, signals.meta_description, signals.og_description] if t]
        for item in _extract_matches(title_texts, VOCAB.get_all_gaming_identity(), "title/meta", ptype):
            if item.matched_term not in seen_identity:
                seen_identity.add(item.matched_term)
                evidence.gaming_identity_terms.append(item)
                
        # 2. Gaming navigation terms
        nav_texts = signals.headings + signals.navigation_labels
        for item in _extract_matches(nav_texts, VOCAB.get_all_gaming_identity() + VOCAB.get_all_gaming_article(), "navigation", ptype):
            if item.matched_term not in seen_nav:
                seen_nav.add(item.matched_term)
                evidence.gaming_navigation_terms.append(item)
                
        # 3. Gaming article titles
        for item in _extract_matches(signals.article_links, VOCAB.get_all_gaming_identity() + VOCAB.get_all_gaming_article(), "article_links", ptype):
            if item.matched_term not in seen_article:
                seen_article.add(item.matched_term)
                evidence.gaming_article_titles.append(item)
                
        # 4. Editorial navigation terms
        for item in _extract_matches(nav_texts, VOCAB.get_all_editorial(), "navigation", ptype):
            if item.matched_term not in seen_edit_nav:
                seen_edit_nav.add(item.matched_term)
                evidence.editorial_navigation_terms.append(item)
                
        # 5. Author/byline
        author_texts = signals.author_links + signals.footer_text + title_texts
        for item in _extract_matches(author_texts, VOCAB.get_all_author(), "author_meta", ptype):
            if item.matched_term not in seen_author:
                seen_author.add(item.matched_term)
                evidence.author_or_byline_evidence.append(item)
                
        # 5b. General article links
        for link in signals.article_links:
            if link not in seen_article_links:
                seen_article_links.add(link)
                evidence.article_like_links.append(EvidenceItem(
                    source="article_links", matched_term=link, page_type=ptype, reason="Found article link"
                ))
                
        # 5c. Categories
        for cat in signals.detected_categories:
            if cat not in seen_categories:
                seen_categories.add(cat)
                evidence.archive_or_category_evidence.append(EvidenceItem(
                    source="detected_categories", matched_term=cat, page_type=ptype, reason="Found category"
                ))
                
        # 6. Technical Evidence
        if signals.canonical_url or signals.page_title:
            evidence.technical_evidence.append(EvidenceItem(
                source="html", matched_term="parsed_html", page_type=ptype, reason=f"Extracted usable HTML for {src}"
            ))
        if signals.json_ld_types:
            evidence.technical_evidence.append(EvidenceItem(
                source="json-ld", matched_term="structured_data", page_type=ptype, reason=f"Found {len(signals.json_ld_types)} JSON-LD items"
            ))
            
        # 7. Dates and Activity
        for date_str in signals.detected_publication_dates:
            evidence.publication_dates.append(EvidenceItem(
                source="html_dates", matched_term=date_str, page_type=ptype, reason=f"Found date {date_str} in {src}"
            ))
            evidence.recent_content_dates.append(EvidenceItem(
                source="html_dates", matched_term=date_str, page_type=ptype, reason=f"Found date {date_str} in {src}"
            ))
            
        # 8. Deductions / Identity
        all_texts = title_texts + nav_texts + signals.footer_text
        for item in _extract_matches(all_texts, VOCAB.store, "store_signals", ptype):
            evidence.store_identity_signals.append(item)
        for item in _extract_matches(all_texts, VOCAB.developer, "developer_signals", ptype):
            evidence.developer_identity_signals.append(item)
        for item in _extract_matches(all_texts, VOCAB.hardware, "hardware_signals", ptype):
            evidence.hardware_identity_signals.append(item)
        for item in _extract_matches(all_texts, VOCAB.casino, "casino_signals", ptype):
            evidence.casino_identity_signals.append(item)
            
        # 9. Market
        if signals.html_language and expected_language and expected_language.lower() in signals.html_language.lower():
            evidence.market_language_evidence.append(EvidenceItem(
                source="html_lang", matched_term=signals.html_language, page_type=ptype, reason=f"Lang matches {expected_language}"
            ))
            
        if expected_market:
            expected_market_lower = expected_market.lower()
            for text in signals.footer_text:
                if expected_market_lower in text.lower():
                    evidence.market_location_evidence.append(EvidenceItem(
                        source="footer", matched_term=expected_market_lower, page_type=ptype, reason=f"Location {expected_market} in footer"
                    ))

    return evidence

def score_gaming_relevance(evidence: NormalizedMultilingualEvidence) -> int:
    score = 0
    score += min(15, len(evidence.gaming_identity_terms) * 5)
    score += min(10, len(evidence.gaming_navigation_terms) * 4)
    score += min(10, len(evidence.gaming_article_titles) * 4)
    
    has_secondary = any(item.page_type != "primary" for item in evidence.gaming_identity_terms + evidence.gaming_navigation_terms + evidence.gaming_article_titles)
    if has_secondary:
        score += 5
        
    score += min(5, len(evidence.archive_or_category_evidence) * 3)
    return min(30, max(0, score))

def score_media_evidence(evidence: NormalizedMultilingualEvidence) -> int:
    score = 0
    score += min(10, len(evidence.editorial_navigation_terms) * 3)
    score += min(8, len(evidence.article_like_links) * 2)
    
    unique_dates = len(set(item.matched_term for item in evidence.publication_dates))
    score += min(6, unique_dates * 2)
    
    score += min(6, len(evidence.author_or_byline_evidence) * 3)
    score += min(5, len(evidence.archive_or_category_evidence) * 3)
    
    metadata_count = sum(1 for item in evidence.technical_evidence if item.source == "json-ld" and ("Article" in item.matched_term or "NewsArticle" in item.matched_term))
    score += min(4, metadata_count * 2)
    
    score += min(5, len(evidence.publication_identity_evidence) * 3)
    
    return min(25, max(0, score))

from typing import Tuple

def score_market_relevance(evidence: NormalizedMultilingualEvidence, expected_market: Optional[str]) -> Tuple[int, str]:
    if not expected_market:
        return 0, "unconfirmed"
        
    score = 0
    status = "unconfirmed"
    
    expected_lower = expected_market.upper()
    if expected_lower == "GLOBAL":
        return 20, "confirmed"
        
    if evidence.market_language_evidence:
        score += 15
    if evidence.market_location_evidence:
        score += 10
        
    if score >= 15:
        status = "confirmed"
    elif score > 0:
        status = "probable"
        
    return min(20, max(0, score)), status

def score_activity(evidence: NormalizedMultilingualEvidence) -> int:
    score = 0
    if len(evidence.recent_content_dates) > 3:
        score += 11
    elif len(evidence.recent_content_dates) > 0:
        score += 7
    return min(15, max(0, score))

def score_technical(evidence: NormalizedMultilingualEvidence) -> int:
    score = 0
    if len(evidence.technical_evidence) > 0:
        score += 3
    has_secondary = any(item.page_type != "primary" for item in evidence.technical_evidence)
    if has_secondary:
        score += 2
    return min(10, max(0, score))

def compute_deductions_and_hard_rejections(evidence: NormalizedMultilingualEvidence) -> Tuple[int, Optional[str], List[str], str]:
    deductions = 0
    hr_rule = None
    hr_evidence = []
    
    unique_store = list(set(item.matched_term for item in evidence.store_identity_signals))
    store_deduction = 0
    has_product_schema = any(item.source == "json-ld" and "Product" in item.matched_term for item in evidence.technical_evidence)
    has_cart = "cart" in unique_store or "checkout" in unique_store
    has_purchase = "purchase" in unique_store or "buy now" in unique_store
    
    if (has_product_schema and has_cart) or (has_cart and has_purchase):
        hr_rule = "dominant_ecommerce_store"
        hr_evidence = unique_store
        store_deduction = 20
    elif len(unique_store) > 0:
        store_deduction = min(20, len(unique_store) * 10)
        
    unique_dev = list(set(item.matched_term for item in evidence.developer_identity_signals))
    dev_deduction = 0
    has_portfolio = "game portfolio" in unique_dev or "our games" in unique_dev
    has_corporate = "investor relations" in unique_dev or "corporate company description" in unique_dev
    if (has_portfolio and has_corporate) and not hr_rule:
        hr_rule = "game_developer_corporate_site"
        hr_evidence = unique_dev
        dev_deduction = 20
    elif len(unique_dev) > 0:
        dev_deduction = min(20, len(unique_dev) * 10)
        
    unique_casino = list(set(item.matched_term for item in evidence.casino_identity_signals))
    casino_deduction = 0
    has_casino = "casino" in unique_casino or "online casino" in unique_casino
    has_betting = "betting" in unique_casino or "sportsbook" in unique_casino or "gambling" in unique_casino
    if (has_casino and has_betting) and not hr_rule:
        hr_rule = "casino_or_betting_site"
        hr_evidence = unique_casino
        casino_deduction = 30
    elif len(unique_casino) > 0:
        casino_deduction = min(30, len(unique_casino) * 15)
        
    unique_hardware = list(set(item.matched_term for item in evidence.hardware_identity_signals))
    hardware_deduction = 0
    has_manufacturer = "manufacturer" in unique_hardware
    has_retail = "retail" in unique_hardware or "hardware store" in unique_hardware
    if (has_manufacturer and has_retail) and not hr_rule:
        hr_rule = "hardware_manufacturer"
        hr_evidence = unique_hardware
        hardware_deduction = 15
    elif len(unique_hardware) > 0:
        hardware_deduction = min(15, len(unique_hardware) * 5)
        
    deductions = store_deduction + dev_deduction + casino_deduction + hardware_deduction
    
    if not hr_rule:
        deductions = min(35, deductions)
    else:
        deductions = min(100, deductions)
        
    total_signals = len(unique_store) + len(unique_dev) + len(unique_casino) + len(unique_hardware)
    negative_confidence = "low"
    
    if hr_rule:
        negative_confidence = "high"
    elif has_product_schema or len(unique_store) >= 2 or len(unique_dev) >= 2 or len(unique_hardware) >= 2 or len(unique_casino) >= 2:
        negative_confidence = "high"
    elif total_signals > 0:
        negative_confidence = "medium"
        
    return deductions, hr_rule, hr_evidence, negative_confidence
