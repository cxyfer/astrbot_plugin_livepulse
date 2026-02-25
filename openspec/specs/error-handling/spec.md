# error-handling Specification

## Purpose
TBD - created by archiving change livepulse-plugin. Update Purpose after archive.
## Requirements
### Requirement: Per-channel error isolation
A single channel's API error SHALL NOT interrupt the checking of other channels within the same polling cycle.

#### Scenario: One channel fails, others succeed
- **WHEN** YouTube poller checks 5 channels and 1 returns a network error
- **THEN** the remaining 4 channels SHALL still be checked and report status normally

### Requirement: Network timeout handling
Each platform SHALL use its configured HTTP timeout (YouTube: 20s, Twitch: 10s, Bilibili: 10s by default). Timeout errors SHALL be handled gracefully.

#### Scenario: Request times out
- **WHEN** an HTTP request exceeds the configured timeout
- **THEN** the system SHALL cancel the request, log the timeout, and treat the channel as `unknown` status

### Requirement: Rate limit detection with dynamic backoff
The system SHALL detect rate limiting (HTTP 429 or platform-specific signals) and apply dynamic backoff.

#### Scenario: Bilibili 429 response
- **WHEN** the Bilibili API returns HTTP 429
- **THEN** the system SHALL increase the polling interval for Bilibili using exponential backoff (base=30s, multiplier=2, max=300s, jitter=+-10%)

#### Scenario: YouTube page block detection
- **WHEN** YouTube returns a page containing the phrase "unusual traffic" (case-insensitive)
- **THEN** the system SHALL treat the response as a block page and raise `RateLimitError`
- **AND** the system SHALL apply exponential backoff for YouTube polling

#### Scenario: YouTube normal page with reCAPTCHA assets
- **WHEN** YouTube returns a normal page containing standard reCAPTCHA assets (e.g., `RECAPTCHA_V3_SITEKEY`, `.grecaptcha-badge`)
- **AND** the page does NOT contain the phrase "unusual traffic"
- **THEN** the system SHALL NOT treat the response as a block page
- **AND** `_is_blocked()` SHALL return `False`

#### Scenario: Twitch 429 response
- **WHEN** the Twitch API returns HTTP 429
- **THEN** the system SHALL apply exponential backoff for Twitch polling

#### Scenario: Backoff recovery
- **WHEN** a platform's request succeeds after a backoff period
- **THEN** the system SHALL gradually reduce the backoff delay toward the configured base interval

### Requirement: Exponential backoff on consecutive per-channel errors
The system SHALL track consecutive errors per channel and apply per-channel exponential backoff with parameters: base=30s, multiplier=2, max=300s, jitter=+-10%.

#### Scenario: Channel error backoff
- **WHEN** a channel fails 3 consecutive times
- **THEN** the system SHALL delay checking that channel by min(30 * 2^2, 300) = 120s (plus jitter)

#### Scenario: Channel error recovery
- **WHEN** a channel succeeds after consecutive failures
- **THEN** the per-channel error counter SHALL reset to 0 and normal polling resumes

### Requirement: Resource cleanup on terminate
The system SHALL properly clean up all resources when the plugin is terminated or reloaded: cancel all asyncio tasks, close the shared aiohttp ClientSession, and flush any pending persistence writes.

#### Scenario: Plugin terminate cleanup
- **WHEN** AstrBot calls the plugin's `terminate()` method
- **THEN** all poller tasks SHALL be cancelled and awaited
- **AND** the aiohttp ClientSession SHALL be closed
- **AND** any pending state changes SHALL be persisted to disk

#### Scenario: Idempotent terminate
- **WHEN** `terminate()` is called multiple times
- **THEN** the system SHALL handle it gracefully without errors

### Requirement: Twitch OAuth token lifecycle
The system SHALL manage Twitch OAuth token lifecycle: obtain token via Client Credentials flow, refresh when `now >= expires_at - 300s`, and handle 401 errors by refreshing and retrying once.

#### Scenario: Token auto-refresh before expiry
- **WHEN** the current time is within 300 seconds of token expiry
- **THEN** the system SHALL refresh the token before the next API call

