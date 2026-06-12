import re
from datetime import datetime, timezone
from dateutil.parser import parse as parse_date
from typing import List, Tuple, Optional
from app.schemas.verification import ExtractedSiteSignals, VerificationReason

GAMING_WORDS_PATTERN = re.compile(r'\b(gaming|video games|videogames|gamer|gamers|gameplay|esports|mmo|rpg)\b', re.I)
PLATFORM_WORDS_PATTERN = re.compile(r'\b(pc|playstation|xbox|nintendo|switch|ps4|ps5|mobile gaming|ios|android)\b', re.I)
EDITORIAL_WORDS_PATTERN = re.compile(r'\b(news|reviews|guides|features|interviews|editorials|articles|walkthroughs)\b', re.I)

STORE_WORDS_PATTERN = re.compile(r'\b(shopping cart|add to cart|buy now|checkout|pricing)\b', re.I)
DEV_WORDS_PATTERN = re.compile(r'\b(developed by|our games|game developer|development studio|published by|game publisher)\b', re.I)
CASINO_WORDS_PATTERN = re.compile(r'\b(casino|betting|gambling|slots|poker|roulette|sportsbook|odds)\b', re.I)
HARDWARE_WORDS_PATTERN = re.compile(r'\b(graphics card|gpu|cpu|motherboard|gaming chair|gaming mouse)\b', re.I)

def _count_matches(pattern: re.Pattern, texts: List[str]) -> int:
    count = 0
    for t in texts:
        if t and pattern.search(t):
            count += 1
    return count

def evaluate_gaming_relevance(signals: ExtractedSiteSignals) -> Tuple[int, List[VerificationReason]]:
    score = 0
    reasons = []
    
    meta_texts = [signals.page_title, signals.meta_description, signals.og_title, signals.og_description, signals.og_site_name]
    nav_head_texts = signals.headings + signals.navigation_labels

    gaming_meta = _count_matches(GAMING_WORDS_PATTERN, meta_texts)
    if gaming_meta > 0:
        pts = min(15, gaming_meta * 5)
        score += pts
        reasons.append(VerificationReason(code="gaming_meta", message="Gaming terminology in metadata", weight=pts, evidence=["Metadata match"]))

    platform_nav = _count_matches(PLATFORM_WORDS_PATTERN, nav_head_texts)
    if platform_nav > 0:
        pts = min(15, platform_nav * 5)
        score += pts
        reasons.append(VerificationReason(code="platform_nav", message="Platform terminology in navigation or headings", weight=pts, evidence=["Platform match"]))

    if 'VideoGame' in signals.json_ld_types or 'esports' in str(meta_texts).lower():
        score += 5
        reasons.append(VerificationReason(code="gaming_structured_data", message="Gaming context or structured data", weight=5, evidence=["Context match"]))

    return min(35, score), reasons

def evaluate_editorial_structure(signals: ExtractedSiteSignals) -> Tuple[int, List[VerificationReason]]:
    score = 0
    reasons = []
    
    editorial_nav = _count_matches(EDITORIAL_WORDS_PATTERN, signals.navigation_labels)
    if editorial_nav > 0:
        pts = min(20, editorial_nav * 10)
        score += pts
        reasons.append(VerificationReason(code="editorial_nav", message="Editorial navigation labels", weight=pts, evidence=["Editorial nav"]))
        
    if len(signals.article_links) > 2:
        pts = min(10, len(signals.article_links) * 2)
        score += pts
        reasons.append(VerificationReason(code="article_links", message="Article-like links detected", weight=pts, evidence=["Article links"]))
        
    editorial_schemas = {'NewsArticle', 'Article', 'Review', 'BlogPosting', 'NewsMediaOrganization'}
    matched_schemas = editorial_schemas.intersection(set(signals.json_ld_types))
    if matched_schemas:
        score += 10
        reasons.append(VerificationReason(code="editorial_schema", message="Editorial JSON-LD schema", weight=10, evidence=list(matched_schemas)))

    return min(35, score), reasons

def evaluate_activity(signals: ExtractedSiteSignals, current_time: datetime) -> Tuple[int, str, Optional[str], List[VerificationReason]]:
    score = 0
    status = "unknown"
    newest_date: Optional[datetime] = None
    reasons = []

    for date_str in signals.detected_publication_dates:
        try:
            d = parse_date(date_str)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if newest_date is None or d > newest_date:
                # ignore future dates
                if (d - current_time).total_seconds() < 86400:
                    newest_date = d
        except Exception:
            continue

    newest_str = None
    if newest_date:
        newest_str = newest_date.isoformat()
        days_old = (current_time - newest_date).days
        if days_old <= 90:
            score += 15
            status = "active_recently"
            reasons.append(VerificationReason(code="active_recently", message="Publication within 90 days", weight=15, evidence=[newest_str]))
        elif days_old <= 365:
            score += 7
            status = "possibly_active"
            reasons.append(VerificationReason(code="possibly_active", message="Publication within 365 days", weight=7, evidence=[newest_str]))
        else:
            status = "stale"
            reasons.append(VerificationReason(code="stale", message="Publication older than 365 days", weight=0, evidence=[newest_str]))

    return min(15, score), status, newest_str, reasons

