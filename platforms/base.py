from __future__ import annotations

from abc import ABC, abstractmethod

from aiohttp import ClientSession

from core.models import StatusSnapshot, ChannelInfo


class BasePlatformChecker(ABC):
    platform_name: str

    @abstractmethod
    async def check_status(self, channel_ids: list[str], session: ClientSession) -> dict[str, StatusSnapshot]:
        ...

    @abstractmethod
    async def validate_channel(self, channel_id: str, session: ClientSession) -> ChannelInfo | None:
        ...


class RateLimitError(Exception):
    def __init__(self, platform: str) -> None:
        self.platform = platform
        super().__init__(f"Rate limited by {platform}")
