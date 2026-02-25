## MODIFIED Requirements

### Requirement: /live add command
The system SHALL provide `/live add <platform> <channel_id>` to add a monitor to the current group. Platform MUST be one of `youtube`, `twitch`, `bilibili`. After successful addition and persistence, the system SHALL perform a single immediate status check for the newly added channel. If the check succeeds (`StatusSnapshot.success == True`), the system SHALL update the monitor's `last_status` and set `initialized = True` before responding. If the check fails, the system SHALL keep `last_status = "unknown"` and `initialized = False`, and SHALL NOT block the add operation.

The system SHALL additionally support `/live add <url>` where the platform argument is omitted. When `channel_id` is empty (only one argument provided), the system SHALL treat the `platform` parameter as a URL and attempt auto-detection:
- The system SHALL normalize the input with `.strip()` (C9).
- The system SHALL use `urllib.parse.urlparse` to extract the hostname, then match against `_HOST_PLATFORM_MAP` exact host allowlist (C1).
- Allowed hosts (C2): `youtube.com`, `www.youtube.com`, `m.youtube.com`, `twitch.tv`, `www.twitch.tv`, `m.twitch.tv`, `live.bilibili.com`.
- If a host matches, the full raw URL (not lowercased) SHALL be passed to the matched platform's `validate_channel` for extraction (C5).
- If no host matches and the input contains both `.` and `/` (URL heuristic), the system SHALL respond with `cmd.add.unrecognized_url`.
- If the input does not look like a URL and matches a valid platform name (case-insensitive), the system SHALL respond with `cmd.add.invalid_channel` (missing channel_id case).
- If the input does not look like a URL and does not match a valid platform name, the system SHALL respond with `cmd.add.invalid_platform`.

The `cmd_add` signature SHALL change to `async def cmd_add(self, event, platform: str, channel_id: str = "")`.

The auto-detect path SHALL NOT lowercase the raw URL before passing to `validate_channel`. The explicit path (when `channel_id` is non-empty) SHALL lowercase `platform` as before (C5).

#### Scenario: Successfully add a YouTube monitor
- **WHEN** user sends `/live add youtube UCxxxxx` in a group
- **THEN** the system SHALL validate the channel exists, add it to the group's monitor list, perform a single status check, and confirm with the channel name

#### Scenario: Successfully add with @handle
- **WHEN** user sends `/live add youtube @handle`
- **THEN** the system SHALL resolve the handle to a Channel ID, add the monitor, perform a single status check, and confirm

#### Scenario: Add duplicate monitor
- **WHEN** user adds a monitor that already exists in the current group
- **THEN** the system SHALL respond that the monitor already exists (idempotent, no state change)

#### Scenario: Add monitor exceeding per-group limit
- **WHEN** the current group has reached its max monitors limit (default 30)
- **THEN** the system SHALL reject the add operation with a "group limit reached" error

#### Scenario: Add monitor exceeding global limit
- **WHEN** adding would cause the global unique channel count to exceed 500
- **THEN** the system SHALL reject with a "global limit reached" error

#### Scenario: Add monitor with invalid platform
- **WHEN** user sends `/live add tiktok xxx`
- **THEN** the system SHALL respond with an error listing valid platforms

#### Scenario: Add monitor for already-live channel
- **WHEN** the channel being added is currently live
- **AND** the immediate status check succeeds (`success == True`)
- **THEN** the system SHALL record the current status as live with `initialized = True` but SHALL NOT send a live-start notification

#### Scenario: Add monitor when platform is rate-limited
- **WHEN** user sends `/live add <platform> <channel_id>`
- **AND** the platform returns a rate-limit response during channel validation
- **THEN** the system SHALL respond with the `error.rate_limited` message including the platform name
- **AND** the system SHALL NOT respond with "channel not found"