#### Scenario: Token refresh on 401
- **WHEN** the Twitch API returns 401 Unauthorized
- **THEN** the system SHALL refresh the token and retry the request once
- **AND** if the retry also fails, the system SHALL treat affected channels as `unknown` (NOT offline)

#### Scenario: Token refresh failure
- **WHEN** the token refresh request itself fails
- **THEN** the system SHALL apply exponential backoff on Twitch polling
- **AND** SHALL NOT mark any channels as offline due to auth failure

### Requirement: RateLimitError MUST surface as distinct user-facing message
When a command handler catches `RateLimitError`, the system SHALL display a dedicated rate-limit error message using the `error.rate_limited` i18n key with the platform name from `RateLimitError.platform`. The system SHALL NOT mask `RateLimitError` as a generic error or "channel not found".

#### Scenario: RateLimitError in /live add yields dedicated message
- **WHEN** a user runs `/live add youtube @handle`
- **AND** `validate_channel` raises `RateLimitError(platform="youtube")`
- **THEN** the system SHALL respond with the `error.rate_limited` i18n string with `{platform}` set to `"youtube"`
- **AND** the system SHALL NOT respond with `cmd.add.invalid_channel`

#### Scenario: Non-RateLimitError in /live add preserves existing behavior
- **WHEN** a user runs `/live add bilibili 99999`
- **AND** `validate_channel` raises a generic `Exception` (e.g., network timeout)
- **THEN** the system SHALL respond with `cmd.add.invalid_channel`
- **AND** the system SHALL NOT use `error.rate_limited`

#### Scenario: error.rate_limited i18n key exists in all locales
- **WHEN** the i18n system looks up `error.rate_limited`
- **THEN** the key SHALL exist in `en.json`, `zh-Hans.json`, and `zh-Hant.json`
- **AND** each translation SHALL include a `{platform}` placeholder

### Requirement: Unrecognized URL error message
When the auto-detect path receives a URL that does not match any supported platform pattern in `_HOST_PLATFORM_MAP`, the system SHALL respond with a dedicated error message using the `cmd.add.unrecognized_url` i18n key. The message SHALL list the supported URL domains.

This error is ONLY triggered when:
1. `channel_id` is empty (single-arg mode)
2. `_detect_platform` returns `None` (host not in allowlist)
3. The input contains both `.` and `/` (URL heuristic)

If the host IS in the allowlist but the checker's URL regex does not match (e.g., `youtube.com/` with no channel path), the error SHALL be `cmd.add.invalid_channel` instead (C6).

#### Scenario: Unrecognized URL shows supported formats
- **WHEN** user sends `/live add https://unknown-site.com/foo`
- **THEN** the system SHALL respond with `cmd.add.unrecognized_url`
- **AND** the message SHALL mention `youtube.com`, `twitch.tv`, and `live.bilibili.com`

#### Scenario: i18n key exists in all locales
- **WHEN** the i18n system looks up `cmd.add.unrecognized_url`
- **THEN** the key SHALL exist in `en.json`, `zh-Hans.json`, and `zh-Hant.json`
- **AND** all three locale messages SHALL have identical placeholder sets (no format string mismatch)

#### Scenario: Non-URL invalid input uses existing error
- **WHEN** user sends `/live add tiktok someuser` (invalid platform, not a URL)
- **THEN** the system SHALL respond with `cmd.add.invalid_platform` (NOT `cmd.add.unrecognized_url`)

#### Scenario: Valid host but invalid path uses invalid_channel
- **WHEN** user sends `/live add youtube.com/` (valid host, no channel path)
- **THEN** the system SHALL respond with `cmd.add.invalid_channel` (NOT `cmd.add.unrecognized_url`) (C6)

#### Scenario: Platform name without channel_id uses invalid_channel
- **WHEN** user sends `/live add youtube` (valid platform name, no channel_id)
- **THEN** the system SHALL respond with `cmd.add.invalid_channel` (NOT `cmd.add.unrecognized_url`)

