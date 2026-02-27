## ADDED Requirements

### Requirement: Per-channel exponential backoff on failure
The system SHALL write to `_channel_failures` and `_channel_backoff_until` in `_process_results()` when a channel returns `success=False`, implementing exponential backoff with a maximum cap of 300 seconds.

#### Scenario: Channel fails once
- **WHEN** `_process_results()` processes a `StatusSnapshot` with `success=False` for channel `cid`
- **THEN** `_channel_failures[cid]` is incremented to 1
- **THEN** `_channel_backoff_until[cid]` is set to `time.time() + delay` where `delay = min(BASE * MULT^0, 300)`

#### Scenario: Channel fails consecutively (n times)
- **WHEN** channel `cid` has failed `n` consecutive times without success
- **THEN** `_channel_failures[cid] == n`
- **THEN** backoff delay is non-decreasing and capped at 300 seconds
- **THEN** the channel is excluded from the next poll cycle if `_channel_backoff_until[cid] > time.time()`

#### Scenario: Channel recovers after failures
- **WHEN** `_process_results()` processes a `StatusSnapshot` with `success=True` for channel `cid`
- **THEN** `_channel_failures.pop(cid, None)` clears the failure count
- **THEN** `_channel_backoff_until.pop(cid, None)` clears the backoff timer
- **THEN** the channel is included in the next poll cycle

#### Scenario: Channel backoff is independent per channel
- **WHEN** channel A fails and channel B succeeds in the same `_process_results()` call
- **THEN** `_channel_failures[A]` is incremented and `_channel_backoff_until[A]` is set
- **THEN** `_channel_failures` and `_channel_backoff_until` for B are cleared (or absent)
- **THEN** no cross-channel mutation occurs
