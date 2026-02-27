## ADDED Requirements

### Requirement: Bilibili HTTP 429 propagated as RateLimitError
The system SHALL raise `RateLimitError("bilibili")` in `_resolve_room_id()` and `_validate_uid()` when the Bilibili API returns HTTP 429, before the generic exception handler swallows it.

#### Scenario: 429 in _resolve_room_id
- **WHEN** `session.get(...)` returns a response with `status == 429`
- **THEN** `RateLimitError("bilibili")` is raised immediately
- **THEN** the caller's `except RateLimitError: raise` re-propagates it to the poller
- **THEN** the poller triggers platform-level backoff

#### Scenario: 429 in _validate_uid
- **WHEN** `session.post(...)` returns a response with `status == 429`
- **THEN** `RateLimitError("bilibili")` is raised immediately
- **THEN** it propagates past the generic `except Exception` handler
- **THEN** `cmd_add` receives `RateLimitError` and returns a rate-limit error message to the user

#### Scenario: Non-429 HTTP error in _resolve_room_id or _validate_uid
- **WHEN** a non-429 HTTP error status causes `raise_for_status()` to raise
- **THEN** the generic `except Exception` handler catches it
- **THEN** the function returns `None` (existing behavior preserved)

#### Scenario: Successful response
- **WHEN** API returns `status == 200` with valid payload
- **THEN** parsed value is returned unchanged (no behavioral regression)
