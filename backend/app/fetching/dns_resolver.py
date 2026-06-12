import socket
import asyncio
from typing import List, Dict, Tuple, Optional
from app.config import get_settings
from app.fetching.exceptions import DNSError, UnsafeIPError
from app.fetching.url_safety import check_ip_safety

class DNSResolver:
    """
    Request-scoped DNS resolver. Caches results safely within one batch.
    """
    def __init__(self):
        self._cache: Dict[str, Tuple[List[str], Optional[Exception]]] = {}
        
    async def resolve_and_check(self, hostname: str) -> List[str]:
        """
        Resolves a hostname and verifies every returned IP for SSRF safety.
        Raises DNSError or UnsafeIPError if unsafe or failed.
        """
        if hostname in self._cache:
            ips, err = self._cache[hostname]
            if err:
                raise err
            return ips
            
        settings = get_settings()
        
        try:
            res = await asyncio.wait_for(
                asyncio.to_thread(socket.getaddrinfo, hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM),
                timeout=settings.FETCH_DNS_TIMEOUT_SECONDS
            )
            
            ips = []
            for item in res:
                ip_str = item[4][0]
                if ip_str not in ips:
                    ips.append(ip_str)
                    
            if not ips:
                raise DNSError(f"No addresses found for {hostname}")
                
            for ip_str in ips:
                check_ip_safety(ip_str)
                
            self._cache[hostname] = (ips, None)
            return ips
            
        except asyncio.TimeoutError:
            err = DNSError("DNS resolution timed out", error_code="dns_timeout", is_retryable=True)
            self._cache[hostname] = ([], err)
            raise err
        except socket.gaierror as e:
            # Check for EAI_AGAIN which is temporary
            is_temp = getattr(e, "errno", None) == socket.EAI_AGAIN
            err = DNSError(f"DNS resolution failed: {e}", error_code="dns_failed", is_retryable=is_temp)
            self._cache[hostname] = ([], err)
            raise err
        except UnsafeIPError as e:
            self._cache[hostname] = ([], e)
            raise e
        except Exception as e:
            err = DNSError(f"Unexpected DNS error: {e}", error_code="dns_failed", is_retryable=False)
            self._cache[hostname] = ([], err)
            raise err
