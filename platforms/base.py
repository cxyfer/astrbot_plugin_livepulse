from __future__ import annotations

from abc import ABC, abstractmethod

from aiohttp import ClientSession

from core.models import ChannelInfo, StatusSnapshot


class BasePlatformChecker(ABC):
    platform_name: str

    @abstractmethod
    async def check_status(
        self, channel_ids: list[str], session: ClientSession
    ) -> dict[str, StatusSnapshot]: ...

    @abstractmethod
    async def validate_channel(
        self, channel_id: str, session: ClientSession
    ) -> ChannelInfo | None: ...

    def extract_id_from_url(self, raw: str) -> str:
        """Extract channel/user identifier from a URL without network calls. Returns empty string if not a URL."""
        return ""


class RateLimitError(Exception):
    def __init__(self, platform: str) -> None:
        self.platform = platform
        super().__init__(f"Rate limited by {platform}")
