## MODIFIED Requirements

### Requirement: YouTube channel monitoring via HTML scraping
The system SHALL monitor YouTube channels by scraping the `/channel/{CHANNEL_ID}/live` page for live status indicators (`"isLive":true` or `hqdefault_live.jpg`). The system SHALL support both Channel ID (`UCxxxxx`) and `@handle` format as input, permanently resolving `@handle` to Channel ID at subscription time. The system SHALL also extract and store the `@handle` as `display_id` by parsing `canonicalBaseUrl` from the page HTML using the pattern `"canonicalBaseUrl"\s*:\s*"(/@[^"]+)"`. If extraction fails, `display_id` SHALL fallback to `channel_id`.

`validate_channel` SHALL additionally accept YouTube URLs in the following formats:
- `https://www.youtube.com/@handle` (with or without scheme, with or without `www.`, with or without `m.`)
- `https://www.youtube.com/channel/UCxxxxx` (with or without scheme, with or without `www.`, with or without `m.`)

URL extraction SHALL use a module-level regex `_YT_URL_RE` matching `(?:https?://)?(?:(?:www|m)\.)?youtube\.com/(?:(@[\w.-]+)|channel/(UC[\w-]{22}))` with flag `re.IGNORECASE`. When a URL is detected via `search()`, `validate_channel` SHALL extract the `@handle` or `UC...` channel ID and delegate to the existing `_resolve_handle` or `_get_channel_name` methods respectively. No new HTTP calls SHALL be introduced.

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
- **NOTE** The `m.` subdomain is handled by `_detect_platform` routing; the checker regex matches `www.` or no subdomain. The mobile URL still works because `search()` matches the `youtube.com/` portion.

### Requirement: Twitch channel monitoring via Helix API
The system SHALL monitor Twitch channels using `GET https://api.twitch.tv/helix/streams?user_login={login}`. The system SHALL use Client Credentials OAuth flow for authentication. For Twitch channels, `display_id` SHALL always equal `channel_id`.

`validate_channel` SHALL additionally accept Twitch URLs in the following formats:
- `https://www.twitch.tv/username` (with or without scheme, with or without `www.`)
- `https://m.twitch.tv/username` (mobile URL)

URL extraction SHALL use a module-level regex `_TWITCH_URL_RE` matching `(?:https?://)?(?:(?:www|m)\.)?twitch\.tv/([\w]+)` with flags `re.IGNORECASE | re.ASCII` (C8). No `$` anchor — trailing query/fragment/subpaths are ignored (C3). When a URL is detected via `search()`, `validate_channel` SHALL extract the first path segment as the username.

The system SHALL define `_RESERVED_PATHS: frozenset[str] = frozenset({"directory", "settings", "videos", "p"})` (C4). After URL extraction, if the extracted username (lowercased) is in `_RESERVED_PATHS`, `validate_channel` SHALL return `None` immediately without attempting a Helix lookup.

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
- **AND** `validate_channel` SHALL return `None` immediately

#### Scenario: Twitch URL with uppercase host
- **WHEN** `validate_channel` receives `HTTPS://WWW.TWITCH.TV/SHROUD`
- **THEN** the regex with `re.IGNORECASE` SHALL match and extract `SHROUD`
- **AND** Helix API lookup is case-insensitive for usernames