#### Scenario: Add monitor with immediate check failure
- **WHEN** user sends `/live add <platform> <channel_id>` and the channel is valid
- **AND** the immediate status check fails (network error, parse error, or `success == False`)
- **THEN** the system SHALL keep `last_status = "unknown"` and `initialized = False`
- **AND** the add operation SHALL succeed with a confirmation message
- **AND** the poller SHALL initialize the status on its next cycle

#### Scenario: Auto-detect YouTube from URL
- **WHEN** user sends `/live add https://www.youtube.com/@GawrGura`
- **THEN** the system SHALL detect `youtube` from the URL host via `_HOST_PLATFORM_MAP`
- **AND** pass the full raw URL to `YouTubeChecker.validate_channel`
- **AND** add the monitor on success

#### Scenario: Auto-detect YouTube from mobile URL
- **WHEN** user sends `/live add https://m.youtube.com/@GawrGura`
- **THEN** the system SHALL detect `youtube` from `m.youtube.com` host
- **AND** pass the full raw URL to `YouTubeChecker.validate_channel`

#### Scenario: Auto-detect Twitch from URL
- **WHEN** user sends `/live add https://www.twitch.tv/shroud`
- **THEN** the system SHALL detect `twitch` from the URL host via `_HOST_PLATFORM_MAP`
- **AND** pass the full raw URL to `TwitchChecker.validate_channel`
- **AND** add the monitor on success

#### Scenario: Auto-detect Bilibili from URL
- **WHEN** user sends `/live add https://live.bilibili.com/22637261`
- **THEN** the system SHALL detect `bilibili` from the URL host via `_HOST_PLATFORM_MAP`
- **AND** pass the full raw URL to `BilibiliChecker.validate_channel`
- **AND** add the monitor on success

#### Scenario: Unrecognized URL in auto-detect
- **WHEN** user sends `/live add https://unknown-site.com/foo`
- **THEN** the system SHALL respond with `cmd.add.unrecognized_url` listing supported URL formats

#### Scenario: Explicit platform with URL still works
- **WHEN** user sends `/live add youtube https://www.youtube.com/@GawrGura`
- **THEN** the system SHALL use `youtube` as the platform (explicit path)
- **AND** pass the URL to `YouTubeChecker.validate_channel`

#### Scenario: Backward compatibility with raw identifiers
- **WHEN** user sends `/live add bilibili 672328094`
- **THEN** the system SHALL use the existing explicit platform path
- **AND** behavior SHALL be identical to pre-change behavior

#### Scenario: Platform name without channel_id
- **WHEN** user sends `/live add youtube` (no channel_id)
- **AND** `"youtube"` is in `_VALID_PLATFORMS`
- **THEN** the system SHALL respond with `cmd.add.invalid_channel` (not unrecognized URL)

#### Scenario: Host-only URL without channel path
- **WHEN** user sends `/live add youtube.com/`
- **THEN** the system SHALL detect `youtube` from the host
- **AND** pass the URL to `YouTubeChecker.validate_channel`
- **AND** the checker regex SHALL NOT match (no valid path)
- **AND** the system SHALL respond with `cmd.add.invalid_channel` (C6)

#### Scenario: URL with uppercase scheme and host
- **WHEN** user sends `/live add HTTPS://WWW.YOUTUBE.COM/@GawrGura`
- **THEN** `_detect_platform` SHALL match via lowercased host
- **AND** the raw URL (preserving case) SHALL be passed to `validate_channel`
- **AND** the checker regex with `re.IGNORECASE` SHALL extract `@GawrGura`

#### Scenario: URL with query parameters
- **WHEN** user sends `/live add https://www.twitch.tv/shroud?tt_content=channel`
- **THEN** the system SHALL detect `twitch` and extract `shroud` from the first path segment
- **AND** the query string SHALL be ignored

#### Scenario: URL with trailing whitespace
- **WHEN** user sends `/live add  https://www.youtube.com/@GawrGura  ` (with spaces)
- **THEN** the system SHALL strip whitespace before processing (C9)
- **AND** auto-detection SHALL succeed normally
