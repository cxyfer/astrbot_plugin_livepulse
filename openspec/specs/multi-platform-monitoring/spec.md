# multi-platform-monitoring Specification

## Purpose
TBD - created by archiving change livepulse-plugin. Update Purpose after archive.
## Requirements
### Requirement: YouTube channel monitoring via HTML scraping
The system SHALL monitor YouTube channels by scraping the `/channel/{CHANNEL_ID}/live` page for live status indicators (`"isLive":true` or `hqdefault_live.jpg`). The system SHALL support both Channel ID (`UCxxxxx`) and `@handle` format as input, permanently resolving `@handle` to Channel ID at subscription time. The system SHALL also extract and store the `@handle` as `display_id` by parsing `canonicalBaseUrl` from the page HTML using the pattern `"canonicalBaseUrl"\s*:\s*"(/@[^"]+)"`. If extraction fails, `display_id` SHALL fallback to `channel_id`.

`validate_channel` SHALL additionally accept YouTube URLs in the following formats:
- `https://www.youtube.com/@handle` (with or without scheme, with or without `www.`, with or without `m.`)
- `https://www.youtube.com/channel/UCxxxxx` (with or without scheme, with or without `www.`, with or without `m.`)

URL extraction SHALL use a module-level regex `_YT_URL_RE` matching `(?:https?://)?(?:(?:www|m)\.)?youtube\.com/(?:(@[\w.-]+)|channel/(UC[\w-]{22}))` with flags `re.IGNORECASE | re.ASCII` (C8). When a URL is detected via `search()`, `validate_channel` SHALL extract the `@handle` or `UC...` channel ID and delegate to the existing `_resolve_handle` or `_get_channel_name` methods respectively. No new HTTP calls SHALL be introduced.

Out of scope: `/user/`, `/c/`, `youtu.be` URL formats (C7).

#### Scenario: Detect YouTube channel going live
- **WHEN** the YouTube poller scrapes a monitored channel's `/live` page
- **AND** the HTML contains `"isLive":true` or `hqdefault_live.jpg`
- **THEN** the system SHALL report the channel as live with extracted title, thumbnail URL, and `success = True`

#### Scenario: YouTube channel not live
- **WHEN** the YouTube poller scrapes a monitored channel's `/live` page
- **AND** no live indicators are found in the HTML
- **THEN** the system SHALL report the channel as offline with `success = True`

#### Scenario: YouTube @handle input resolution
- **WHEN** a user adds a YouTube monitor using `@handle` format
- **THEN** the system SHALL resolve the handle to a canonical Channel ID (`UCxxxxx`) via HTTP request
- **AND** store the resolved Channel ID for all subsequent polling
- **AND** store the `@handle` as `display_id` on the `ChannelInfo`

#### Scenario: YouTube @handle resolution failure
- **WHEN** handle resolution fails due to network error or invalid handle
- **THEN** the system SHALL reject the add operation and return an error message to the user

#### Scenario: YouTube HTML parse failure
- **WHEN** the scraper cannot parse the expected markers from the page
- **THEN** the system SHALL return `StatusSnapshot(is_live=False, success=False)`
- **AND** SHALL NOT emit live-start or live-end transitions
- **AND** SHALL continue retrying at the normal polling interval

#### Scenario: YouTube @handle extraction from channel page
- **WHEN** `validate_channel` or `_get_channel_name` fetches a YouTube channel page
- **AND** the HTML contains `"canonicalBaseUrl":"/@SomeHandle"`
- **THEN** the system SHALL extract `@SomeHandle` as the `display_id`

#### Scenario: YouTube @handle extraction fallback
- **WHEN** the YouTube page HTML does not contain a `canonicalBaseUrl` field
- **THEN** `display_id` SHALL fallback to the `channel_id` value

#### Scenario: YouTube poller updates display_id
- **WHEN** the poller checks a YouTube channel and `StatusSnapshot.success == True`
- **AND** `StatusSnapshot.display_id` is non-empty
- **THEN** the system SHALL update the `MonitorEntry.display_id` with the new value

