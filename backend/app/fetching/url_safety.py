import ipaddress
from urllib.parse import urlparse
from app.discovery.url_normalizer import validate_and_normalize_url, NormalizationError
from app.fetching.exceptions import UnsafeURLError, UnsafeIPError

from typing import Tuple

METADATA_HOSTNAMES = {
    "metadata.google.internal",
    "instance-data",
    "instance-data.ec2.internal",
    "169.254.169.254",
    "100.100.100.200"
}

def validate_url_safety(url: str) -> Tuple[str, str]:
    """
    Validates the URL using Phase 3B normalizer and checks for metadata hostnames.
    Returns (normalized_url, registered_domain) or raises UnsafeURLError.
    """
    try:
        norm_url, _, reg_domain, _ = validate_and_normalize_url(url)
    except NormalizationError as e:
        raise UnsafeURLError(e.safe_reason, e.reason_code)
        
    parsed = urlparse(norm_url)
    hostname = parsed.hostname
    
    if not hostname:
        raise UnsafeURLError("Missing hostname", "missing_host")
        
    if hostname.lower() in METADATA_HOSTNAMES:
        raise UnsafeURLError("Metadata hostname blocked", "unsafe_resolved_ip")
        
    return norm_url, reg_domain

def check_ip_safety(ip_str: str) -> None:
    """
    Checks if an IP address is safe to connect to.
    Raises UnsafeIPError if it's private, loopback, link-local, multicast, etc.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return 
        
    if ip.is_loopback:
        raise UnsafeIPError("Loopback IP blocked")
    if ip.is_private:
        raise UnsafeIPError("Private IP blocked")
    if ip.is_link_local:
        raise UnsafeIPError("Link-local IP blocked")
    if ip.is_multicast:
        raise UnsafeIPError("Multicast IP blocked")
    if ip.is_reserved:
        raise UnsafeIPError("Reserved IP blocked")
    if ip.is_unspecified:
        raise UnsafeIPError("Unspecified IP blocked")
        
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped:
            mapped_ip = ip.ipv4_mapped
            if mapped_ip.is_private or mapped_ip.is_loopback or mapped_ip.is_link_local:
                raise UnsafeIPError("IPv4-mapped private IP blocked")
                
    if ip_str in METADATA_HOSTNAMES:
        raise UnsafeIPError("Cloud metadata IP blocked")
