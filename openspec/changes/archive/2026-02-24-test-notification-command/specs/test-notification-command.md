# Spec: test-notification-command

## Requirement: `/live test_notify <delay>` command

The system SHALL register sub-command `test_notify` under the `live` command group. It accepts a single required parameter `delay` (integer, seconds).

### Scenario: Valid delay triggers delayed test notifications

- **GIVEN** the plugin is initialized and `self._notifier` is available
- **WHEN** a user invokes `/live test_notify 10`
- **THEN** the system SHALL immediately yield a confirmation message containing the delay value
- **AND** spawn a background `asyncio.Task` that:
  1. Sleeps for `delay` seconds
  2. Calls `Notifier.send_live_notification(origin, "test", snapshot, global_enable=True, force=True)` with synthetic `StatusSnapshot`
  3. Calls `Notifier.send_end_notification(origin, "test", "Test Streamer", global_enable=True, global_end_enable=True, force=True)`

### Scenario: Missing or invalid delay

- **WHEN** delay is missing, non-integer, or <= 0
- **THEN** yield `cmd.test_notify.invalid_delay` error message
- **AND** no task is scheduled

### Scenario: Delay exceeds 300 seconds

- **WHEN** delay > 300
- **THEN** yield `cmd.test_notify.delay_too_long` error message with `{max}` = 300

### Scenario: Plugin not initialized

- **WHEN** `self._notifier` is `None`
- **THEN** yield `cmd.test_notify.not_ready` error message

## Requirement: `force` parameter on Notifier send methods

`send_live_notification()` and `send_end_notification()` SHALL accept keyword-only `force: bool = False`. When `force=True`, `_should_notify()` is skipped entirely.

### Scenario: force=True bypasses all gate checks

- **WHEN** `force=True`
- **THEN** notification is sent regardless of `global_enable`, `group.notify_enabled`, `group.end_notify_enabled`, or failure count

### Scenario: force=False preserves existing behavior

- **WHEN** `force=False` (default)
- **THEN** behavior is identical to current implementation (no regression)

## Requirement: `track_failure` parameter on `_send_chain`

`_send_chain()` SHALL accept keyword-only `track_failure: bool = True`. When `False`, `increment_failure()` and `reset_failure()` are not called.

### Scenario: Test notification failure does not pollute counter

- **WHEN** a test notification is sent with `force=True`
- **AND** `_send_chain` is called with `track_failure=False`
- **AND** the send fails
- **THEN** `send_failure_count` for the origin SHALL remain unchanged

## Requirement: Background task lifecycle

Background tasks spawned by `test_notify` SHALL be tracked in `self._bg_tasks: set[asyncio.Task]`. On `terminate()`, all tasks are cancelled and awaited.

### Scenario: Plugin terminates during delay

- **WHEN** `terminate()` is called while a test_notify task is sleeping
- **THEN** the task SHALL be cancelled
- **AND** no notification is sent
- **AND** no unhandled exception is raised

## Requirement: i18n keys

New keys SHALL be added to all three language files (`en.json`, `zh-Hans.json`, `zh-Hant.json`):

| Key | Purpose |
|-----|---------|
| `cmd.test_notify.scheduled` | Confirmation: "Test notification will be sent in {delay} seconds." |
| `cmd.test_notify.invalid_delay` | Error: invalid/missing delay value |
| `cmd.test_notify.delay_too_long` | Error: delay > max, with `{max}` placeholder |
| `cmd.test_notify.not_ready` | Error: plugin not initialized |

## PBT Properties

### Property: force=False is backward-compatible

**Invariant**: For any call to `send_live_notification` or `send_end_notification` without `force` parameter, behavior is identical to the pre-change version.
**Falsification**: Call both methods with all combinations of `global_enable`, `notify_enabled`, `end_notify_enabled` — output must match original `_should_notify` logic.

### Property: force=True always delivers

**Invariant**: When `force=True`, the notification dispatch code is always reached regardless of gate state.
**Falsification**: Set `global_enable=False`, `notify_enabled=False`, `end_notify_enabled=False`, `send_failure_count=100` — notification must still be attempted.

### Property: track_failure=False preserves counter

**Invariant**: `send_failure_count` before and after a `_send_chain(track_failure=False)` call are equal, regardless of send success/failure.
**Falsification**: Record counter, send with `track_failure=False` (mock send to fail), assert counter unchanged.

### Property: Delay bounds

**Invariant**: `cmd_test_notify` only schedules a task when `0 < delay <= 300`.
**Falsification**: Test with delay values `{-1, 0, 1, 300, 301, "abc", ""}` — only `1` and `300` should schedule.

### Property: Background task cleanup

**Invariant**: After `terminate()`, `self._bg_tasks` is empty and all tasks are done or cancelled.
**Falsification**: Schedule a test_notify with delay=9999, call terminate(), assert task is cancelled and set is empty.
