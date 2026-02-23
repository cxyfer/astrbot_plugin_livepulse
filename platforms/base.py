from __future__ import annotations

from abc import ABC, abstractmethod

from aiohttp import ClientSession

from core.models import StatusSnapshot, ChannelInfo


DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


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
