import pytest
import socket
from unittest.mock import patch
from app.fetching.dns_resolver import DNSResolver
from app.fetching.exceptions import DNSError, UnsafeIPError

@pytest.fixture
def mock_getaddrinfo():
    with patch("socket.getaddrinfo") as mock:
        yield mock

@pytest.mark.asyncio
async def test_resolver_safe(mock_getaddrinfo):
    mock_getaddrinfo.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 80))
    ]
    resolver = DNSResolver()
    ips = await resolver.resolve_and_check("example.com")
    assert ips == ["8.8.8.8"]

@pytest.mark.asyncio
async def test_resolver_unsafe(mock_getaddrinfo):
    mock_getaddrinfo.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))
    ]
    resolver = DNSResolver()
    with pytest.raises(UnsafeIPError):
        await resolver.resolve_and_check("localhost")

@pytest.mark.asyncio
async def test_resolver_mixed_unsafe(mock_getaddrinfo):
    mock_getaddrinfo.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 80)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 80))
    ]
    resolver = DNSResolver()
    with pytest.raises(UnsafeIPError):
        await resolver.resolve_and_check("example.com")

@pytest.mark.asyncio
async def test_resolver_cache(mock_getaddrinfo):
    mock_getaddrinfo.return_value = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 80))
    ]
    resolver = DNSResolver()
    await resolver.resolve_and_check("example.com")
    await resolver.resolve_and_check("example.com")
    assert mock_getaddrinfo.call_count == 1

@pytest.mark.asyncio
async def test_resolver_failure(mock_getaddrinfo):
    mock_getaddrinfo.side_effect = socket.gaierror("Name or service not known")
    resolver = DNSResolver()
    with pytest.raises(DNSError):
        await resolver.resolve_and_check("example.com")
        
@pytest.mark.asyncio
async def test_resolver_failure_cache(mock_getaddrinfo):
    mock_getaddrinfo.side_effect = socket.gaierror("Name or service not known")
    resolver = DNSResolver()
    with pytest.raises(DNSError):
        await resolver.resolve_and_check("example.com")
    with pytest.raises(DNSError):
        await resolver.resolve_and_check("example.com")
    assert mock_getaddrinfo.call_count == 1