#### Scenario: YouTube URL with @handle accepted by validate_channel
- **WHEN** `validate_channel` receives `https://www.youtube.com/@GawrGura`
- **THEN** the system SHALL extract `@GawrGura` from the URL via `_YT_URL_RE.search()`
- **AND** delegate to `_resolve_handle("@GawrGura", session)`
- **AND** return the resolved `ChannelInfo` on success

#### Scenario: YouTube URL with channel ID accepted by validate_channel
- **WHEN** `validate_channel` receives `https://www.youtube.com/channel/UCoSrY_IQQVpmIRZ9Xf-y93g`
- **THEN** the system SHALL extract `UCoSrY_IQQVpmIRZ9Xf-y93g` from the URL
- **AND** delegate to `_get_channel_name("UCoSrY_IQQVpmIRZ9Xf-y93g", session)`
- **AND** return the resolved `ChannelInfo` on success

#### Scenario: YouTube URL without scheme accepted
- **WHEN** `validate_channel` receives `youtube.com/@GawrGura` (no `https://`)
- **THEN** the system SHALL still extract `@GawrGura` and resolve normally

#### Scenario: YouTube URL with unrecognized path rejected
- **WHEN** `validate_channel` receives `https://www.youtube.com/watch?v=abc123`
- **THEN** the URL regex SHALL NOT match
- **AND** the input SHALL fall through to existing logic (treated as raw identifier)

#### Scenario: YouTube URL with uppercase host
- **WHEN** `validate_channel` receives `HTTPS://WWW.YOUTUBE.COM/@GawrGura`
- **THEN** the regex with `re.IGNORECASE` SHALL match and extract `@GawrGura`

#### Scenario: YouTube mobile URL accepted
- **WHEN** `validate_channel` receives `https://m.youtube.com/@GawrGura`
- **THEN** the system SHALL extract `@GawrGura` and resolve normally
- **NOTE** The `m.` subdomain is handled by `_detect_platform` routing; the checker regex matches `www.` or `m.` subdomains.

### Requirement: Twitch channel monitoring via Helix API
The system SHALL monitor Twitch channels using `GET https://api.twitch.tv/helix/streams?user_login={login}`. The system SHALL use Client Credentials OAuth flow for authentication. For Twitch channels, `display_id` SHALL always equal `channel_id`.

`validate_channel` SHALL additionally accept Twitch URLs in the following formats:
- `https://www.twitch.tv/username` (with or without scheme, with or without `www.`)
- `https://m.twitch.tv/username` (mobile URL)

URL extraction SHALL use a module-level regex `_TWITCH_URL_RE` matching `(?:https?://)?(?:(?:www|m)\.)?twitch\.tv/([\w]+)` with flags `re.IGNORECASE | re.ASCII` (C8). No `$` anchor — trailing query/fragment/subpaths are ignored (C3). When a URL is detected via `search()`, `validate_channel` SHALL extract the first path segment as the username.

The system SHALL define `_RESERVED_PATHS: frozenset[str] = frozenset({"directory", "settings", "videos", "p"})` (C4). After URL extraction, if the extracted username (lowercased) is in `_RESERVED_PATHS`, `validate_channel` SHALL treat the input as not a valid URL match and fall through to existing logic (which will fail at Helix lookup).

No new HTTP calls SHALL be introduced.

#### Scenario: Detect Twitch channel going live
- **WHEN** the Twitch poller queries the Helix API for a monitored username
- **AND** the `data` array is non-empty
- **THEN** the system SHALL report the channel as live with `title`, `game_name`, `thumbnail_url`, `user_name`, and `success = True`

#### Scenario: Twitch channel not live
- **WHEN** the Twitch poller queries the Helix API
- **AND** the `data` array is empty
- **THEN** the system SHALL report the channel as offline with `success = True`

#### Scenario: Twitch credentials not configured
- **WHEN** Twitch `client_id` or `client_secret` is empty in WebUI config
- **THEN** the system SHALL NOT start the Twitch poller task
- **AND** `/live add twitch` SHALL return a "credentials not configured" error

