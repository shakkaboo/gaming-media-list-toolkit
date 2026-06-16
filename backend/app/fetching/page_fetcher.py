import asyncio
import httpx
import time
from urllib.parse import urljoin, urlparse
from typing import List, Optional, Set, Tuple
from datetime import datetime, timezone

from app.config import get_settings
from app.fetching.exceptions import (
    FetchError, UnsafeURLError, UnsafeIPError, DNSError, 
    ResponseTooLargeError, UnsupportedContentTypeError, RedirectError
)
from app.fetching.url_safety import validate_url_safety
from app.fetching.dns_resolver import DNSResolver
from app.fetching.title_parser import extract_title
from app.schemas.fetch import FetchedPage

async def _fetch_attempt(
    url: str,
    client: httpx.AsyncClient,
    dns_resolver: DNSResolver,
    settings,
    allowed_content_types: Optional[Tuple[str, ...]] = None,
    max_response_bytes: Optional[int] = None
) -> FetchedPage:
    """
    Executes a single fetch attempt (including redirect following).
    """
    start_time = time.monotonic()
    
    current_url = url
    redirect_chain = []
    visited_urls: Set[str] = set()
    redirect_count = 0
    final_reg_domain = ""
    
    if allowed_content_types is None:
        allowed_content_types = ("text/html", "application/xhtml+xml")

    try:
        # Initial validation to get the reg_domain
        try:
            norm_url, reg_domain = validate_url_safety(current_url)
            current_url = norm_url
            final_reg_domain = reg_domain
        except UnsafeURLError as e:
            raise FetchError(e.args[0], e.error_code, is_retryable=False)

        while True:
            if current_url in visited_urls:
                raise RedirectError("Redirect loop detected", "redirect_failure")
            visited_urls.add(current_url)
            
            parsed = urlparse(current_url)
            hostname = parsed.hostname
            
            if not hostname:
                raise RedirectError("Invalid redirect URL", "redirect_failure")
                
            # DNS resolution & safety check for every step of the redirect
            await dns_resolver.resolve_and_check(hostname)
            
            req = client.build_request("GET", current_url)
            
            response = await client.send(req, stream=True)
            
            status_code = response.status_code
            
            if status_code in (301, 302, 303, 307, 308):
                await response.aclose()
                redirect_count += 1
                if redirect_count > settings.MAX_FETCH_REDIRECTS:
                    raise RedirectError("Too many redirects", "redirect_failure")
                    
                location = response.headers.get("Location")
                if not location:
                    raise RedirectError("Redirect missing Location", "redirect_failure")
                    
                next_url = urljoin(current_url, location)
                
                if current_url.startswith("https://") and next_url.startswith("http://"):
                    raise RedirectError("HTTPS downgrade rejected", "redirect_failure")
                    
                redirect_chain.append(next_url)
                current_url = next_url
                continue
                
            break
            
        content_type_header = response.headers.get("Content-Type", "")
        content_length_header = response.headers.get("Content-Length")
        
        limit_bytes = max_response_bytes or settings.MAX_HTML_RESPONSE_BYTES
        
        if content_length_header and content_length_header.isdigit():
            content_length = int(content_length_header)
            if content_length > limit_bytes:
                await response.aclose()
                raise ResponseTooLargeError("Declared Content-Length too large")
                
        if status_code == 204:
            await response.aclose()
            raise FetchError("No content", "empty_html", is_retryable=False)
        elif status_code == 206:
            await response.aclose()
            raise FetchError("Unexpected partial content", "unknown", is_retryable=False)
        elif status_code == 401:
            await response.aclose()
            raise FetchError("Unauthorized", "http_401", is_retryable=False, status_code=status_code)
        elif status_code == 403:
            await response.aclose()
            raise FetchError("Forbidden", "http_403", is_retryable=False, status_code=status_code)
        elif status_code == 404:
            await response.aclose()
            raise FetchError("Not Found", "http_404", is_retryable=False, status_code=status_code)
        elif status_code == 429:
            await response.aclose()
            raise FetchError("Rate limited", "http_429", is_retryable=False, status_code=status_code)
        elif status_code in (400, 410, 451):
            await response.aclose()
            raise FetchError(f"HTTP {status_code}", "unknown", is_retryable=False, status_code=status_code)
        elif status_code in (500, 502, 503, 504):
            await response.aclose()
            raise FetchError(f"HTTP {status_code}", "http_5xx", is_retryable=True, status_code=status_code)
        elif status_code >= 400:
            await response.aclose()
            raise FetchError(f"HTTP {status_code}", "unknown", is_retryable=False, status_code=status_code)
            
        if not content_type_header:
            await response.aclose()
            raise UnsupportedContentTypeError("Missing Content-Type", "unsupported_content_type")
            
        media_type = content_type_header.split(";")[0].strip().lower()
        if allowed_content_types and media_type not in allowed_content_types:
            await response.aclose()
            raise UnsupportedContentTypeError(f"Unsupported content type: {media_type}")
            
        content_type = content_type_header
        
        chunks = []
        downloaded_bytes = 0
        try:
            async for chunk in response.aiter_bytes():
                downloaded_bytes += len(chunk)
                if downloaded_bytes > limit_bytes:
                    raise ResponseTooLargeError("Streamed body too large")
                chunks.append(chunk)
        finally:
            await response.aclose()
            
        raw_body = b"".join(chunks)
        
        charset = response.charset_encoding or "utf-8"
        try:
            html = raw_body.decode(charset, errors="replace")
        except Exception:
            raise FetchError("Decoding error", "unknown", is_retryable=False)
            
        # Challenge detection
        html_lower = html.lower()
        challenge_detected = False
        js_shell_detected = False
        
        if status_code == 200:
            if "cloudflare" in html_lower and ("challenge" in html_lower or "attention required" in html_lower):
                challenge_detected = True
            elif "distil_ident_block" in html_lower or "incapsula" in html_lower:
                challenge_detected = True
            elif len(html_lower) < 2000 and "<script" in html_lower and "document.cookie" in html_lower:
                challenge_detected = True
            elif len(html_lower) < 2000 and "enable javascript" in html_lower:
                js_shell_detected = True
                
        if challenge_detected:
            raise FetchError("Challenge page detected", "challenge_page", is_retryable=False, status_code=status_code)
            
        title = extract_title(html)
        
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        
        return FetchedPage(
            requested_url=url,
            final_url=current_url,
            registered_domain=final_reg_domain,
            status_code=status_code,
            content_type=content_type,
            content_length=downloaded_bytes,
            html=html,
            title=title,
            fetched_at=datetime.now(timezone.utc),
            redirect_chain=redirect_chain,
            redirect_count=redirect_count,
            elapsed_ms=elapsed_ms,
            success=True,
            error_code=None,
            safe_error=None,
            failure_category=None,
            failure_reason=None,
            challenge_detected=challenge_detected,
            javascript_shell_detected=js_shell_detected,
            robots_disallowed=False,
            attempt_count=1
        )
            
    except FetchError:
        raise
    except httpx.ConnectTimeout:
        raise FetchError("Connect timeout", "timeout", is_retryable=True)
    except httpx.ReadTimeout:
        raise FetchError("Read timeout", "timeout", is_retryable=True)
    except httpx.ConnectError:
        raise FetchError("Connection error", "connection_error", is_retryable=True)
    except DNSError:
        raise FetchError("DNS error", "dns_error", is_retryable=True)
    except Exception as e:
        if "ssl" in str(e).lower() or "certificate" in str(e).lower() or "tls" in str(e).lower():
            raise FetchError("TLS error", "ssl_error", is_retryable=False)
        raise FetchError(f"Unexpected error: {e}", "unknown", is_retryable=False)

