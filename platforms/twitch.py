from __future__ import annotations

import asyncio
import re
import time

from aiohttp import ClientSession, ClientTimeout
from astrbot.api import logger

from core.models import ChannelInfo, StatusSnapshot
from platforms.base import BasePlatformChecker, RateLimitError

_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
_STREAMS_URL = "https://api.twitch.tv/helix/streams"
_USERS_URL = "https://api.twitch.tv/helix/users"
_BATCH_SIZE = 100
_TWITCH_URL_RE = re.compile(
    r"(?:https?://)?(?:(?:www|m)\.)?twitch\.tv/([\w]+)",
    re.IGNORECASE | re.ASCII,
)
_RESERVED_PATHS: frozenset[str] = frozenset({"directory", "settings", "videos", "p"})


class TwitchChecker(BasePlatformChecker):
    platform_name = "twitch"

    def __init__(self, client_id: str, client_secret: str, timeout: int = 10) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = ClientTimeout(total=timeout)
        self._access_token: str = ""
        self._expires_at: float = 0.0
        self._token_lock = asyncio.Lock()

    async def _ensure_token(self, session: ClientSession) -> str:
        async with self._token_lock:
            if self._access_token and time.time() < self._expires_at - 300:
                return self._access_token
            return await self._refresh_token(session)

    async def _refresh_token(self, session: ClientSession) -> str:
        payload = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "client_credentials",
        }
        async with session.post(
            _TOKEN_URL, data=payload, timeout=self._timeout
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
        self._access_token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 3600)
        return self._access_token

    def _headers(self) -> dict[str, str]:
        return {
            "Client-ID": self._client_id,
            "Authorization": f"Bearer {self._access_token}",
        }

    async def check_status(
        self, channel_ids: list[str], session: ClientSession
    ) -> dict[str, StatusSnapshot]:
        results: dict[str, StatusSnapshot] = {}
        await self._ensure_token(session)

        for i in range(0, len(channel_ids), _BATCH_SIZE):
            chunk = channel_ids[i : i + _BATCH_SIZE]
            params = [("user_login", uid) for uid in chunk]
            try:
                data = await self._get_with_retry(session, _STREAMS_URL, params)
            except RateLimitError:
                raise
            except Exception as e:
                logger.warning(f"Twitch streams query failed: {e}")
                for uid in chunk:
                    results[uid] = StatusSnapshot(
                        is_live=False, streamer_name=uid, success=False
                    )
                continue

            live_map: dict[str, dict] = {}
            for stream in data.get("data", []):
                login = (stream.get("user_login") or "").lower()
                live_map[login] = stream

            for uid in chunk:
                stream = live_map.get(uid.lower())
                if stream is None:
                    results[uid] = StatusSnapshot(is_live=False, streamer_name=uid)
                    continue
                thumb = (
                    stream.get("thumbnail_url", "")
                    .replace("{width}", "1280")
                    .replace("{height}", "720")
                )
                user_login = (stream.get("user_login") or uid).lower()
                results[uid] = StatusSnapshot(
                    is_live=True,
                    stream_id=stream.get("id", ""),
                    title=stream.get("title", ""),
                    category=stream.get("game_name", ""),
                    image_url=thumb,
                    streamer_name=stream.get("user_name", uid),
                    stream_url=f"https://www.twitch.tv/{uid}",
                    display_id=user_login,
                    login_name=user_login,
                )
        return results

    async def _get_with_retry(
        self, session: ClientSession, url: str, params: list[tuple[str, str]]
    ) -> dict:
        async with session.get(
            url, params=params, headers=self._headers(), timeout=self._timeout
        ) as resp:
            if resp.status == 429:
                raise RateLimitError("twitch")
            if resp.status == 401:
                await self._refresh_token(session)
                async with session.get(
                    url, params=params, headers=self._headers(), timeout=self._timeout
                ) as retry:
                    if retry.status == 429:
                        raise RateLimitError("twitch")
                    retry.raise_for_status()
                    return await retry.json()
            resp.raise_for_status()
            return await resp.json()

    def extract_id_from_url(self, raw: str) -> str:
        m = _TWITCH_URL_RE.search(raw)
        if m:
            extracted = m.group(1)
            if extracted.lower() not in _RESERVED_PATHS:
                return extracted
        return ""

    async def validate_channel(
        self, channel_id: str, session: ClientSession
    ) -> ChannelInfo | None:
        extracted = self.extract_id_from_url(channel_id)
        if extracted:
            channel_id = extracted
        await self._ensure_token(session)
        try:
            data = await self._get_with_retry(
                session, _USERS_URL, [("login", channel_id)]
            )
        except RateLimitError:
            raise
        except Exception as e:
            logger.warning(f"Twitch validate failed for {channel_id}: {e}")
            raise
        users = data.get("data", [])
        if not users:
            return None
        user = users[0]
        return ChannelInfo(
            channel_id=user.get("login", channel_id),
            channel_name=user.get("display_name", channel_id),
            platform="twitch",
        )
