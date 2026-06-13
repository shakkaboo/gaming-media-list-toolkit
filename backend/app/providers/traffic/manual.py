import asyncio
from typing import Optional
from decimal import Decimal
from app.providers.traffic.base import TrafficProvider
from app.schemas.traffic_estimate import TrafficEstimate

class ManualTrafficProvider(TrafficProvider):
    async def get_traffic(self, domain: str, market: Optional[str] = None) -> TrafficEstimate:
        await asyncio.sleep(0.01) # Simulate network call

        # Deterministic test fixtures per user request
        if domain == "kotaku.com":
            return TrafficEstimate(
                provider="manual",
                has_data=True,
                monthly_visits=Decimal("1250000"),
                pages_per_visit=Decimal("2.0"),
                confidence=Decimal("0.9")
            )
        elif domain == "example-small-site.com":
            return TrafficEstimate(
                provider="manual",
                has_data=True,
                monthly_visits=Decimal("125000"),
                pages_per_visit=Decimal("2.0"),
                confidence=Decimal("0.8")
            )
        elif domain == "example-no-data.com":
            return TrafficEstimate(
                provider="manual",
                has_data=False,
                notes="No data available"
            )
        elif domain == "error.com":
            return TrafficEstimate(
                provider="manual",
                has_data=False,
                error_code="rate_limit",
                safe_error="Provider rate limited"
            )
        elif domain == "crash.com":
            raise Exception("Unexpected provider crash")
        # Default mock for any other site, returns a passing value
        return TrafficEstimate(
            provider="manual",
            has_data=True,
            monthly_visits=Decimal("500000"),
            pages_per_visit=Decimal("2.5"),
            confidence=Decimal("0.7")
        )
