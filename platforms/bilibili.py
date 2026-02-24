from __future__ import annotations

import re

from aiohttp import ClientSession, ClientTimeout

from astrbot.api import logger

from core.models import StatusSnapshot, ChannelInfo
from platforms.base import BasePlatformChecker, RateLimitError

_API_URL = "https://api.live.bilibili.com/room/v1/Room/get_status_info_by_uids"
_BILI_URL_RE = re.compile(r"(?:https?://)?live\.bilibili\.com/(\d+)")
_ROOM_INFO_URL = "https://api.live.bilibili.com/room/v1/Room/get_info"
_CHUNK_SIZE = 50


class BilibiliChecker(BasePlatformChecker):
    platform_name = "bilibili"

    def __init__(self, timeout: int = 10) -> None:
        self._timeout = ClientTimeout(total=timeout)

    async def check_status(self, channel_ids: list[str], session: ClientSession) -> dict[str, StatusSnapshot]:
        results: dict[str, StatusSnapshot] = {}
        for i in range(0, len(channel_ids), _CHUNK_SIZE):
            chunk = channel_ids[i : i + _CHUNK_SIZE]
            valid_uids: list[int] = []
            for uid in chunk:
                try:
                    valid_uids.append(int(uid))
                except ValueError:
                    logger.warning(f"Bilibili: skipping invalid UID {uid}")
                    results[uid] = StatusSnapshot(is_live=False, streamer_name=uid)
            if not valid_uids:
                continue
            try:
                async with session.post(_API_URL, json={"uids": valid_uids}, timeout=self._timeout) as resp:
                    if resp.status == 429:
                        raise RateLimitError("bilibili")
                    resp.raise_for_status()
                    data = await resp.json()
            except RateLimitError:
                raise
            except Exception as e:
                logger.warning(f"Bilibili batch query failed: {e}")
                for uid in chunk:
                    results[uid] = StatusSnapshot(is_live=False, streamer_name=uid, success=False)
                continue
            info_map = data.get("data", {})
            for uid in chunk:
                info = info_map.get(str(uid))
                if info is None:
                    results[uid] = StatusSnapshot(is_live=False, streamer_name=uid)
                    continue
                is_live = info.get("live_status") == 1
                room_id = str(info.get("room_id", ""))
                results[uid] = StatusSnapshot(
                    is_live=is_live,
                    stream_id=room_id if is_live else "",
                    title=info.get("title", ""),
                    category=info.get("area_v2_name", ""),
                    thumbnail_url=info.get("cover_from_user", ""),
                    streamer_name=info.get("uname", uid),
                    stream_url=f"https://live.bilibili.com/{room_id}" if room_id else "",
                )
        return results

    async def _resolve_room_id(self, room_id: str, session: ClientSession) -> str | None:
        try:
            async with session.get(_ROOM_INFO_URL, params={"room_id": room_id}, timeout=self._timeout) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except Exception as e:
            logger.warning(f"Bilibili room resolve failed for {room_id}: {e}")
            return None
        uid = data.get("data", {}).get("uid")
        return str(uid) if uid is not None else None

    async def _validate_uid(self, uid: str, session: ClientSession) -> ChannelInfo | None:
        try:
            uid_int = int(uid)
        except ValueError:
            return None
        uid_str = str(uid_int)
        try:
            async with session.post(_API_URL, json={"uids": [uid_int]}, timeout=self._timeout) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except Exception as e:
            logger.warning(f"Bilibili validate failed for {uid_str}: {e}")
            return None
        info = data.get("data", {}).get(uid_str)
        if info is None:
            return None
        return ChannelInfo(
            channel_id=uid_str,
            channel_name=info.get("uname", uid_str),
            platform="bilibili",
        )

    async def validate_channel(self, channel_id: str, session: ClientSession) -> ChannelInfo | None:
        url_match = _BILI_URL_RE.search(channel_id)
        if url_match:
            room_id = url_match.group(1)
            uid = await self._resolve_room_id(room_id, session)
            if uid is None:
                return None
            return await self._validate_uid(uid, session)
        if channel_id.isdigit():
            return await self._validate_uid(channel_id, session)
        return None
