from typing import List, Dict

from app.schemas.contact_discovery import ExtractedContact, ContactForm
from app.config import get_settings

class Deduplicator:
    def __init__(self):
        self.settings = get_settings()
        self.free_email_domains = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com', 'mail.com'}

    def deduplicate_and_rank_contacts(self, contacts: List[ExtractedContact], publisher_domain: str, homepage_url: str) -> List[ExtractedContact]:
        merged: Dict[str, ExtractedContact] = {}
        
        for contact in contacts:
            key = contact.normalized_email
            if key not in merged:
                merged[key] = contact
            else:
                existing = merged[key]
                # Merge evidence
                # Avoid exact duplicate evidence
                existing_ev_keys = {(e.source_url, e.extraction_method, e.nearby_text) for e in existing.evidence}
                for ev in contact.evidence:
                    ekey = (ev.source_url, ev.extraction_method, ev.nearby_text)
                    if ekey not in existing_ev_keys:
                        existing.evidence.append(ev)
                        existing_ev_keys.add(ekey)
                        
        results = list(merged.values())
        for contact in results:
            self._rank_contact(contact, publisher_domain, homepage_url)
            
        # Sort descending by score, tie break alphabetically
        results.sort(key=lambda x: (-x.rank_score, x.normalized_email))
        return results

    def _rank_contact(self, contact: ExtractedContact, publisher_domain: str, homepage_url: str):
        score = 0
        
        is_dedicated_page = False
        is_homepage_only = True
        has_mailto = False
        has_json_ld = False
        
        for ev in contact.evidence:
            if ev.source_url.rstrip('/') != homepage_url.rstrip('/'):
                is_homepage_only = False
                if ev.source_page_type in ['contact', 'advertising', 'editorial', 'about']:
                    is_dedicated_page = True
            
            if ev.extraction_method == 'mailto':
                has_mailto = True
            elif ev.extraction_method == 'json_ld':
                has_json_ld = True
                
        # Positive factors
        if is_dedicated_page:
            score += 40
        if has_mailto:
            score += 30
            
        email_domain = contact.normalized_email.split('@')[1]
        if email_domain == publisher_domain or email_domain.endswith('.' + publisher_domain):
            score += 20
        elif email_domain in self.free_email_domains:
            score -= 20 # Mild penalty for free webmail
        else:
            score -= 10 # External domain penalty
            
        if contact.is_role_based:
            score += 10
            
        if contact.primary_type not in ['unknown', 'general']:
            score += 10
            
        if has_json_ld:
            score += 10
            
        # Repeated evidence bonus
        if len(contact.evidence) > 1:
            score += min(30, (len(contact.evidence) - 1) * 10)
            
        # Negative factors
        if is_homepage_only:
            # Check if extracted via footer visible text, etc.
            # If it's a mailto on homepage, it's slightly better, but still homepage-only.
            score -= 50
            
        if contact.is_placeholder_suspected:
            score -= 80
            
        # Clamp 0-100
        contact.rank_score = max(0, min(100, score))
        
        # Limit evidence count
        if len(contact.evidence) > self.settings.MAX_CONTACT_REASONS:
            contact.evidence = contact.evidence[:self.settings.MAX_CONTACT_REASONS]

    def deduplicate_forms(self, forms: List[ContactForm]) -> List[ContactForm]:
        merged: Dict[str, ContactForm] = {}
        
        for form in forms:
            # Identify form by action and fields
            key = f"{form.action_url}_{'-'.join(sorted(form.field_names))}"
            if key not in merged:
                merged[key] = form
            else:
                # keep highest confidence
                if form.confidence > merged[key].confidence:
                    merged[key] = form
                    
        # Sort descending by confidence
        results = list(merged.values())
        results.sort(key=lambda x: (-x.confidence, x.page_url))
        return results