#### Scenario: Twitch API query failure
- **WHEN** the Twitch poller encounters a non-RateLimitError exception
- **THEN** the system SHALL return `StatusSnapshot(is_live=False, success=False)` for affected channels

#### Scenario: Twitch URL accepted by validate_channel
- **WHEN** `validate_channel` receives `https://www.twitch.tv/shroud`
- **THEN** the system SHALL extract `shroud` from the URL
- **AND** delegate to the existing Helix `/users?login=shroud` lookup
- **AND** return the resolved `ChannelInfo` on success

#### Scenario: Twitch mobile URL accepted by validate_channel
- **WHEN** `validate_channel` receives `https://m.twitch.tv/shroud`
- **THEN** the system SHALL extract `shroud` from the URL
- **AND** resolve normally via Helix API

#### Scenario: Twitch URL without scheme accepted
- **WHEN** `validate_channel` receives `twitch.tv/shroud` (no `https://`)
- **THEN** the system SHALL still extract `shroud` and resolve normally

#### Scenario: Twitch URL with subpath ignored
- **WHEN** `validate_channel` receives `https://www.twitch.tv/shroud/videos`
- **THEN** the URL regex SHALL match and extract `shroud` (first path segment only, C3)
- **AND** `/videos` subpath SHALL be ignored

#### Scenario: Twitch URL with trailing slash accepted
- **WHEN** `validate_channel` receives `https://www.twitch.tv/shroud/`
- **THEN** the system SHALL extract `shroud`

#### Scenario: Twitch URL with query parameters accepted
- **WHEN** `validate_channel` receives `https://www.twitch.tv/shroud?tt_content=channel`
- **THEN** the system SHALL extract `shroud` (query string ignored)

#### Scenario: Twitch reserved path rejected
- **WHEN** `validate_channel` receives `https://www.twitch.tv/directory`
- **THEN** the system SHALL extract `directory` but reject it via `_RESERVED_PATHS` check (C4)
- **AND** the input SHALL fall through to existing logic (Helix lookup with `directory` as login, which will return no user)

#### Scenario: Twitch URL with uppercase host
- **WHEN** `validate_channel` receives `HTTPS://WWW.TWITCH.TV/SHROUD`
- **THEN** the regex with `re.IGNORECASE` SHALL match and extract `SHROUD`
- **AND** Helix API lookup is case-insensitive for usernames

### Requirement: Bilibili user monitoring via public batch API
The system SHALL monitor Bilibili users using `POST https://api.live.bilibili.com/room/v1/Room/get_status_info_by_uids` with batch UID queries. No authentication is required. For Bilibili channels, `display_id` SHALL always equal `channel_id`.

#### Scenario: Detect Bilibili user going live
- **WHEN** the Bilibili poller queries the batch API
- **AND** a UID's `live_status == 1`
- **THEN** the system SHALL report the user as live with `uname`, `title`, `room_id`, `cover_from_user`, and `success = True`

#### Scenario: Bilibili user not live
- **WHEN** the Bilibili poller queries the batch API
- **AND** a UID's `live_status != 1`
- **THEN** the system SHALL report the user as offline with `success = True`

#### Scenario: Bilibili batch size limit
- **WHEN** more than 50 UIDs need to be queried
- **THEN** the system SHALL split the query into chunks of at most 50 UIDs per request

#### Scenario: Bilibili partial batch result
- **WHEN** the batch API response omits some requested UIDs
- **THEN** the system SHALL treat missing UIDs as `unknown` status
- **AND** SHALL NOT trigger offline transitions for missing UIDs

#### Scenario: Bilibili batch query failure
- **WHEN** the Bilibili poller encounters a non-RateLimitError exception during batch query
- **THEN** the system SHALL return `StatusSnapshot(is_live=False, success=False)` for affected UIDs

### Requirement: Platform-independent polling intervals
Each platform SHALL have a configurable global polling interval via WebUI. Default intervals: YouTube 300s, Twitch 120s, Bilibili 180s.

