import pytest
import respx
import httpx
import socket
from unittest.mock import patch

from app.config import get_settings
from app.fetching.page_fetcher import fetch_page_with_retries
from app.fetching.dns_resolver import DNSResolver

@pytest.fixture
def mock_dns():
    with patch("socket.getaddrinfo") as mock:
        mock.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 80))]
        yield mock
        
@pytest.fixture
def settings():
    return get_settings()

@pytest.mark.asyncio
async def test_fetch_success(mock_dns, settings):
    resolver = DNSResolver()
    async with httpx.AsyncClient() as client:
        with respx.mock:
            respx.get("http://example.com/").mock(return_value=httpx.Response(200, text="<html><title>Test</title></html>", headers={"Content-Type": "text/html"}))
            page = await fetch_page_with_retries("http://example.com", client, resolver, settings)
            assert page.success
            assert page.status_code == 200
            assert page.title == "Test"
            assert page.html == "<html><title>Test</title></html>"
            
@pytest.mark.asyncio
async def test_fetch_redirect(mock_dns, settings):
    resolver = DNSResolver()
    async with httpx.AsyncClient() as client:
        with respx.mock:
            respx.get("http://example.com/").mock(return_value=httpx.Response(301, headers={"Location": "https://example.com/"}))
            respx.get("https://example.com/").mock(return_value=httpx.Response(200, text="<html><title>Secure</title></html>", headers={"Content-Type": "text/html"}))
            page = await fetch_page_with_retries("http://example.com", client, resolver, settings)
            assert page.success
            assert page.redirect_count == 1
            assert page.final_url == "https://example.com/"
            
@pytest.mark.asyncio
async def test_fetch_https_downgrade(mock_dns, settings):
    resolver = DNSResolver()
    async with httpx.AsyncClient() as client:
        with respx.mock:
            respx.get("https://example.com/").mock(return_value=httpx.Response(301, headers={"Location": "http://example.com/"}))
            page = await fetch_page_with_retries("https://example.com", client, resolver, settings)
            assert not page.success
            assert page.error_code == "https_downgrade"

@pytest.mark.asyncio
async def test_fetch_unsafe_redirect(mock_dns, settings):
    resolver = DNSResolver()
    async with httpx.AsyncClient() as client:
        with respx.mock:
            respx.get("http://example.com/").mock(return_value=httpx.Response(301, headers={"Location": "http://127.0.0.1/"}))
            page = await fetch_page_with_retries("http://example.com", client, resolver, settings)
            assert not page.success
            assert page.error_code == "unsafe_redirect"

@pytest.mark.asyncio
async def test_fetch_oversized_content_length(mock_dns, settings):
    resolver = DNSResolver()
    async with httpx.AsyncClient() as client:
        with respx.mock:
            respx.get("http://example.com/").mock(return_value=httpx.Response(200, headers={"Content-Length": str(settings.MAX_HTML_RESPONSE_BYTES + 10)}))
            page = await fetch_page_with_retries("http://example.com", client, resolver, settings)
            assert not page.success
            assert page.error_code == "response_too_large"

@pytest.mark.asyncio
async def test_fetch_unsupported_content_type(mock_dns, settings):
    resolver = DNSResolver()
    async with httpx.AsyncClient() as client:
        with respx.mock:
            respx.get("http://example.com/").mock(return_value=httpx.Response(200, headers={"Content-Type": "application/pdf"}))
            page = await fetch_page_with_retries("http://example.com", client, resolver, settings)
            assert not page.success
            assert page.error_code == "unsupported_content_type"

@pytest.mark.asyncio
async def test_fetch_404_no_retry(mock_dns, settings):
    resolver = DNSResolver()
    async with httpx.AsyncClient() as client:
        with respx.mock:
            respx.get("http://example.com/").mock(return_value=httpx.Response(404))
            with patch("asyncio.sleep") as mock_sleep:
                page = await fetch_page_with_retries("http://example.com", client, resolver, settings)
                assert mock_sleep.call_count == 0
                assert not page.success
                assert page.error_code == "http_client_error"

@pytest.mark.asyncio
async def test_fetch_500_retry(mock_dns, settings):
    resolver = DNSResolver()
    async with httpx.AsyncClient() as client:
        with respx.mock:
            route = respx.get("http://example.com/")
            route.side_effect = [
                httpx.Response(500),
                httpx.Response(200, text="<html></html>", headers={"Content-Type": "text/html"})
            ]
            with patch("asyncio.sleep") as mock_sleep:
                page = await fetch_page_with_retries("http://example.com", client, resolver, settings)
                assert page.success
                assert mock_sleep.call_count == 1
