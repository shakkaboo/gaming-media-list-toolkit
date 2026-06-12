from typing import List, Optional
from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin, urlparse

from app.schemas.contact_discovery import ContactForm
from app.config import get_settings
from app.fetching.url_safety import validate_url_safety

class FormDetector:
    def __init__(self):
        self.settings = get_settings()

        self.contact_keywords = {'message', 'contact', 'email', 'inquiry', 'subject', 'body'}
        self.reject_keywords = {'login', 'password', 'sign up', 'register', 'search', 'comment', 'newsletter', 'checkout', 'subscribe'}

    def detect_forms(self, html: str, page_url: str, base_domain: str) -> List[ContactForm]:
        forms = []
        soup = BeautifulSoup(html, 'html.parser')
        
        for form in soup.find_all('form'):
            if len(forms) >= self.settings.MAX_CONTACT_FORMS_PER_PAGE:
                break
                
            action = form.get('action')
            method = form.get('method', 'get').lower()
            
            # Form fields
            inputs = form.find_all(['input', 'textarea', 'select'])
            field_names = []
            has_password = False
            has_search = False
            
            form_text = form.get_text(separator=' ', strip=True).lower()
            
            for inp in inputs:
                typ = inp.get('type', '').lower()
                name = inp.get('name', '').lower()
                
                if typ == 'hidden':
                    continue
                    
                if typ == 'password':
                    has_password = True
                if typ == 'search' or name == 'q' or name == 's':
                    has_search = True
                    
                if name:
                    field_names.append(name)
                    
            if has_password or has_search:
                continue
                
            # Check for reject keywords in form text and action
            reject_match = False
            for rk in self.reject_keywords:
                if rk in form_text or (action and rk in action.lower()):
                    reject_match = True
                    break
            if reject_match:
                continue
                
            # Check for contact evidence
            contact_match = False
            for ck in self.contact_keywords:
                if ck in form_text or any(ck in fn for fn in field_names) or (action and ck in action.lower()):
                    contact_match = True
                    break
                    
            if not contact_match:
                continue
                
            # Resolve action URL
            action_url = None
            is_external = False
            if action:
                try:
                    full_action = urljoin(page_url, action)
                    norm_url, reg_domain = validate_url_safety(full_action)
                    action_url = norm_url
                    if reg_domain != base_domain:
                        is_external = True
                except Exception:
                    action_url = action # fallback to raw
                    is_external = True
                    
            purpose = "contact"
            confidence = 0.8
            
            if action_url and "forms.gle" in action_url:
                is_external = True
                confidence = 0.9
                
            forms.append(ContactForm(
                page_url=page_url,
                action_url=action_url,
                is_external=is_external,
                method=method,
                purpose=purpose,
                confidence=confidence,
                field_names=field_names[:20] # bound field names
            ))
            
        return forms