## ADDED Requirements

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
- **WHEN** YouTube returns a block page or CAPTCHA instead of channel content
- **THEN** the system SHALL apply exponential backoff for YouTube polling

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