def evaluate_publication_identity(signals: ExtractedSiteSignals) -> Tuple[int, List[VerificationReason]]:
    score = 0
    reasons = []

    if signals.og_site_name:
        score += 2
        reasons.append(VerificationReason(code="og_site_name", message="Open Graph site name present", weight=2, evidence=[signals.og_site_name]))

    if len(signals.author_links) > 0:
        pts = min(4, len(signals.author_links) * 2)
        score += pts
        reasons.append(VerificationReason(code="author_links", message="Author/Byline links detected", weight=pts, evidence=["Authors"]))

    about_patterns = re.compile(r'\b(about us|team|contact us|editorial staff)\b', re.I)
    about_links = _count_matches(about_patterns, signals.navigation_labels + signals.footer_text)
    if about_links > 0:
        score += 3
        reasons.append(VerificationReason(code="about_links", message="Editorial footprint", weight=3, evidence=["About/Team"]))

    pub_patterns = re.compile(r'\b(publication|magazine|journalism|coverage|daily news)\b', re.I)
    pub_text = _count_matches(pub_patterns, [signals.meta_description, signals.page_title, signals.og_description])
    if pub_text > 0:
        score += 6
        reasons.append(VerificationReason(code="publication_text", message="Explicit publication wording", weight=6, evidence=["Publication text"]))

    return min(15, score), reasons

def evaluate_negative_penalties(signals: ExtractedSiteSignals) -> Tuple[int, List[VerificationReason]]:
    penalty = 0
    reasons = []

    all_texts = [signals.page_title, signals.meta_description, signals.og_description] + signals.headings + signals.navigation_labels + signals.footer_text

    store_hits = _count_matches(STORE_WORDS_PATTERN, all_texts)
    if store_hits > 0:
        pts = min(40, store_hits * 10)
        penalty += pts
        reasons.append(VerificationReason(code="store_signals", message="E-commerce or store signals detected", weight=-pts, evidence=["Store evidence"]))

    dev_hits = _count_matches(DEV_WORDS_PATTERN, all_texts)
    if dev_hits > 0:
        pts = min(40, dev_hits * 15)
        penalty += pts
        reasons.append(VerificationReason(code="developer_signals", message="Developer or publisher signals detected", weight=-pts, evidence=["Dev evidence"]))

    casino_hits = _count_matches(CASINO_WORDS_PATTERN, all_texts)
    if casino_hits > 0:
        pts = 80
        penalty += pts
        reasons.append(VerificationReason(code="casino_signals", message="Casino or betting signals detected", weight=-pts, evidence=["Casino evidence"]))

    hardware_hits = _count_matches(HARDWARE_WORDS_PATTERN, all_texts)
    if hardware_hits > 0:
        pts = min(30, hardware_hits * 10)
        penalty += pts
        reasons.append(VerificationReason(code="hardware_signals", message="Hardware retailer signals detected", weight=-pts, evidence=["Hardware evidence"]))

    return min(80, penalty), reasons

def detect_categories(signals: ExtractedSiteSignals) -> List[str]:
    categories = set()
    all_text = " ".join([t for t in [signals.page_title, signals.meta_description] + signals.navigation_labels + signals.headings if t]).lower()
    
    if "news" in all_text: categories.add("gaming_news")
    if "review" in all_text: categories.add("reviews")
    if "guide" in all_text or "walkthrough" in all_text: categories.add("guides")
    if "feature" in all_text: categories.add("features")
    if "interview" in all_text: categories.add("interviews")
    if "esport" in all_text or "tournament" in all_text: categories.add("esports")
    if "pc" in all_text or "steam" in all_text: categories.add("pc_gaming")
    if "playstation" in all_text or "ps4" in all_text or "ps5" in all_text: categories.add("playstation")
    if "xbox" in all_text: categories.add("xbox")
    if "nintendo" in all_text or "switch" in all_text: categories.add("nintendo")
    if "mobile" in all_text or "ios" in all_text or "android" in all_text: categories.add("mobile_gaming")
    if "indie" in all_text: categories.add("indie_games")
    if "hardware" in all_text or "gpu" in all_text: categories.add("hardware")
    
    return list(categories)
