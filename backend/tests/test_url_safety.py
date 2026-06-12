import pytest
from app.fetching.url_safety import validate_url_safety, check_ip_safety
from app.fetching.exceptions import UnsafeURLError, UnsafeIPError

def test_validate_url_safety_valid():
    norm, reg = validate_url_safety("http://example.com")
    assert norm == "http://example.com/"
    assert reg == "example.com"

def test_validate_url_safety_metadata():
    with pytest.raises(UnsafeURLError) as exc:
        validate_url_safety("http://metadata.google.internal")
    assert exc.value.error_code in ("unsafe_resolved_ip", "invalid_registered_domain")

def test_validate_url_safety_invalid_scheme():
    with pytest.raises(UnsafeURLError):
        validate_url_safety("ftp://example.com")
        
def test_validate_url_safety_credentials():
    with pytest.raises(UnsafeURLError):
        validate_url_safety("http://user:pass@example.com")

def test_validate_url_safety_raw_ip():
    with pytest.raises(UnsafeURLError):
        validate_url_safety("http://8.8.8.8")

def test_check_ip_safety_valid():
    check_ip_safety("8.8.8.8")
    check_ip_safety("2001:4860:4860::8888")

def test_check_ip_safety_unsafe():
    with pytest.raises(UnsafeIPError, match="Loopback"):
        check_ip_safety("127.0.0.1")
    with pytest.raises(UnsafeIPError, match="Private"):
        check_ip_safety("10.0.0.1")
    with pytest.raises(UnsafeIPError, match="Private"):
        check_ip_safety("192.168.1.1")
    with pytest.raises(UnsafeIPError, match="Private"):
        check_ip_safety("172.16.0.1")
    with pytest.raises(UnsafeIPError, match="Private|Link-local"):
        check_ip_safety("169.254.169.254")
    with pytest.raises(UnsafeIPError, match="Multicast"):
        check_ip_safety("224.0.0.1")
    with pytest.raises(UnsafeIPError, match="Loopback"):
        check_ip_safety("::1")
    with pytest.raises(UnsafeIPError, match="Private|IPv4-mapped"):
        check_ip_safety("::ffff:192.168.1.1")
    with pytest.raises(UnsafeIPError, match="Cloud metadata"):
        check_ip_safety("100.100.100.200")