async def fetch_page_with_retries(
    url: str,
    client: httpx.AsyncClient,
    dns_resolver: DNSResolver,
    settings,
    allowed_content_types: Optional[Tuple[str, ...]] = None,
    max_response_bytes: Optional[int] = None
) -> FetchedPage:
    
    start_time = time.monotonic()
    
    attempts = 0
    max_attempts = settings.FETCH_MAX_RETRIES + 1
    
    last_failure_category = "unknown"
    last_error_msg = "Unknown error"
    last_status_code = 0
    
    while attempts < max_attempts:
        attempts += 1
        try:
            page = await _fetch_attempt(url, client, dns_resolver, settings, allowed_content_types, max_response_bytes)
            page.attempt_count = attempts
            return page
        except FetchError as e:
            last_failure_category = e.error_code
            last_error_msg = str(e)
            last_status_code = e.status_code or 0
            
            if not e.is_retryable:
                break
                
            if attempts < max_attempts:
                delay = settings.FETCH_RETRY_BASE_DELAY_SECONDS * (2 ** (attempts - 1))
                delay = min(delay, settings.FETCH_MAX_RETRY_DELAY_SECONDS)
                await asyncio.sleep(delay)
                
    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    
    try:
        norm_url, reg_domain = validate_url_safety(url)
    except Exception:
        norm_url = url
        reg_domain = ""
    
    return FetchedPage(
        requested_url=url,
        final_url=norm_url,
        registered_domain=reg_domain,
        status_code=last_status_code,
        content_type=None,
        content_length=None,
        html=None,
        title=None,
        fetched_at=datetime.now(timezone.utc),
        redirect_chain=[],
        redirect_count=0,
        elapsed_ms=elapsed_ms,
        success=False,
        error_code=last_failure_category,
        safe_error=last_error_msg,
        failure_category=last_failure_category,
        failure_reason=last_error_msg,
        challenge_detected=(last_failure_category == "challenge_page"),
        javascript_shell_detected=False,
        robots_disallowed=False,
        attempt_count=attempts
    )
