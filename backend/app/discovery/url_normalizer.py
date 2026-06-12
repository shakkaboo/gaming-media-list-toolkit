import ipaddress
import urllib.parse
import tldextract
from typing import Tuple, Optional
from app.config import get_settings

extractor = tldextract.TLDExtract(suffix_list_urls=None)

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id",
    "gclid", "dclid", "fbclid", "msclkid", "mc_cid", "mc_eid"
}

class NormalizationError(Exception):
    def __init__(self, reason_code: str, safe_reason: str):
        self.reason_code = reason_code
        self.safe_reason = safe_reason
        super().__init__(safe_reason)

def validate_and_normalize_url(raw_url: str) -> Tuple[str, str, str, Optional[str]]:
    """
    Returns (normalized_url, homepage_url, registered_domain, subdomain)
    Raises NormalizationError if invalid or rejected.
    """
    settings = get_settings()

    if not raw_url:
        raise NormalizationError("invalid_url", "URL cannot be empty")
        
    if len(raw_url) > settings.MAX_URL_LENGTH:
        raise NormalizationError("url_too_long", f"URL exceeds {settings.MAX_URL_LENGTH} characters")
        
    if "\x00" in raw_url or any(ord(c) < 32 for c in raw_url):
        raise NormalizationError("invalid_url", "URL contains control characters or null bytes")
        
    url_to_parse = raw_url.strip()
    
    if not url_to_parse.startswith("http://") and not url_to_parse.startswith("https://"):
        if url_to_parse.startswith("//"):
            raise NormalizationError("invalid_url", "Protocol-relative URLs are not supported")
        if "://" in url_to_parse:
            raise NormalizationError("unsupported_scheme", "Scheme is not supported")
        if " " in url_to_parse or ("/" not in url_to_parse and "." not in url_to_parse):
            raise NormalizationError("invalid_url", "URL lacks valid scheme and host structure")
        url_to_parse = "https://" + url_to_parse

    try:
        parsed = urllib.parse.urlsplit(url_to_parse)
    except ValueError:
        raise NormalizationError("invalid_url", "Failed to parse URL")
        
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise NormalizationError("unsupported_scheme", "Only HTTP and HTTPS are allowed")
        
    if parsed.username or parsed.password:
        raise NormalizationError("embedded_credentials", "URLs with credentials are not allowed")
        
    hostname = parsed.hostname
    if not hostname:
        raise NormalizationError("missing_host", "URL is missing a hostname")
        
    hostname = hostname.lower()
    
    if hostname.endswith("."):
        hostname = hostname[:-1]
        
    if len(hostname) > settings.MAX_HOST_LENGTH:
        raise NormalizationError("host_too_long", f"Hostname exceeds {settings.MAX_HOST_LENGTH} characters")
        
    try:
        hostname = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        raise NormalizationError("invalid_hostname", "Invalid IDNA conversion")
        
    for label in hostname.split("."):
        if len(label) > 63:
            raise NormalizationError("invalid_hostname", "DNS label exceeds 63 characters")
            
    if hostname == "localhost":
        raise NormalizationError("localhost", "Localhost is not permitted")
        
    try:
        ip = ipaddress.ip_address(hostname)
        raise NormalizationError("raw_ip_not_allowed", "Raw IP addresses are not permitted")
    except ValueError:
        pass 
        
    port = parsed.port
    if port is not None:
        if not settings.ALLOW_NON_STANDARD_PORTS:
            if (scheme == "http" and port != 80) or (scheme == "https" and port != 443):
                raise NormalizationError("unsupported_port", "Non-standard ports are not allowed")
                
    ext = extractor(hostname)
    registered_domain = ext.registered_domain
    if not registered_domain:
        raise NormalizationError("invalid_registered_domain", "Could not extract registered domain")
        
    subdomain = ext.subdomain
    if subdomain == "www" or subdomain.startswith("www."):
        subdomain = subdomain[4:]
        
    if not subdomain:
        subdomain = None
        
    final_host = f"{subdomain}.{registered_domain}" if subdomain else registered_domain
    
    path = urllib.parse.quote(parsed.path, safe="/%")
    if not path:
        path = "/"
        
    query_parts = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered_queries = [(k, v) for k, v in query_parts if k.lower() not in TRACKING_PARAMS]
    
    query_str = urllib.parse.urlencode(filtered_queries)
    normalized_url = urllib.parse.urlunsplit((scheme, final_host, path, query_str, ""))
    
    homepage_url = f"{scheme}://{final_host}/"
    
    return normalized_url, homepage_url, registered_domain, subdomain
