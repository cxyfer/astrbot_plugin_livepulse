## MODIFIED Requirements

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

## ADDED Requirements

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
