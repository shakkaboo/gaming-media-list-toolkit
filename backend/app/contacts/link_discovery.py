import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from typing import List, Dict, Set, Optional

from app.schemas.search import NormalizedCandidate
from app.schemas.contact_discovery import ContactPageCandidate
from app.config import get_settings
from app.fetching.url_safety import validate_url_safety

class LinkDiscoverer:
    def __init__(self):
        self.settings = get_settings()

        # Compile regexes for signals
        # Strong
        self.strong_re = re.compile(
            r'\b(?:contact(?: us)?|advertise|advertising|partnerships?|partner with us|'
            r'press|media kit|editorial|editors?|masthead|write for us|submissions?|'
            r'news tips?|tip us|sponsors?|sponsorship|business)\b|'
            r'お問い合わせ|広告|編集部|情報提供',
            re.IGNORECASE
        )
        # Medium
        self.medium_re = re.compile(
            r'\b(?:about(?: us)?|team|staff|contributors?|company|corporate)\b|'
            r'会社概要|運営会社|採用情報',
            re.IGNORECASE
        )
        # Reject
        self.reject_re = re.compile(
            r'\b(?:login|signup|account|shop|store|comments?|forum|tags?|categories|'
            r'articles?|authors?|privacy|terms|careers?|newsletter|'
            r'faq)\b',
            re.IGNORECASE
        )
        
        self.support_re = re.compile(r'\b(?:support|help)\b', re.IGNORECASE)

    def _determine_page_type(self, text: str, path: str) -> Optional[str]:
        combined = f"{text} {path}".lower()
        if self.reject_re.search(combined):
            return None
            
        if self.support_re.search(combined):
            return 'support'
            
        # check specific strong categories to classify
        if re.search(r'\b(?:advertise|advertising|partnerships?|partner with us|sponsors?|sponsorship)\b|広告', combined):
            return 'advertising'
        if re.search(r'\b(?:editorial|editors?|masthead|write for us|submissions?|news tips?|tip us)\b|編集部|情報提供', combined):
            return 'editorial'
        if re.search(r'\b(?:contact(?: us)?|business)\b|お問い合わせ', combined):
            return 'contact'
            
        if self.strong_re.search(combined):
            return 'contact' # fallback strong
            
        if self.medium_re.search(combined):
            return 'about'
            
        return None

    def discover_links(self, html: str, base_url: str, candidate: NormalizedCandidate) -> List[ContactPageCandidate]:
        if not html:
            return []
            
        soup = BeautifulSoup(html, 'html.parser')
        anchors = soup.find_all('a', href=True)[:self.settings.MAX_CONTACT_LINKS_ANALYZED]
        
        candidates_by_url: Dict[str, ContactPageCandidate] = {}
        
        for idx, a in enumerate(anchors):
            href = a['href'].strip()
            text = a.get_text(separator=' ', strip=True)
            
            # handle mailto right away? No, we discover contact pages to fetch.
            # Mailto on homepage will be handled differently or we can just let email_extractor do it.
            # But the prompt says "discovery contact-page fetching".
            if href.lower().startswith('mailto:'):
                continue
                
            try:
                full_url = urljoin(base_url, href)
                norm_url, reg_domain = validate_url_safety(full_url)
            except Exception:
                continue
                
            # Same publisher restriction
            parsed = urlparse(norm_url)
            base_parsed = urlparse(base_url)
            
            if candidate.subdomain:
                if parsed.hostname != base_parsed.hostname:
                    continue
            else:
                if reg_domain != candidate.registered_domain:
                    continue
                    
            page_type = self._determine_page_type(text, parsed.path)
            if not page_type:
                continue
                
            score = 0
            reason_codes = []
            
            if page_type == 'contact':
                score = 100
                reason_codes.append('strong_contact_match')
            elif page_type == 'advertising':
                score = 90
                reason_codes.append('strong_advertising_match')
            elif page_type == 'editorial':
                score = 90
                reason_codes.append('strong_editorial_match')
            elif page_type == 'about':
                score = 70
                reason_codes.append('medium_about_match')
            elif page_type == 'support':
                score = 30
                reason_codes.append('weak_support_match')
                
            # Prefer shorter, root-like paths over deep nested paths
            if len(parsed.path.strip('/')) > 0:
                segments = len(parsed.path.strip('/').split('/'))
                score -= (segments - 1) * 5
                
            # Dedup
            if norm_url in candidates_by_url:
                existing = candidates_by_url[norm_url]
                if score > existing.score:
                    existing.score = score
                    existing.page_type = page_type
                    existing.reason_codes = reason_codes
                    if text and not existing.anchor_text:
                        existing.anchor_text = text
            else:
                candidates_by_url[norm_url] = ContactPageCandidate(
                    url=norm_url,
                    page_type=page_type,
                    score=score,
                    reason_codes=reason_codes,
                    anchor_text=text or None,
                    discovery_order=idx
                )
                
        # Diversity selection
        # up to 2 contact/business pages
        # up to 1 advertising/partnership page
        # up to 1 editorial/team/masthead page
        # up to 1 about/company page
        
        all_candidates = list(candidates_by_url.values())
        # Sort by score descending, then discovery order
        all_candidates.sort(key=lambda x: (-x.score, x.discovery_order))
        
        selected: List[ContactPageCandidate] = []
        counts = {
            'contact': 0,
            'advertising': 0,
            'editorial': 0,
            'about': 0,
            'support': 0
        }
        
        limits = {
            'contact': 2,
            'advertising': 1,
            'editorial': 1,
            'about': 1,
            'support': 1 # will only select if budget remains
        }
        
        for c in all_candidates:
            if len(selected) >= self.settings.MAX_CONTACT_PAGES_PER_SITE:
                break
                
            ptype = c.page_type
            if counts.get(ptype, 0) < limits.get(ptype, 0):
                selected.append(c)
                counts[ptype] = counts.get(ptype, 0) + 1
                
        # Fill remaining budget if possible
        for c in all_candidates:
            if len(selected) >= self.settings.MAX_CONTACT_PAGES_PER_SITE:
                break
            if c not in selected:
                selected.append(c)
                
        return selected
