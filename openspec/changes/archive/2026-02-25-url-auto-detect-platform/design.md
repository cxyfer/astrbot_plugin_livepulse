## Context

`cmd_add` currently requires two positional args: `platform` and `channel_id`. Bilibili's `validate_channel` already extracts room IDs from URLs via `_BILI_URL_RE`. YouTube and Twitch checkers accept only raw identifiers (@handle, UC... channel ID, username). Users expect to paste browser URLs directly.

Confirmed constraints from user:
- YouTube: `youtube.com/@handle` and `youtube.com/channel/UC...` only (no /live/, no youtu.be)
- Twitch: `twitch.tv/username` and `m.twitch.tv/username`
- Bilibili: no change (existing regex sufficient)
- Auto-detect triggers only when platform arg is omitted

## Goals / Non-Goals

**Goals:**
- Each checker's `validate_channel` handles its own URL extraction internally (same pattern as Bilibili)
- `cmd_add` accepts `/live add <url>` with auto-detection when platform is omitted
- Full backward compatibility with `/live add <platform> <channel_id>`

**Non-Goals:**
- Short URLs (youtu.be, b23.tv) — requires HTTP redirect follow, out of scope
- `/live/VIDEO_ID` URLs — these are stream links, not channel identifiers
- Changes to `cmd_check` or `cmd_remove`
- URL support in any command other than `cmd_add`
- Legacy YouTube paths (`/user/`, `/c/`) — out of scope (C7)

## Decisions

### D1: URL regex placement — inside each checker

Each platform checker adds a module-level regex and handles URL extraction at the top of `validate_channel`, before delegating to existing resolution logic. This mirrors the Bilibili pattern exactly.

**YouTube** (`platforms/youtube.py`):
```python
_YT_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?youtube\.com/"
    r"(?:(@[\w.-]+)|channel/(UC[\w-]{22}))",
    re.IGNORECASE | re.ASCII,
)
```
- Group 1 → `@handle`, delegate to `_resolve_handle`
- Group 2 → `UC...` channel ID, delegate to `_get_channel_name`
- `re.IGNORECASE` handles uppercase scheme/host; `re.ASCII` restricts `\w` to ASCII (C8)

**Twitch** (`platforms/twitch.py`):
```python
_TWITCH_URL_RE = re.compile(
    r"(?:https?://)?(?:(?:www|m)\.)?twitch\.tv/([\w]+)",
    re.IGNORECASE | re.ASCII,
)

_RESERVED_PATHS: frozenset[str] = frozenset({"directory", "settings", "videos", "p"})
```
- Group 1 → first path segment as username, delegate to existing Helix lookup
- No `$` anchor — trailing query/fragment/subpaths are ignored (C3)
- `_RESERVED_PATHS` blacklist rejects known non-channel paths before API call (C4)

**Rationale over centralizing in main.py**: Each checker owns its identifier formats. Adding URL awareness to checkers keeps the single-responsibility boundary clean and makes future platform additions self-contained.

### D2: `cmd_add` signature change for auto-detect

Make `channel_id` optional with default `""`:
```python
async def cmd_add(self, event, platform: str, channel_id: str = ""):
```

Detection logic in `cmd_add` (before platform validation):
```python
if not channel_id:
    raw_input = platform.strip()  # C9: normalize whitespace
    detected = _detect_platform(raw_input)
    if detected:
        platform, channel_id = detected, raw_input  # C5: pass raw URL
    elif "." in raw_input and "/" in raw_input:
        # URL heuristic: looks like URL but host not recognized
        yield error "cmd.add.unrecognized_url"
        return
    else:
        platform = raw_input.lower()
        if platform in _VALID_PLATFORMS:
            yield error "cmd.add.invalid_channel"  # missing channel_id
            return
        yield error "cmd.add.invalid_platform"
        return
else:
    platform = platform.lower()  # explicit path: lowercase as before
```

The URL is passed as-is to `validate_channel`, which handles extraction internally.

**Rationale**: Domain-to-platform mapping lives in `main.py` (routing concern), URL-to-identifier extraction lives in checkers (platform concern). Clean separation.

### D3: Domain matching via `urlparse` + host allowlist

Replace regex-based domain matching with structured URL parsing (C1):
```python
from urllib.parse import urlparse

_HOST_PLATFORM_MAP: dict[str, str] = {
    "youtube.com": "youtube",
    "www.youtube.com": "youtube",
    "m.youtube.com": "youtube",
    "twitch.tv": "twitch",
    "www.twitch.tv": "twitch",
    "m.twitch.tv": "twitch",
    "live.bilibili.com": "bilibili",
}

def _detect_platform(raw: str) -> str | None:
    url = raw if "://" in raw else f"https://{raw}"
    try:
        host = urlparse(url).hostname
    except Exception:
        return None
    if host is None:
        return None
    return _HOST_PLATFORM_MAP.get(host.lower())
```

