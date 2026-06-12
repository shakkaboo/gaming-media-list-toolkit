import pytest
import respx
import httpx
from unittest.mock import MagicMock
from app.contacts.robots_policy import RobotsPolicyChecker
from app.services.fetch_service import FetchService

@pytest.fixture
def robots_checker():
    # FetchService uses real httpx internally, but we can mock it using respx
    service = FetchService()
    checker = RobotsPolicyChecker(service)
    return checker

@pytest.mark.asyncio
async def test_robots_allow():
    checker = RobotsPolicyChecker(FetchService())
    
    with respx.mock:
        respx.get("http://example.com/robots.txt").respond(
            200, 
            headers={"Content-Type": "text/plain; charset=utf-8"},
            text="User-agent: *\nAllow: /"
        )
        decision = await checker.is_allowed("http://example.com/contact")
        assert decision.allowed is True

@pytest.mark.asyncio
async def test_robots_disallow():
    checker = RobotsPolicyChecker(FetchService())
    
    with respx.mock:
        respx.get("http://example.com/robots.txt").respond(
            200, 
            headers={"Content-Type": "text/plain; charset=utf-8"},
            text="User-agent: *\nDisallow: /contact"
        )
        decision = await checker.is_allowed("http://example.com/contact")
        assert decision.allowed is False
        
        # Another path should be allowed
        decision2 = await checker.is_allowed("http://example.com/about")
        assert decision2.allowed is True

@pytest.mark.asyncio
async def test_robots_404():
    checker = RobotsPolicyChecker(FetchService())
    
    with respx.mock:
        respx.get("http://example.com/robots.txt").respond(404)
        decision = await checker.is_allowed("http://example.com/contact")
        assert decision.allowed is True # 404 means no restrictions

@pytest.mark.asyncio
async def test_robots_403():
    checker = RobotsPolicyChecker(FetchService())
    
    with respx.mock:
        respx.get("http://example.com/robots.txt").respond(403)
        decision = await checker.is_allowed("http://example.com/contact")
        assert decision.allowed is False # 403 means deny all

@pytest.mark.asyncio
async def test_robots_500():
    checker = RobotsPolicyChecker(FetchService())
    # By default ROBOTS_FAILURE_POLICY = deny
    checker.failure_policy = "deny"
    
    with respx.mock:
        respx.get("http://example.com/robots.txt").respond(500)
        decision = await checker.is_allowed("http://example.com/contact")
        assert decision.allowed is False 
        assert decision.status == "unavailable"
        
        allow_checker = RobotsPolicyChecker(FetchService())
        allow_checker.failure_policy = "allow"
        decision2 = await allow_checker.is_allowed("http://example.com/contact")
        assert decision2.allowed is True
