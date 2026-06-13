from abc import ABC, abstractmethod
from typing import Optional
from app.schemas.traffic_estimate import TrafficEstimate
from app.config import Settings

class TrafficProvider(ABC):
    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    async def get_traffic(self, domain: str, market: Optional[str] = None) -> TrafficEstimate:
        pass
