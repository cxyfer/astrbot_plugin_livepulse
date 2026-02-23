from __future__ import annotations

from aiohttp import ClientSession, ClientTimeout

from astrbot.api import logger

from core.models import StatusSnapshot, ChannelInfo
from platforms.base import BasePlatformChecker, RateLimitError

_API_URL = "https://api.live.bilibili.com/room/v1/Room/get_status_info_by_uids"
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
                    results[uid] = StatusSnapshot(is_live=False, streamer_name=uid)
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

    async def validate_channel(self, channel_id: str, session: ClientSession) -> ChannelInfo | None:
        try:
            int(channel_id)
        except ValueError:
            return None
        try:
            async with session.post(_API_URL, json={"uids": [int(channel_id)]}, timeout=self._timeout) as resp:
                resp.raise_for_status()
                data = await resp.json()
        except Exception as e:
            logger.warning(f"Bilibili validate failed for {channel_id}: {e}")
            return None
        info = data.get("data", {}).get(str(channel_id))
        if info is None:
            return None
        return ChannelInfo(
            channel_id=channel_id,
            channel_name=info.get("uname", channel_id),
            platform="bilibili",
        )
