from __future__ import annotations

import re

from aiohttp import ClientSession, ClientTimeout

from astrbot.api import logger

from core.models import StatusSnapshot, ChannelInfo
from platforms.base import BasePlatformChecker, RateLimitError

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
_LIVE_URL = "https://www.youtube.com/channel/{channel_id}/live"
_HANDLE_URL = "https://www.youtube.com/{handle}"
_CHANNEL_ID_RE = re.compile(r'"channelId"\s*:\s*"(UC[\w-]{22})"')
_TITLE_RE = re.compile(r'"title"\s*:\s*"([^"]+)"')
_THUMB_RE = re.compile(r'"thumbnail"\s*:\s*\{\s*"thumbnails"\s*:\s*\[\s*\{[^}]*"url"\s*:\s*"([^"]+)"')


class YouTubeChecker(BasePlatformChecker):
    platform_name = "youtube"

    def __init__(self, timeout: int = 20) -> None:
        self._timeout = ClientTimeout(total=timeout)

    async def check_status(self, channel_ids: list[str], session: ClientSession) -> dict[str, StatusSnapshot]:
        results: dict[str, StatusSnapshot] = {}
        for cid in channel_ids:
            try:
                results[cid] = await self._check_single(cid, session)
            except RateLimitError:
                raise
            except Exception as e:
                logger.warning(f"YouTube check failed for {cid}: {e}")
                results[cid] = StatusSnapshot(is_live=False, streamer_name=cid)
        return results

    async def _check_single(self, channel_id: str, session: ClientSession) -> StatusSnapshot:
        url = _LIVE_URL.format(channel_id=channel_id)
        headers = {"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
        async with session.get(url, headers=headers, timeout=self._timeout, allow_redirects=True) as resp:
            if resp.status == 429:
                raise RateLimitError("youtube")
            if resp.status != 200:
                return StatusSnapshot(is_live=False, streamer_name=channel_id)
            html = await resp.text()

        if _is_blocked(html):
            raise RateLimitError("youtube")

        is_live = '"isLive":true' in html or "hqdefault_live.jpg" in html

        name_match = re.search(r'"author"\s*:\s*"([^"]+)"', html)
        name = name_match.group(1) if name_match else channel_id

        title = ""
        title_match = _TITLE_RE.search(html)
        if title_match:
            title = title_match.group(1)

        thumb = ""
        thumb_match = _THUMB_RE.search(html)
        if thumb_match:
            thumb = thumb_match.group(1)

        return StatusSnapshot(
            is_live=is_live,
            stream_id=channel_id if is_live else "",
            title=title if is_live else "",
            thumbnail_url=thumb if is_live else "",
            streamer_name=name,
            stream_url=url if is_live else "",
        )

    async def validate_channel(self, channel_id: str, session: ClientSession) -> ChannelInfo | None:
        if channel_id.startswith("@"):
            resolved = await self._resolve_handle(channel_id, session)
            if resolved is None:
                return None
            channel_id, name = resolved
        else:
            name = await self._get_channel_name(channel_id, session)
            if name is None:
                return None
        return ChannelInfo(channel_id=channel_id, channel_name=name, platform="youtube")

    async def _resolve_handle(self, handle: str, session: ClientSession) -> tuple[str, str] | None:
        url = _HANDLE_URL.format(handle=handle)
        headers = {"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
        try:
            async with session.get(url, headers=headers, timeout=self._timeout, allow_redirects=True) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
        except Exception as e:
            logger.warning(f"YouTube handle resolution failed for {handle}: {e}")
            return None

        cid_match = _CHANNEL_ID_RE.search(html)
        if cid_match is None:
            return None
        channel_id = cid_match.group(1)

        name_match = re.search(r'"author"\s*:\s*"([^"]+)"', html)
        name = name_match.group(1) if name_match else handle
        return channel_id, name

    async def _get_channel_name(self, channel_id: str, session: ClientSession) -> str | None:
        url = _LIVE_URL.format(channel_id=channel_id)
        headers = {"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
        try:
            async with session.get(url, headers=headers, timeout=self._timeout, allow_redirects=True) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
        except Exception:
            return None
        name_match = re.search(r'"author"\s*:\s*"([^"]+)"', html)
        return name_match.group(1) if name_match else channel_id


def _is_blocked(html: str) -> bool:
    return "captcha" in html.lower() or "unusual traffic" in html.lower()
