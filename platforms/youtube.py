from __future__ import annotations

import re

from aiohttp import ClientSession, ClientTimeout

from astrbot.api import logger

from core.models import StatusSnapshot, ChannelInfo
from platforms import DEFAULT_USER_AGENT
from platforms.base import BasePlatformChecker, RateLimitError

_STREAMS_URL = "https://www.youtube.com/channel/{channel_id}/streams"
_HANDLE_URL = "https://www.youtube.com/{handle}"
_EXTERNAL_ID_RE = re.compile(r'"externalId"\s*:\s*"(UC[\w-]{22})"')
_OG_URL_CID_RE = re.compile(
    r'<meta\s+property="og:url"\s+content="https://www\.youtube\.com/channel/(UC[\w-]{22})"',
    re.I,
)
_OG_TITLE_RE = re.compile(r'<meta\s+property="og:title"\s+content="([^"]+)"', re.I)


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
        url = _STREAMS_URL.format(channel_id=channel_id)
        headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
        async with session.get(url, headers=headers, timeout=self._timeout, allow_redirects=True) as resp:
            if resp.status == 429:
                raise RateLimitError("youtube")
            if resp.status != 200:
                return StatusSnapshot(is_live=False, streamer_name=channel_id)
            html = await resp.text()

        if _is_blocked(html):
            raise RateLimitError("youtube")

        name_match = _OG_TITLE_RE.search(html)
        name = name_match.group(1) if name_match else channel_id

        live_marker = '"style":"LIVE"'
        search_pos = 0
        video_id = ""
        title = ""
        thumb = ""

        while True:
            live_pos = html.find(live_marker, search_pos)
            if live_pos == -1:
                break

            renderer_start = html.rfind('"videoRenderer"', 0, live_pos)
            if renderer_start == -1:
                search_pos = live_pos + len(live_marker)
                continue

            renderer_end = html.find('"videoRenderer"', live_pos + len(live_marker))
            if renderer_end == -1:
                renderer_end = len(html)
            renderer = html[renderer_start:renderer_end]

            video_match = re.search(r'"videoId"\s*:\s*"([^"]+)"', renderer)
            if video_match is None:
                search_pos = live_pos + len(live_marker)
                continue

            video_id = video_match.group(1)
            title_match = re.search(
                r'"title"\s*:\s*\{\s*"runs"\s*:\s*\[\s*\{\s*"text"\s*:\s*"([^"]+)"',
                renderer,
            )
            if title_match:
                title = title_match.group(1)

            thumb_match = re.search(
                r'"thumbnail"\s*:\s*\{\s*"thumbnails"\s*:\s*\[\s*\{[^}]*"url"\s*:\s*"([^"]+)"',
                renderer,
            )
            if thumb_match:
                thumb = thumb_match.group(1)
            break

        if not video_id:
            return StatusSnapshot(is_live=False, streamer_name=name)

        stream_url = f"https://www.youtube.com/watch?v={video_id}"

        return StatusSnapshot(
            is_live=True,
            stream_id=video_id,
            title=title,
            thumbnail_url=thumb,
            streamer_name=name,
            stream_url=stream_url,
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
        headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
        try:
            async with session.get(url, headers=headers, timeout=self._timeout, allow_redirects=True) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
        except Exception as e:
            logger.warning(f"YouTube handle resolution failed for {handle}: {e}")
            return None

        if _is_blocked(html):
            raise RateLimitError("youtube")

        cid_match = _EXTERNAL_ID_RE.search(html)
        if cid_match is None:
            cid_match = _OG_URL_CID_RE.search(html)
        if cid_match is None:
            return None
        channel_id = cid_match.group(1)

        name_match = _OG_TITLE_RE.search(html)
        name = name_match.group(1) if name_match else handle
        return channel_id, name

    async def _get_channel_name(self, channel_id: str, session: ClientSession) -> str | None:
        url = f"https://www.youtube.com/channel/{channel_id}"
        headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
        try:
            async with session.get(url, headers=headers, timeout=self._timeout, allow_redirects=True) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()
        except Exception:
            return None
        name_match = _OG_TITLE_RE.search(html)
        return name_match.group(1) if name_match else channel_id


def _is_blocked(html: str) -> bool:
    return "unusual traffic" in html.lower()
