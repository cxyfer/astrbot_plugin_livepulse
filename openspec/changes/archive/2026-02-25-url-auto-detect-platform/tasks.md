## 1. Platform Checker URL Support

- [x] 1.1 Add `_YT_URL_RE` regex to `platforms/youtube.py` (module-level, after existing imports/constants) with pattern `r"(?:https?://)?(?:www\.)?youtube\.com/(?:(@[\w.-]+)|channel/(UC[\w-]{22}))"` and flags `re.IGNORECASE | re.ASCII`. Update `validate_channel` to call `_YT_URL_RE.search(channel_id)` at the top: if group(1) matches, set `channel_id = match.group(1)` (@handle); if group(2) matches, set `channel_id = match.group(2)` (UC... ID). Then fall through to existing `if channel_id.startswith("@")` / `else` branches.
- [x] 1.2 Add `_TWITCH_URL_RE` regex to `platforms/twitch.py` (module-level) with pattern `r"(?:https?://)?(?:(?:www|m)\.)?twitch\.tv/([\w]+)"` and flags `re.IGNORECASE | re.ASCII`. Add `_RESERVED_PATHS: frozenset[str] = frozenset({"directory", "settings", "videos", "p"})`. Update `validate_channel` to call `_TWITCH_URL_RE.search(channel_id)` at the top: if match and `match.group(1).lower() not in _RESERVED_PATHS`, set `channel_id = match.group(1)`. Then fall through to existing Helix lookup.

## 2. Auto-Detect in cmd_add

- [x] 2.1 Add to `main.py` (module-level, after existing imports): `from urllib.parse import urlparse` and define `_HOST_PLATFORM_MAP: dict[str, str]` with keys `youtube.com`, `www.youtube.com`, `m.youtube.com`, `twitch.tv`, `www.twitch.tv`, `m.twitch.tv`, `live.bilibili.com` mapping to their platform names. Add `_detect_platform(raw: str) -> str | None` function: prepend `https://` if `://` not in raw, call `urlparse(url).hostname`, return `_HOST_PLATFORM_MAP.get(host.lower())` or `None`.
- [x] 2.2 Change `cmd_add` signature to `channel_id: str = ""`. Replace the current `platform = platform.lower()` + `if platform not in _VALID_PLATFORMS` block with: if `not channel_id`: set `raw_input = platform.strip()`, call `_detect_platform(raw_input)` — if detected, set `platform, channel_id = detected, raw_input`; elif `"." in raw_input and "/" in raw_input`, yield `cmd.add.unrecognized_url` and return; else set `platform = raw_input.lower()`, if in `_VALID_PLATFORMS` yield `cmd.add.invalid_channel` and return, otherwise yield `cmd.add.invalid_platform` and return. If `channel_id` is non-empty (explicit path), set `platform = platform.lower()` and continue with existing `_VALID_PLATFORMS` check.
- [x] 2.3 Verify error flow: `/live add youtube` → `invalid_channel`; `/live add tiktok` → `invalid_platform`; `/live add https://unknown.com/x` → `unrecognized_url`; `/live add youtube.com/` → auto-detect hits youtube → checker regex no match → `invalid_channel`. No code change needed if 2.2 is correct; this is a verification-only task.

## 3. i18n

- [x] 3.1 Add `cmd.add.unrecognized_url` key to `en.json` (`"Unrecognized URL. Supported: youtube.com, twitch.tv, live.bilibili.com"`), `zh-Hans.json` (`"无法识别的 URL。支持：youtube.com、twitch.tv、live.bilibili.com"`), and `zh-Hant.json` (`"無法識別的 URL。支援：youtube.com、twitch.tv、live.bilibili.com"`). No placeholders in this key.

## PBT Properties

### _detect_platform
- P1: Idempotent — same input always returns same platform or None
- P2: Host-only — result depends solely on urlparse hostname, not path/query/fragment
- P3: No false positives — only exact hosts in `_HOST_PLATFORM_MAP` match; look-alike hosts (`notyoutube.com`, `mytwitch.tv`) return None
- P4: Case-insensitive — `YOUTUBE.COM` and `youtube.com` return same result
- P5: Never raises — returns None for any malformed input

### YouTube _YT_URL_RE
- P6: Extracts exactly one group — either group(1) @handle or group(2) UC... ID, never both
- P7: Rejects unsupported paths — `/user/`, `/c/`, `/watch?v=` do not match
- P8: ASCII-only — non-ASCII characters in handle position do not match
- P9: Round-trip — `validate_channel(url)` with mock produces same ChannelInfo as `validate_channel(extracted_id)`

### Twitch _TWITCH_URL_RE
- P10: First segment extraction — extracts first path segment regardless of trailing content
- P11: Reserved path rejection — `directory`, `settings`, `videos`, `p` (case-insensitive) are rejected
- P12: ASCII-only — non-ASCII characters do not match
- P13: Round-trip — `validate_channel(url)` with mock produces same ChannelInfo as `validate_channel(extracted_username)`

### cmd_add routing
- P14: Two-arg backward compatibility — `cmd_add(platform, channel_id)` with non-empty channel_id behaves identically to pre-change
- P15: Deterministic error routing — each single-arg input maps to exactly one of: auto-detect success, `unrecognized_url`, `invalid_channel`, `invalid_platform`
- P16: No URL mutation — auto-detect path passes raw URL (stripped, not lowercased) to validate_channel
- P17: Whitespace invariance — leading/trailing whitespace does not change routing outcome
