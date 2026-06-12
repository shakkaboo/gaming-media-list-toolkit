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
    max_response_bytes: Optional[int] = None,
    timeout_seconds: Optional[int] = None
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
        while True:
            try:
                norm_url, reg_domain = validate_url_safety(current_url)
            except UnsafeURLError as e:
                if redirect_count > 0:
                    raise RedirectError("Unsafe redirect URL", "unsafe_redirect")
                raise
                
            current_url = norm_url
            final_reg_domain = reg_domain
            
            if current_url in visited_urls:
                raise RedirectError("Redirect loop detected", "redirect_loop")
            visited_urls.add(current_url)
            
            parsed = urlparse(current_url)
            hostname = parsed.hostname
            
            # DNS resolution & safety check
            await dns_resolver.resolve_and_check(hostname)
            
            # NOTE: We pass the URL to HTTPX here. HTTPX will resolve the hostname again.
            # This creates a TOCTOU (Time-of-Check to Time-of-Use) gap regarding DNS rebinding.
            # Mitigating this perfectly requires a custom HTTP transport.
            
            req = client.build_request("GET", current_url)
            
            response = await client.send(req, stream=True)
            
            status_code = response.status_code
            
            if status_code in (301, 302, 303, 307, 308):
                await response.aclose()
                redirect_count += 1
                if redirect_count > settings.MAX_FETCH_REDIRECTS:
                    raise RedirectError("Too many redirects", "too_many_redirects")
                    
                location = response.headers.get("Location")
                if not location:
                    raise RedirectError("Redirect missing Location", "unsafe_redirect")
                    
                next_url = urljoin(current_url, location)
                
                if current_url.startswith("https://") and next_url.startswith("http://"):
                    raise RedirectError("HTTPS downgrade rejected", "https_downgrade")
                    
                redirect_chain.append(next_url)
                current_url = next_url
                continue
                
            break
            
        content_type_header = response.headers.get("Content-Type", "")
        content_length_header = response.headers.get("Content-Length")
        
        if content_length_header and content_length_header.isdigit():
            content_length = int(content_length_header)
            if content_length > settings.MAX_HTML_RESPONSE_BYTES:
                await response.aclose()
                raise ResponseTooLargeError("Declared Content-Length too large")
                
        if status_code == 204:
            await response.aclose()
            raise FetchError("No content", "no_content", is_retryable=False)
        elif status_code == 206:
            await response.aclose()
            raise FetchError("Unexpected partial content", "unexpected_partial_content", is_retryable=False)
        elif status_code == 429:
            await response.aclose()
            raise FetchError("Rate limited", "rate_limited", is_retryable=False)
        elif status_code in (400, 401, 403, 404, 410, 451):
            await response.aclose()
            raise FetchError(f"HTTP {status_code}", "http_client_error", is_retryable=False, status_code=status_code)
        elif status_code in (500, 502, 503, 504):
            await response.aclose()
            raise FetchError(f"HTTP {status_code}", "http_server_error", is_retryable=True, status_code=status_code)
        elif status_code >= 400:
            await response.aclose()
            raise FetchError(f"HTTP {status_code}", "unexpected_fetch_error", is_retryable=False, status_code=status_code)
            
        if not content_type_header:
            await response.aclose()
            raise UnsupportedContentTypeError("Missing Content-Type", "missing_content_type")
            
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
                if downloaded_bytes > settings.MAX_HTML_RESPONSE_BYTES:
                    raise ResponseTooLargeError("Streamed body too large")
                chunks.append(chunk)
        finally:
            await response.aclose()
            
        raw_body = b"".join(chunks)
        
        charset = response.charset_encoding or "utf-8"
        try:
            html = raw_body.decode(charset, errors="replace")
        except Exception:
            raise FetchError("Decoding error", "decoding_error", is_retryable=False)
            
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
            safe_error=None
        )
            
    except FetchError:
        raise
    except httpx.ConnectTimeout:
        raise FetchError("Connect timeout", "connection_timeout", is_retryable=True)
    except httpx.ReadTimeout:
        raise FetchError("Read timeout", "read_timeout", is_retryable=True)
    except httpx.ConnectError:
        raise FetchError("Connection error", "connection_error", is_retryable=True)
    except Exception as e:
        if "ssl" in str(e).lower() or "certificate" in str(e).lower() or "tls" in str(e).lower():
            raise FetchError("TLS error", "tls_error", is_retryable=False)
        raise FetchError(f"Unexpected error: {e}", "unexpected_fetch_error", is_retryable=False)

async def fetch_page_with_retries(
    url: str,
    client: httpx.AsyncClient,
    dns_resolver: DNSResolver,
    settings,
    allowed_content_types: Optional[Tuple[str, ...]] = None,
    max_response_bytes: Optional[int] = None,
    timeout_seconds: Optional[int] = None
) -> FetchedPage:
    
    start_time = time.monotonic()
    
    attempts = 0
    max_attempts = settings.FETCH_MAX_RETRIES + 1
    
    last_error_code = "unexpected_fetch_error"
    last_error_msg = "Unknown error"
    last_status_code = 0
    
    while attempts < max_attempts:
        attempts += 1
        try:
            return await _fetch_attempt(url, client, dns_resolver, settings, allowed_content_types, max_response_bytes, timeout_seconds)
        except FetchError as e:
            last_error_code = e.error_code
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
        error_code=last_error_code,
        safe_error=last_error_msg
    )
