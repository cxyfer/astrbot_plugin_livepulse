# multi-platform-monitoring Specification

## Purpose
TBD - created by archiving change livepulse-plugin. Update Purpose after archive.
## Requirements
### Requirement: YouTube channel monitoring via HTML scraping
The system SHALL monitor YouTube channels by scraping the `/channel/{CHANNEL_ID}/live` page for live status indicators (`"isLive":true` or `hqdefault_live.jpg`). The system SHALL support both Channel ID (`UCxxxxx`) and `@handle` format as input, permanently resolving `@handle` to Channel ID at subscription time.

#### Scenario: Detect YouTube channel going live
- **WHEN** the YouTube poller scrapes a monitored channel's `/live` page
- **AND** the HTML contains `"isLive":true` or `hqdefault_live.jpg`
- **THEN** the system SHALL report the channel as live with extracted title and thumbnail URL

#### Scenario: YouTube channel not live
- **WHEN** the YouTube poller scrapes a monitored channel's `/live` page
- **AND** no live indicators are found in the HTML
- **THEN** the system SHALL report the channel as offline

#### Scenario: YouTube @handle input resolution
- **WHEN** a user adds a YouTube monitor using `@handle` format
- **THEN** the system SHALL resolve the handle to a canonical Channel ID (`UCxxxxx`) via HTTP request
- **AND** store only the resolved Channel ID for all subsequent polling

#### Scenario: YouTube @handle resolution failure
- **WHEN** handle resolution fails due to network error or invalid handle
- **THEN** the system SHALL reject the add operation and return an error message to the user

#### Scenario: YouTube HTML parse failure
- **WHEN** the scraper cannot parse the expected markers from the page
- **THEN** the system SHALL mark the channel status as `unknown`
- **AND** SHALL NOT emit live-start or live-end transitions
- **AND** SHALL continue retrying at the normal polling interval

### Requirement: Twitch channel monitoring via Helix API
The system SHALL monitor Twitch channels using `GET https://api.twitch.tv/helix/streams?user_login={login}`. The system SHALL use Client Credentials OAuth flow for authentication.

#### Scenario: Detect Twitch channel going live
- **WHEN** the Twitch poller queries the Helix API for a monitored username
- **AND** the `data` array is non-empty
- **THEN** the system SHALL report the channel as live with `title`, `game_name`, `thumbnail_url`, and `user_name`

#### Scenario: Twitch channel not live
- **WHEN** the Twitch poller queries the Helix API
- **AND** the `data` array is empty
- **THEN** the system SHALL report the channel as offline

#### Scenario: Twitch credentials not configured
- **WHEN** Twitch `client_id` or `client_secret` is empty in WebUI config
- **THEN** the system SHALL NOT start the Twitch poller task
- **AND** `/live add twitch` SHALL return a "credentials not configured" error

### Requirement: Bilibili user monitoring via public batch API
The system SHALL monitor Bilibili users using `POST https://api.live.bilibili.com/room/v1/Room/get_status_info_by_uids` with batch UID queries. No authentication is required.

#### Scenario: Detect Bilibili user going live
- **WHEN** the Bilibili poller queries the batch API
- **AND** a UID's `live_status == 1`
- **THEN** the system SHALL report the user as live with `uname`, `title`, `room_id`, and `cover_from_user`

#### Scenario: Bilibili user not live
- **WHEN** the Bilibili poller queries the batch API
- **AND** a UID's `live_status != 1`
- **THEN** the system SHALL report the user as offline

#### Scenario: Bilibili batch size limit
- **WHEN** more than 50 UIDs need to be queried
- **THEN** the system SHALL split the query into chunks of at most 50 UIDs per request

#### Scenario: Bilibili partial batch result
- **WHEN** the batch API response omits some requested UIDs
- **THEN** the system SHALL treat missing UIDs as `unknown` status
- **AND** SHALL NOT trigger offline transitions for missing UIDs

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

