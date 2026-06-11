import re
from bs4 import BeautifulSoup
from src.utils import make_absolute_url

class ContactExtractor:
    """Extracts contact info, social links, and relevant pages from HTML."""

    def __init__(self):
        # Email Regex
        self.email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')

    def extract(self, html, base_url):
        if not html:
            return {
                "Contact Email": "",
                "Advertising Email": "",
                "Editorial Contact Page": "",
                "Media Kit URL": "",
                "LinkedIn URL": "",
                "X/Twitter URL": "",
                "YouTube URL": ""
            }

        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. Extract Emails
        emails = set(re.findall(self.email_pattern, html))
        # Filter out common false positives (e.g., example@example.com, or image files ending in common extensions)
        valid_emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', 'sentry.io', 'example.com'))]
        
        contact_email = ""
        advertising_email = ""
        for e in valid_emails:
            e_lower = e.lower()
            if 'ad' in e_lower or 'sales' in e_lower or 'sponsor' in e_lower:
                advertising_email = e
            elif not contact_email:
                contact_email = e

        if not contact_email and valid_emails:
            contact_email = valid_emails[0]

        # 2. Extract Social Links & Relevant Pages
        social_links = {
            "LinkedIn URL": "",
            "X/Twitter URL": "",
            "YouTube URL": ""
        }
        pages = {
            "Editorial Contact Page": "",
            "Media Kit URL": ""
        }

        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            text = a_tag.get_text().lower()

            # Socials
            if 'linkedin.com/company/' in href or 'linkedin.com/in/' in href:
                social_links["LinkedIn URL"] = href
            elif 'twitter.com/' in href or 'x.com/' in href:
                if 'intent/tweet' not in href and 'share' not in href:
                    social_links["X/Twitter URL"] = href
            elif 'youtube.com/' in href:
                social_links["YouTube URL"] = href

            # Pages
            if ('contact' in href.lower() or 'contact' in text) and not pages["Editorial Contact Page"]:
                pages["Editorial Contact Page"] = make_absolute_url(base_url, href)
            
            if ('media-kit' in href.lower() or 'mediakit' in href.lower() or 'advertise' in href.lower() or 'sponsor' in href.lower() or 'media kit' in text) and not pages["Media Kit URL"]:
                pages["Media Kit URL"] = make_absolute_url(base_url, href)

        return {
            "Contact Email": contact_email,
            "Advertising Email": advertising_email,
            "Editorial Contact Page": pages["Editorial Contact Page"],
            "Media Kit URL": pages["Media Kit URL"],
            "LinkedIn URL": social_links["LinkedIn URL"],
            "X/Twitter URL": social_links["X/Twitter URL"],
            "YouTube URL": social_links["YouTube URL"]
        }
