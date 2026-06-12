import json
import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup

from app.config import get_settings
from app.schemas.verification import ExtractedSiteSignals

class HtmlAnalyzer:
    def __init__(self, html_content: str):
        self.settings = get_settings()
        if len(html_content) > self.settings.MAX_VERIFICATION_HTML_CHARS:
            html_content = html_content[:self.settings.MAX_VERIFICATION_HTML_CHARS]
        self.soup = BeautifulSoup(html_content, "html.parser")
        self.signals = ExtractedSiteSignals()

    def analyze(self) -> ExtractedSiteSignals:
        self._extract_metadata()
        self._extract_headings()
        self._extract_navigation_and_footer()
        self._extract_links()
        self._extract_time_elements()
        self._extract_json_ld()
        self._detect_challenges()
        return self.signals

    def _clean_text(self, text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        cleaned = " ".join(text.split())
        if len(cleaned) > self.settings.MAX_ELEMENT_TEXT_CHARS:
            cleaned = cleaned[:self.settings.MAX_ELEMENT_TEXT_CHARS]
        return cleaned if cleaned else None

    def _extract_metadata(self):
        title_tag = self.soup.find('title')
        if title_tag:
            self.signals.page_title = self._clean_text(title_tag.get_text())

        meta_desc = self.soup.find('meta', attrs={'name': lambda x: x and x.lower() == 'description'})
        if meta_desc and meta_desc.get('content'):
            self.signals.meta_description = self._clean_text(meta_desc['content'])

        og_title = self.soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            self.signals.og_title = self._clean_text(og_title['content'])

        og_desc = self.soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            self.signals.og_description = self._clean_text(og_desc['content'])

        og_site_name = self.soup.find('meta', property='og:site_name')
        if og_site_name and og_site_name.get('content'):
            self.signals.og_site_name = self._clean_text(og_site_name['content'])

        html_tag = self.soup.find('html')
        if html_tag and html_tag.get('lang'):
            self.signals.html_language = self._clean_text(html_tag['lang'])

        canonical = self.soup.find('link', rel='canonical')
        if canonical and canonical.get('href'):
            self.signals.canonical_url = self._clean_text(canonical['href'])

    def _extract_headings(self):
        headings = []
        for tag in self.soup.find_all(['h1', 'h2', 'h3'], limit=self.settings.MAX_ANALYZED_HEADINGS):
            text = self._clean_text(tag.get_text())
            if text and text not in headings:
                headings.append(text)
        self.signals.headings = headings

    def _extract_navigation_and_footer(self):
        nav_labels = []
        for nav in self.soup.find_all('nav'):
            for tag in nav.find_all(['a', 'button'], limit=self.settings.MAX_ANALYZED_NAV_ITEMS):
                text = self._clean_text(tag.get_text())
                if text and text not in nav_labels:
                    nav_labels.append(text)
            if len(nav_labels) >= self.settings.MAX_ANALYZED_NAV_ITEMS:
                break
        self.signals.navigation_labels = nav_labels[:self.settings.MAX_ANALYZED_NAV_ITEMS]

        footer_text = []
        for footer in self.soup.find_all('footer'):
            for tag in footer.find_all(['a', 'p', 'span'], limit=50):
                text = self._clean_text(tag.get_text())
                if text and text not in footer_text:
                    footer_text.append(text)
        self.signals.footer_text = footer_text[:50]

    def _extract_links(self):
        article_links = []
        author_links = []
        
        article_patterns = re.compile(r'/(news|reviews|guides|features|interviews|article|post)/', re.I)
        author_patterns = re.compile(r'/(author|writer|profile)/', re.I)
        
        links = self.soup.find_all('a', href=True, limit=self.settings.MAX_ANALYZED_ANCHORS)
        for a in links:
            href = a['href']
            if article_patterns.search(href):
                article_links.append(href)
            if author_patterns.search(href) or a.get('rel') == ['author']:
                author_links.append(href)
                
        self.signals.article_links = list(set(article_links))
        self.signals.author_links = list(set(author_links))

    def _extract_time_elements(self):
        dates = []
        times = self.soup.find_all('time', limit=self.settings.MAX_ANALYZED_TIME_ELEMENTS)
        for t in times:
            if t.get('datetime'):
                dates.append(t['datetime'])
            elif t.get_text():
                dates.append(self._clean_text(t.get_text()))
                
        for m in self.soup.find_all('meta', attrs={'property': ['article:published_time', 'article:modified_time']}):
            if m.get('content'):
                dates.append(m['content'])
                
        self.signals.detected_publication_dates = list(set(dates))

    def _extract_json_ld(self):
        scripts = self.soup.find_all('script', type='application/ld+json', limit=self.settings.MAX_ANALYZED_JSONLD_BLOCKS)
        types = []
        dates = []
        
        for script in scripts:
            content = script.string
            if not content:
                continue
            if len(content) > self.settings.MAX_JSONLD_BLOCK_CHARS:
                continue
            try:
                data = json.loads(content)
                self._traverse_json_ld(data, 0, types, dates)
            except json.JSONDecodeError:
                pass
                
        self.signals.json_ld_types = list(set(types))
        if dates:
            self.signals.detected_publication_dates.extend(list(set(dates)))
            self.signals.detected_publication_dates = list(set(self.signals.detected_publication_dates))

    def _traverse_json_ld(self, obj: Any, depth: int, types: List[str], dates: List[str]):
        if depth >= self.settings.MAX_JSONLD_DEPTH:
            return
            
        if isinstance(obj, dict):
            if '@type' in obj:
                t = obj['@type']
                if isinstance(t, str):
                    types.append(t)
                elif isinstance(t, list):
                    for t_item in t:
                        if isinstance(t_item, str):
                            types.append(t_item)
                    
            if 'datePublished' in obj and isinstance(obj['datePublished'], str):
                dates.append(obj['datePublished'])
            if 'dateModified' in obj and isinstance(obj['dateModified'], str):
                dates.append(obj['dateModified'])
                
            for v in obj.values():
                self._traverse_json_ld(v, depth + 1, types, dates)
                
        elif isinstance(obj, list):
            for item in obj:
                self._traverse_json_ld(item, depth + 1, types, dates)

    def _detect_challenges(self):
        title_lower = (self.signals.page_title or "").lower()
        if "just a moment" in title_lower or "attention required" in title_lower or "cloudflare" in title_lower:
            self.signals.challenge_indicators.append("cloudflare_challenge")
        if "access denied" in title_lower or "403 forbidden" in title_lower:
            self.signals.challenge_indicators.append("access_denied")
            
        if "domain for sale" in title_lower or "parked domain" in title_lower:
            self.signals.parking_indicators.append("domain_parked_or_for_sale")
