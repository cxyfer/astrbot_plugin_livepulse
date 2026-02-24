# test-notification-command

## Context

LivePulse supports Discord Embed and plain text notifications for live-start and live-end events. Currently there is no way to preview how these notifications render on a given platform without waiting for an actual stream state change. A test command allows users to verify notification display (especially Discord Embed formatting) on demand.

The existing notification infrastructure in `core/notifier.py` already handles platform detection (`_is_discord_origin`), embed building (`_build_live_embed`, `_build_end_embed`), and plain text fallback. The test command needs to reuse this dispatch logic with synthetic data.

Commands follow the `@filter.command_group("live")` / `@live.command()` pattern in `main.py`. All commands are async generators yielding `event.plain_result()`. Delayed execution uses `asyncio.sleep()`.

## Requirements

### Requirement: `/live test_notify` command with delay

The system SHALL register a new sub-command `test_notify` under the `live` command group. It accepts a single required parameter `delay` (integer, seconds).

#### Scenario: Valid delay triggers delayed test notifications

- **WHEN** a user invokes `/live test_notify <delay>` with a positive integer
- **THEN** the system SHALL immediately reply with a confirmation message indicating the delay
- **AND** after `delay` seconds, SHALL send a simulated live-start notification to the current origin
- **AND** immediately after, SHALL send a simulated live-end notification to the current origin

#### Scenario: Invalid or missing delay

- **WHEN** a user invokes `/live test_notify` without a delay or with a non-positive / non-integer value
- **THEN** the system SHALL reply with a usage hint and NOT schedule any notification

#### Scenario: Delay upper bound

- **WHEN** the delay exceeds 300 seconds
- **THEN** the system SHALL reject the command with an error message (prevent abuse / forgotten timers)

### Requirement: Reuse existing notification dispatch

The test command SHALL invoke `Notifier.send_live_notification()` and `Notifier.send_end_notification()` with a synthetic `StatusSnapshot` containing hardcoded test data. This ensures the test exercises the exact same code path as real notifications, including Discord Embed rendering and plain text fallback.

#### Scenario: Discord target

- **WHEN** the origin belongs to a Discord adapter
- **AND** `DiscordEmbed` is available
- **THEN** the test notifications SHALL render as Discord Embeds identical in structure to real notifications

#### Scenario: Non-Discord target

- **WHEN** the origin does NOT belong to a Discord adapter
- **THEN** the test notifications SHALL render as plain text + optional thumbnail, identical to real notifications

### Requirement: Bypass notification gate checks

Real notifications pass through `_should_notify()` which checks global enable, group enable, and failure count. The test command SHALL bypass these checks — test notifications must always be delivered regardless of notification settings.

#### Scenario: Notifications disabled but test still works

- **WHEN** group notifications are disabled (`notify_enabled = False`)
- **THEN** `/live test_notify` SHALL still deliver the test notifications

### Requirement: i18n keys for test command

New i18n keys SHALL be added to all three language files for:
- Confirmation message (with delay placeholder)
- Usage/error messages
- Test notification content labels (to distinguish from real notifications)

### Requirement: Hardcoded synthetic test data

The `StatusSnapshot` used for test notifications SHALL contain:
- `is_live`: `True`
- `streamer_name`: `"Test Streamer"`
- `title`: `"Test Stream Title"`
- `category`: `"Just Chatting"`
- `stream_url`: `"https://example.com/test"`
- `thumbnail_url`: `""` (empty — no external fetch)
- `platform`: `"test"`

## Constraints

| Type | Constraint |
|------|-----------|
| Hard | Must reuse `Notifier.send_live_notification()` and `send_end_notification()` — no duplicate embed/text building |
| Hard | `_should_notify()` gate must be bypassed for test; cannot modify its signature for production callers |
| Hard | `asyncio.sleep()` for delay — no new scheduler dependency |
| Hard | Delay capped at 300s to prevent abuse |
| Hard | Command is async generator yielding `event.plain_result()` — matches existing pattern |
| Soft | Synthetic data is hardcoded — no user-customizable fields |
| Soft | No permission restriction — any user can trigger (consistent with other `/live` commands) |
| Soft | `thumbnail_url` empty to avoid external HTTP requests during test |

## Success Criteria

1. `/live test_notify 10` immediately replies with confirmation, then sends live-start and live-end notifications after 10 seconds
2. Discord targets receive Embed notifications; non-Discord targets receive plain text — identical to real notifications
3. Test works even when group notifications are disabled
4. Invalid input (missing delay, non-integer, negative, >300) returns clear error messages
5. All three i18n files contain the new keys
6. No new dependencies introduced
