from html.parser import HTMLParser
from typing import Optional

class TitleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.title_text = ""
        self.done = False
        
    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        if tag.lower() == "title":
            self.in_title = True
            
    def handle_endtag(self, tag):
        if self.done:
            return
        if tag.lower() == "title":
            self.in_title = False
            if self.title_text.strip():
                self.done = True
                
    def handle_data(self, data):
        if self.in_title and not self.done:
            self.title_text += data

def extract_title(html: str) -> Optional[str]:
    if not html:
        return None
        
    parser = TitleParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass 
        
    cleaned = parser.title_text.strip()
    return cleaned if cleaned else None