**Rationale over regex**: `urlparse` eliminates substring false positives (`notyoutube.com`, `mytwitch.tv`), handles case-insensitive hosts naturally, and is more maintainable than anchored regex patterns.

### D4: Detecting auto-detect path vs explicit platform

The heuristic: if `channel_id` is empty, the user invoked `/live add <single_arg>`. The `platform` parameter then holds whatever the user typed.

Priority order (deterministic, no ambiguity):
1. `_detect_platform(raw_input)` succeeds → auto-detect path
2. `"." in raw_input and "/" in raw_input` → `cmd.add.unrecognized_url`
3. `raw_input.lower() in _VALID_PLATFORMS` → `cmd.add.invalid_channel` (missing channel_id)
4. Otherwise → `cmd.add.invalid_platform` (existing behavior)

### D5: i18n — single new key

Add `cmd.add.unrecognized_url` to all 3 locale files (C11):
- en: `"Unrecognized URL. Supported: youtube.com, twitch.tv, live.bilibili.com"`
- zh-Hans: `"无法识别的 URL。支持：youtube.com、twitch.tv、live.bilibili.com"`
- zh-Hant: `"無法識別的 URL。支援：youtube.com、twitch.tv、live.bilibili.com"`

## Risks / Trade-offs

**R1: Twitch URL reserved path false positives** → Mitigation: `_RESERVED_PATHS` frozenset rejects `directory`, `settings`, `videos`, `p` before Helix API call (C4). Non-blacklisted paths that aren't real users will fail gracefully at Helix lookup.

**R2: YouTube handle charset edge cases** → Mitigation: `[\w.-]+` with `re.ASCII` covers documented YouTube handle characters (alphanumeric, underscore, dot, hyphen). Handles that don't exist will fail gracefully at `_resolve_handle`.

**R3: User types platform name without channel_id** (e.g., `/live add youtube`) → Mitigation: `"youtube"` doesn't contain `.` and `/`, so it falls through to `_VALID_PLATFORMS` check → `cmd.add.invalid_channel`.

**R4: Trailing slashes / query params / fragments in URLs** → Mitigation: Checker regexes use `search()` not `fullmatch()`, so trailing content is ignored. The captured group is the identifier.

**R5: Host-only URL** (e.g., `youtube.com/`) → Mitigation: `_detect_platform` matches the host, URL is passed to checker, checker regex finds no valid path → `validate_channel` returns `None` → `cmd.add.invalid_channel` (C6).

**R6: URL case sensitivity** → Mitigation: `_detect_platform` lowercases host via `urlparse`. Checker regexes use `re.IGNORECASE`. YouTube `UC...` channel IDs preserve original case because auto-detect path does not lowercase the raw URL (C5).

## Resolved Constraints

| ID | Constraint | Decision |
|----|-----------|----------|
| C1 | Domain matching strategy | `urlparse` + `_HOST_PLATFORM_MAP` host allowlist |
| C2 | Host allowlist scope | `youtube.com`, `www.youtube.com`, `m.youtube.com`, `twitch.tv`, `www.twitch.tv`, `m.twitch.tv`, `live.bilibili.com` |
| C3 | Twitch regex anchoring | No `$` anchor; extract first path segment; `re.IGNORECASE \| re.ASCII` |
| C4 | Twitch reserved paths | `_RESERVED_PATHS = frozenset({"directory", "settings", "videos", "p"})` |
| C5 | lowercase timing | Auto-detect passes raw URL to `validate_channel`; explicit path lowercases platform |
| C6 | Host-only URL behavior | Auto-detect → checker regex no match → `invalid_channel` |
| C7 | YouTube URL scope | Only `@handle` and `channel/UC...`; `/user/`, `/c/`, `youtu.be` out of scope |
| C8 | Regex flags | All URL regexes use `re.IGNORECASE \| re.ASCII` |
| C9 | Input normalization | `raw_input = platform.strip()` |
| C10 | Constant naming | `_HOST_PLATFORM_MAP` (replaces `_URL_PLATFORM_MAP` from initial design) |
| C11 | i18n scope | `cmd.add.unrecognized_url` in `en.json`, `zh-Hans.json`, `zh-Hant.json` |
