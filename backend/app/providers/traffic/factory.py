from app.providers.traffic.base import TrafficProvider
from app.providers.traffic.manual import ManualTrafficProvider
from app.config import Settings

def get_traffic_provider(provider_name: str, settings: Settings) -> TrafficProvider:
    if provider_name == "manual" or provider_name == "mock":
        return ManualTrafficProvider(settings)
    raise ValueError(f"Unknown traffic provider: {provider_name}")