#### Scenario: Default polling intervals applied
- **WHEN** the plugin starts with default configuration
- **THEN** YouTube poller SHALL poll every 300s, Twitch every 120s, Bilibili every 180s

#### Scenario: Custom polling interval via WebUI
- **WHEN** an administrator changes a platform's polling interval in WebUI
- **THEN** the poller for that platform SHALL adopt the new interval on the next cycle

### Requirement: Global monitor count limit
The system SHALL enforce a global maximum of unique monitored channels (default 500, configurable via WebUI). The count is calculated after deduplication across all groups.

#### Scenario: Global limit reached
- **WHEN** a user attempts to add a monitor that would cause the global unique channel count to exceed the configured maximum
- **THEN** the system SHALL reject the add operation with a "global limit reached" error

#### Scenario: Shared channel does not double-count
- **WHEN** Group A and Group B both monitor the same YouTube channel
- **THEN** the system SHALL count that channel as 1 toward the global limit

### Requirement: Shared HTTP session MUST include browser-like User-Agent
The shared `aiohttp.ClientSession` SHALL be initialized with a default `User-Agent` header set to the value of `DEFAULT_USER_AGENT` defined in `platforms/__init__.py`. All platform checkers using the shared session SHALL inherit this header automatically. The User-Agent value SHALL be a standard desktop Chrome browser string.

#### Scenario: Bilibili API accepts requests with shared session UA
- **WHEN** the Bilibili checker sends a POST to `get_status_info_by_uids` via the shared session
- **THEN** the request SHALL include a `User-Agent` header equal to `DEFAULT_USER_AGENT`
- **AND** Bilibili SHALL NOT return HTTP 412

#### Scenario: Bilibili room resolution uses shared session UA
- **WHEN** the Bilibili checker sends a GET to `get_info?room_id=X` via the shared session
- **THEN** the request SHALL include the session-level `User-Agent` header

#### Scenario: Per-request headers merge with session defaults
- **WHEN** a platform checker (e.g., YouTube) provides per-request headers
- **THEN** those headers SHALL merge with (not replace) the session-level `User-Agent`
- **AND** if per-request headers include `User-Agent`, the per-request value SHALL take precedence

#### Scenario: Twitch API unaffected by session-level UA
- **WHEN** the Twitch checker sends requests with `Client-ID` and `Authorization` headers via the shared session
- **THEN** the session-level `User-Agent` SHALL also be sent
- **AND** the Twitch API SHALL respond normally (UA does not conflict with OAuth headers)

### Requirement: Single source of truth for User-Agent constant
The `DEFAULT_USER_AGENT` constant SHALL be defined in `platforms/__init__.py`. Both the session initialization in `main.py` and any per-request header construction (e.g., YouTube) SHALL import from this single location. No duplicate UA string literals SHALL exist across the codebase.

#### Scenario: YouTube per-request UA matches session default
- **WHEN** YouTube constructs per-request headers with a User-Agent
- **THEN** the value SHALL be imported from `DEFAULT_USER_AGENT` in `platforms/__init__.py`
- **AND** no hardcoded UA string SHALL exist in `youtube.py`

### Requirement: StatusSnapshot success field
`StatusSnapshot` SHALL include a `success: bool` field (default `True`). When a platform checker encounters a non-`RateLimitError` exception during `check_status`, it SHALL set `success = False` on the returned snapshot instead of silently mapping the error to `is_live = False`. The poller and `cmd_add` initialization logic SHALL only update `MonitorEntry.last_status` and `MonitorEntry.initialized` when `success == True`.

#### Scenario: Successful status check
- **WHEN** a platform checker successfully queries a channel's status
- **THEN** `StatusSnapshot.success` SHALL be `True`
- **AND** the poller SHALL update `MonitorEntry.last_status` and `initialized`

#### Scenario: Failed status check
- **WHEN** a platform checker fails to query a channel (network error, parse error)
- **THEN** `StatusSnapshot.success` SHALL be `False`
- **AND** the poller SHALL NOT update `MonitorEntry.last_status` or `initialized`
- **AND** the poller SHALL NOT trigger live-start or live-end notifications

