import re
from typing import List, Set

from app.schemas.contact_discovery import ExtractedContact

class ContactClassifier:
    def __init__(self):
        self.categories = {
            'editorial': re.compile(r'\b(editor(?:ial|s)?|news|desk)\b', re.IGNORECASE),
            'advertising': re.compile(r'\b(ads?|advertising|sales|sponsor(?:ship|s)?)\b', re.IGNORECASE),
            'partnerships': re.compile(r'\b(partners?|partnerships?|collab(?:orations?)?)\b', re.IGNORECASE),
            'press': re.compile(r'\b(press|media|pr)\b', re.IGNORECASE),
            'tips': re.compile(r'\b(tips?|scoops?|leaks?)\b', re.IGNORECASE),
            'submissions': re.compile(r'\b(submissions?|pitches|pitch|contribute)\b', re.IGNORECASE),
            'business': re.compile(r'\b(biz|business|corporate)\b', re.IGNORECASE),
            'general': re.compile(r'\b(contact|info|hello|enquiries|inquiries|hi)\b', re.IGNORECASE),
            'support': re.compile(r'\b(support|help|service)\b', re.IGNORECASE)
        }
        
        self.priority = [
            'tips', 'submissions', 'advertising', 'partnerships', 
            'press', 'editorial', 'business', 'support', 'general', 'unknown'
        ]

    def classify(self, contact: ExtractedContact) -> ExtractedContact:
        matched_types: Set[str] = set()
        
        local_part = contact.normalized_email.split('@')[0]
        
        # Aggregate all text evidence
        text_evidence = []
        for ev in contact.evidence:
            if ev.source_page_type:
                text_evidence.append(ev.source_page_type)
            if ev.nearby_text:
                text_evidence.append(ev.nearby_text)
                
        combined_text = " ".join(text_evidence)
        
        # 1. Check local part
        local_matches = set()
        for cat, regex in self.categories.items():
            if regex.search(local_part):
                local_matches.add(cat)
                
        # 2. Check context text
        context_matches = set()
        for cat, regex in self.categories.items():
            if regex.search(combined_text):
                context_matches.add(cat)
                
        # Combine. If local part matches something, but context strongly contradicts it, 
        # we might favor context. For now, union them, but use context to promote priority.
        matched_types.update(local_matches)
        matched_types.update(context_matches)
        
        # 3. Deduce from source page type if no other strong signal
        if not matched_types:
            for ev in contact.evidence:
                if ev.source_page_type in self.categories:
                    matched_types.add(ev.source_page_type)
                    
        if not matched_types:
            matched_types.add('unknown')
            
        # Sort by priority
        sorted_types = sorted(list(matched_types), key=lambda x: self.priority.index(x) if x in self.priority else 999)
        
        # Override primary if local_part is very explicitly one thing, but context had another thing.
        # Generally, local part is strong evidence if it is a role address.
        if contact.is_role_based and local_matches:
            best_local = sorted(list(local_matches), key=lambda x: self.priority.index(x))[0]
            # Ensure the best local match is primary if it's high priority
            if best_local in sorted_types and best_local not in ('general', 'unknown'):
                sorted_types.remove(best_local)
                sorted_types.insert(0, best_local)
                
        contact.primary_type = sorted_types[0]
        contact.secondary_types = sorted_types[1:]
        
        return contact