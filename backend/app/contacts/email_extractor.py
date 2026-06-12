import re
import json
from typing import List, Dict, Optional, Tuple
from bs4 import BeautifulSoup, NavigableString, Tag
import encodings.idna

from app.schemas.contact_discovery import ExtractedContact, ContactEvidence
from app.config import get_settings

class EmailExtractor:
    def __init__(self):
        self.settings = get_settings()
        
        # Email validation regex (standard + strict local part)
        self.email_re = re.compile(r'^[a-zA-Z0-9._%+-]{1,64}@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        
        # Obfuscation matching
        self.obfuscation_re = re.compile(
            r'([a-zA-Z0-9._%+-]{1,64})\s*(?:\[at\]|\(at\)|\sAT\s|@)\s*([a-zA-Z0-9.-]+)\s*(?:\[dot\]|\(dot\)|\sDOT\s|\.)\s*([a-zA-Z]{2,})',
            re.IGNORECASE
        )

        self.hard_reject_re = re.compile(r'^(example|email|name|yourname)@(example|domain)\.(com|org|net)$', re.IGNORECASE)
        self.placeholder_re = re.compile(r'^(test|admin|user)@', re.IGNORECASE)

        self.role_re = re.compile(
            r'^(info|contact|hello|support|press|media|pr|ads?|advertising|sponsors?|partners?|partnerships?|'
            r'editor|editorial|news|tips?|submissions?|business|sales|inquiries|enquiries)$',
            re.IGNORECASE
        )

    def is_valid_email(self, email: str) -> bool:
        if len(email) > 254: return False
        if re.search(r'[\x00-\x1F\x7F]', email): return False # Control chars
        if not self.email_re.match(email): return False
        
        local, domain = email.rsplit('@', 1)
        if len(local) > 64: return False
        
        try:
            domain.encode('idna').decode('ascii')
        except Exception:
            return False
            
        return True

    def validate_and_normalize(self, raw_email: str) -> Optional[Tuple[str, str, bool, bool]]:
        """Returns (original_email, normalized_email, is_role_based, is_placeholder) or None if invalid."""
        email = raw_email.strip(' \t\n\r"\'.,:;')
        if not self.is_valid_email(email):
            return None
            
        local, domain = email.rsplit('@', 1)
        domain = domain.lower()
        normalized = f"{local}@{domain}"
        
        if self.hard_reject_re.match(normalized):
            return None
            
        is_placeholder = bool(self.placeholder_re.match(normalized))
        is_role = bool(self.role_re.match(local))
        
        return email, normalized, is_role, is_placeholder

    def _extract_from_text(self, text: str, method: str, source_url: str, source_page_type: str, discovery_order: int) -> List[ExtractedContact]:
        contacts = []
        words = text.split()
        for word in words:
            if '@' in word:
                valid = self.validate_and_normalize(word)
                if valid:
                    orig, norm, is_role, is_place = valid
                    evidence = ContactEvidence(
                        source_url=source_url,
                        extraction_method=method,
                        source_page_type=source_page_type,
                        nearby_text=text[:self.settings.MAX_CONTACT_EVIDENCE_CHARS],
                        reason_codes=["extracted_from_text"],
                        first_seen_order=discovery_order
                    )
                    
                    contacts.append(ExtractedContact(
                        email=orig,
                        normalized_email=norm,
                        primary_type="unknown",
                        secondary_types=[],
                        is_role_based=is_role,
                        is_named_contact=not is_role,
                        is_placeholder_suspected=is_place,
                        confidence=0.5,
                        rank_score=0,
                        evidence=[evidence]
                    ))
                    
        # Basic obfuscations
        for match in self.obfuscation_re.finditer(text):
            local, dom, tld = match.groups()
            reconstructed = f"{local}@{dom}.{tld}"
            valid = self.validate_and_normalize(reconstructed)
            if valid:
                orig, norm, is_role, is_place = valid
                evidence = ContactEvidence(
                    source_url=source_url,
                    extraction_method=method,
                    source_page_type=source_page_type,
                    nearby_text=text[:self.settings.MAX_CONTACT_EVIDENCE_CHARS],
                    reason_codes=["deobfuscated_text"],
                    first_seen_order=discovery_order
                )
                contacts.append(ExtractedContact(
                    email=orig,
                    normalized_email=norm,
                    primary_type="unknown",
                    secondary_types=[],
                    is_role_based=is_role,
                    is_named_contact=not is_role,
                    is_placeholder_suspected=is_place,
                    confidence=0.5,
                    rank_score=0,
                    evidence=[evidence]
                ))
                
        return contacts

    def extract_from_html(self, html: str, source_url: str, source_page_type: str, discovery_order: int) -> List[ExtractedContact]:
        contacts = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. Mailto links
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            if href.lower().startswith('mailto:'):
                raw_email = href[7:].split('?')[0]
                valid = self.validate_and_normalize(raw_email)
                if valid:
                    orig, norm, is_role, is_place = valid
                    text = a.get_text(separator=' ', strip=True)
                    evidence = ContactEvidence(
                        source_url=source_url,
                        extraction_method='mailto',
                        source_page_type=source_page_type,
                        nearby_text=text[:self.settings.MAX_CONTACT_EVIDENCE_CHARS],
                        reason_codes=["mailto_link"],
                        first_seen_order=discovery_order
                    )
                    contacts.append(ExtractedContact(
                        email=orig,
                        normalized_email=norm,
                        primary_type="unknown",
                        secondary_types=[],
                        is_role_based=is_role,
                        is_named_contact=not is_role,
                        is_placeholder_suspected=is_place,
                        confidence=0.8,
                        rank_score=0,
                        evidence=[evidence]
                    ))
                    
        # 2. Text blocks
        for element in soup.find_all(['p', 'div', 'span', 'li', 'td']):
            if element.name in ['script', 'style']:
                continue
            text = element.get_text(separator=' ', strip=True)
            if '@' in text or '[at]' in text.lower() or '(at)' in text.lower():
                contacts.extend(self._extract_from_text(text, 'visible_text', source_url, source_page_type, discovery_order))
                
        # 3. JSON-LD
        jsonld_blocks = soup.find_all('script', type='application/ld+json')
        blocks_processed = 0
        for block in jsonld_blocks:
            if blocks_processed >= self.settings.MAX_CONTACT_JSONLD_BLOCKS:
                break
            try:
                data = json.loads(block.string)
                blocks_processed += 1
                contacts.extend(self._parse_jsonld(data, 0, source_url, source_page_type, discovery_order))
            except Exception:
                pass
                
        return contacts

    def _parse_jsonld(self, data: any, depth: int, source_url: str, source_page_type: str, discovery_order: int) -> List[ExtractedContact]:
        if depth >= self.settings.MAX_CONTACT_JSONLD_DEPTH:
            return []
            
        contacts = []
        if isinstance(data, dict):
            typ = data.get('@type', '')
            if typ == 'ContactPoint' or typ == 'Organization':
                email = data.get('email')
                if email and isinstance(email, str):
                    valid = self.validate_and_normalize(email)
                    if valid:
                        orig, norm, is_role, is_place = valid
                        contact_type = str(data.get('contactType', ''))
                        evidence = ContactEvidence(
                            source_url=source_url,
                            extraction_method='json_ld',
                            source_page_type=source_page_type,
                            nearby_text=contact_type[:self.settings.MAX_CONTACT_EVIDENCE_CHARS],
                            reason_codes=["json_ld"],
                            first_seen_order=discovery_order
                        )
                        contacts.append(ExtractedContact(
                            email=orig,
                            normalized_email=norm,
                            primary_type="unknown",
                            secondary_types=[],
                            is_role_based=is_role,
                            is_named_contact=not is_role,
                            is_placeholder_suspected=is_place,
                            confidence=0.9,
                            rank_score=0,
                            evidence=[evidence]
                        ))
            for v in data.values():
                contacts.extend(self._parse_jsonld(v, depth + 1, source_url, source_page_type, discovery_order))
        elif isinstance(data, list):
            for item in data:
                contacts.extend(self._parse_jsonld(item, depth + 1, source_url, source_page_type, discovery_order))
                
        return contacts