#### Scenario: Failed check does not overwrite existing state
- **WHEN** a `MonitorEntry` has `initialized = True` and `last_status = "live"`
- **AND** the next check returns `success = False`
- **THEN** the entry SHALL retain `initialized = True` and `last_status = "live"`

### Requirement: StatusSnapshot display_id field
`StatusSnapshot` SHALL include a `display_id: str | None` field (default `None`). Platform checkers MAY populate this field during `check_status`. The poller SHALL update `MonitorEntry.display_id` when `success == True` and `display_id` is non-empty.

#### Scenario: Poller receives display_id from YouTube
- **WHEN** YouTube `check_status` returns `StatusSnapshot` with `display_id = "@handle"`
- **AND** `success == True`
- **THEN** the poller SHALL update `MonitorEntry.display_id` to `"@handle"`

#### Scenario: Poller ignores display_id on failure
- **WHEN** `check_status` returns `StatusSnapshot` with `success == False`
- **THEN** the poller SHALL NOT update `MonitorEntry.display_id` regardless of the `display_id` value

#### Scenario: Poller ignores empty display_id
- **WHEN** `check_status` returns `StatusSnapshot` with `display_id = None` or `""`
- **AND** `success == True`
- **THEN** the poller SHALL NOT overwrite the existing `MonitorEntry.display_id`

### Requirement: ChannelInfo display_id field
`ChannelInfo` SHALL include a `display_id: str` field. YouTube `validate_channel` SHALL populate `display_id` with the resolved `@handle` (fallback to `channel_id`). Bilibili and Twitch `validate_channel` SHALL set `display_id = channel_id`.

#### Scenario: YouTube ChannelInfo with @handle
- **WHEN** `validate_channel` resolves a YouTube channel with `canonicalBaseUrl = "/@MyHandle"`
- **THEN** `ChannelInfo.display_id` SHALL be `"@MyHandle"`

#### Scenario: YouTube ChannelInfo without @handle
- **WHEN** `validate_channel` cannot extract `canonicalBaseUrl`
- **THEN** `ChannelInfo.display_id` SHALL equal `ChannelInfo.channel_id`

#### Scenario: Bilibili ChannelInfo display_id
- **WHEN** `validate_channel` succeeds for a Bilibili channel
- **THEN** `ChannelInfo.display_id` SHALL equal `ChannelInfo.channel_id`

#### Scenario: Twitch ChannelInfo display_id
- **WHEN** `validate_channel` succeeds for a Twitch channel
- **THEN** `ChannelInfo.display_id` SHALL equal `ChannelInfo.channel_id`

### Requirement: MonitorEntry display_id field
`MonitorEntry` SHALL include a `display_id: str` field. `to_dict` SHALL serialize this field. `from_dict` SHALL deserialize with fallback: `display_id = d.get("display_id", d["channel_id"])` to maintain backward compatibility with existing data.

#### Scenario: New MonitorEntry serialization round-trip
- **WHEN** a `MonitorEntry` with `display_id = "@handle"` is serialized and deserialized
- **THEN** `display_id` SHALL be preserved as `"@handle"`

#### Scenario: Legacy data without display_id
- **WHEN** `from_dict` receives a dict without `display_id` key
- **THEN** `display_id` SHALL default to `channel_id`

### Requirement: Store display_id lookup for remove
`Store` SHALL provide a method to resolve a `display_id` to a `channel_id` within a group's platform monitors. `cmd_remove` SHALL use this lookup when the provided identifier does not directly match a `channel_id`.

#### Scenario: Lookup existing display_id
- **WHEN** `lookup_by_display_id` is called with `platform = "youtube"` and `display_id = "@handle"`
- **AND** a monitor exists with `display_id == "@handle"` in the group
- **THEN** the method SHALL return the corresponding `channel_id`

#### Scenario: Lookup non-existent display_id
- **WHEN** `lookup_by_display_id` is called with a `display_id` that matches no monitor
- **THEN** the method SHALL return `None`

