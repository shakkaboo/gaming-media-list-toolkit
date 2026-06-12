import pytest
from app.discovery.url_normalizer import validate_and_normalize_url, NormalizationError

def test_valid_http_url():
    norm, home, reg, sub = validate_and_normalize_url("http://example.com/path")
    assert norm == "http://example.com/path"
    assert home == "http://example.com/"
    assert reg == "example.com"
    assert sub is None

def test_missing_scheme_repaired():
    norm, home, reg, sub = validate_and_normalize_url("example.com/path")
    assert norm == "https://example.com/path"

def test_ambiguous_schemeless_input_rejected():
    with pytest.raises(NormalizationError) as exc:
        validate_and_normalize_url("invalid_input_string")
    assert exc.value.reason_code == "invalid_url"

def test_protocol_relative_rejected():
    with pytest.raises(NormalizationError) as exc:
        validate_and_normalize_url("//example.com/path")
    assert exc.value.reason_code == "invalid_url"

def test_credentials_rejected():
    with pytest.raises(NormalizationError) as exc:
        validate_and_normalize_url("https://user:pass@example.com")
    assert exc.value.reason_code == "embedded_credentials"

def test_uppercase_host_normalized():
    norm, home, reg, sub = validate_and_normalize_url("HTTPS://WWW.Example.COM")
    assert norm == "https://example.com/"
    assert reg == "example.com"
    assert sub is None

def test_www_removed():
    norm, home, reg, sub = validate_and_normalize_url("https://www.news.example.com")
    assert sub == "news"

def test_fragment_removed():
    norm, _, _, _ = validate_and_normalize_url("https://example.com/page#top")
    assert norm == "https://example.com/page"

def test_tracking_params_removed():
    norm, _, _, _ = validate_and_normalize_url("https://example.com/?utm_source=twitter&id=123")
    assert norm == "https://example.com/?id=123"

def test_ref_and_source_preserved():
    norm, _, _, _ = validate_and_normalize_url("https://example.com/?ref=abc&source=xyz")
    assert "ref=abc" in norm
    assert "source=xyz" in norm

def test_meaningful_query_params_preserved():
    norm, _, _, _ = validate_and_normalize_url("https://example.com/?page=2&article=test")
    assert "page=2" in norm
    assert "article=test" in norm

def test_default_ports_removed():
    norm, _, _, _ = validate_and_normalize_url("https://example.com:443/path")
    assert norm == "https://example.com/path"

def test_non_standard_ports_rejected():
    with pytest.raises(NormalizationError) as exc:
        validate_and_normalize_url("https://example.com:8443/path")
    assert exc.value.reason_code == "unsupported_port"
    
def test_malformed_ports_rejected():
    with pytest.raises(NormalizationError) as exc:
        validate_and_normalize_url("https://example.com:abc/path")
    assert exc.value.reason_code in {"invalid_url", "missing_host"}

def test_unicode_domain_converted():
    norm, _, reg, _ = validate_and_normalize_url("https://münchen.de")
    assert reg == "xn--mnchen-3ya.de"

def test_punycode_accepted():
    norm, _, reg, _ = validate_and_normalize_url("https://xn--mnchen-3ya.de")
    assert reg == "xn--mnchen-3ya.de"

def test_complex_tld_extraction():
    norm, _, reg, sub = validate_and_normalize_url("https://news.example.co.uk")
    assert reg == "example.co.uk"
    assert sub == "news"

def test_localhost_rejected():
    with pytest.raises(NormalizationError) as exc:
        validate_and_normalize_url("http://localhost:8080")
    assert exc.value.reason_code == "localhost"

def test_raw_ip_rejected():
    with pytest.raises(NormalizationError) as exc:
        validate_and_normalize_url("http://192.168.1.1")
    assert exc.value.reason_code == "raw_ip_not_allowed"

def test_ipv6_rejected():
    with pytest.raises(NormalizationError) as exc:
        validate_and_normalize_url("http://[2001:db8::1]")
    assert exc.value.reason_code == "raw_ip_not_allowed"

def test_null_characters_rejected():
    with pytest.raises(NormalizationError) as exc:
        validate_and_normalize_url("https://example.com/path\x00")
    assert exc.value.reason_code == "invalid_url"

def test_trailing_dot_normalized():
    norm, home, reg, sub = validate_and_normalize_url("https://example.com.")
    assert reg == "example.com"
    assert norm == "https://example.com/"

def test_url_too_long_rejected():
    long_path = "a" * 2000
    with pytest.raises(NormalizationError) as exc:
        validate_and_normalize_url(f"https://example.com/{long_path}")
    assert exc.value.reason_code == "url_too_long"
    
def test_host_too_long_rejected():
    long_host = "a" * 254
    with pytest.raises(NormalizationError) as exc:
        validate_and_normalize_url(f"https://{long_host}.com")
    assert exc.value.reason_code == "host_too_long"
