import pytest
from app.discovery.domain_filter import get_block_reason

def test_exact_blocked_domain():
    assert get_block_reason("reddit.com") == "blocked_forum"

def test_blocked_subdomain():
    assert get_block_reason("www.reddit.com") == "blocked_forum"
    assert get_block_reason("old.reddit.com") == "blocked_forum"

def test_no_substring_false_positive():
    assert get_block_reason("redditgames.example.com") is None
    assert get_block_reason("notreddit.com") is None

def test_exact_host_block_behavior():
    assert get_block_reason("store.steampowered.com") == "blocked_marketplace"
    assert get_block_reason("steampowered.com") is None

def test_custom_user_block():
    assert get_block_reason("example.com", {"example.com"}) == "blocked_domain"
    assert get_block_reason("sub.example.com", {"example.com"}) == "blocked_domain"

def test_mandatory_security_restrictions_cannot_be_disabled():
    assert get_block_reason("youtube.com", set()) == "blocked_video"

def test_medium_blocked_by_default():
    assert get_block_reason("medium.com") == "blocked_domain"
    assert get_block_reason("gaming.medium.com") == "blocked_domain"

def test_normal_gaming_publication_accepted():
    assert get_block_reason("ign.com") is None
    assert get_block_reason("kotaku.com") is None
