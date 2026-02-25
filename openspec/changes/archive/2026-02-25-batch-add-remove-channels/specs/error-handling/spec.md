## ADDED Requirements

### Requirement: Fine-grained batch validation error classification
The system SHALL classify batch validation errors into distinct categories. Each platform's `validate_channel` SHALL surface errors with enough semantic information for the batch processor to map them to the correct per-channel result status.

The error categories SHALL be:
- `success`: validation passed, `ChannelInfo` returned.
- `not_found`: channel does not exist on the platform (`validate_channel` returns `None`).
- `rate_limited`: platform returned a rate-limit response (`RateLimitError` raised).
- `invalid_format`: the identifier/URL format is invalid before network call (e.g., URL regex mismatch).
- `internal_error`: unexpected exception during validation (network timeout, parse error, etc.).

#### Scenario: Twitch validation error surfaces correctly
- **WHEN** `TwitchChecker.validate_channel` encounters an HTTP error during batch validation
- **THEN** the error SHALL propagate as an `Exception` (not silently return `None`)
- **AND** the batch processor SHALL classify it as `internal_error`

#### Scenario: Bilibili validation error surfaces correctly
- **WHEN** `BilibiliChecker.validate_channel` encounters HTTP 429
- **THEN** it SHALL raise `RateLimitError(platform="bilibili")`
- **AND** the batch processor SHALL classify it as `rate_limited`

#### Scenario: YouTube validation error surfaces correctly
- **WHEN** `YouTubeChecker.validate_channel` detects a block page
- **THEN** it SHALL raise `RateLimitError(platform="youtube")`
- **AND** the batch processor SHALL classify it as `rate_limited`

#### Scenario: validate_channel returns None classified as not_found
- **WHEN** `validate_channel` returns `None` for a channel
- **THEN** the batch processor SHALL classify it as `not_found`

#### Scenario: Unexpected exception classified as internal_error
- **WHEN** `validate_channel` raises an exception that is not `RateLimitError`
- **THEN** the batch processor SHALL classify it as `internal_error`
- **AND** the exception SHALL be logged at WARNING level

### Requirement: Batch error classification does not alter existing single-channel error behavior
The fine-grained error classification SHALL be implemented in the batch processing layer only. Existing `validate_channel` implementations SHALL NOT change their return type or exception semantics beyond ensuring `RateLimitError` is raised (not swallowed) for rate-limit conditions.

#### Scenario: Existing single-channel error paths preserved
- **WHEN** a platform's `validate_channel` is called outside the batch context
- **THEN** its return type and exception behavior SHALL remain unchanged from pre-batch behavior

#### Scenario: RateLimitError already raised by YouTube and Bilibili
- **WHEN** YouTube or Bilibili encounters rate limiting
- **THEN** they SHALL continue to raise `RateLimitError` as they do today

#### Scenario: Twitch validate_channel exception handling audit
- **WHEN** `TwitchChecker.validate_channel` encounters a non-404 HTTP error
- **THEN** it SHALL NOT silently return `None`
- **AND** it SHALL let the exception propagate so the batch processor can classify it
