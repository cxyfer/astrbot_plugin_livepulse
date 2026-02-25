# Proposal: Batch Add/Remove Channels

## Context

Currently `/live add` and `/live remove` only accept a single channel per invocation. Users managing multiple streamers must repeat the command for each channel, which is tedious.

**User need**: Support adding or removing multiple channels in one command.

```
/live add twitch wpnebula imcyv scottybvb
/live remove twitch wpnebula imcyv scottybvb
/live add https://twitch.tv/a https://youtube.com/@b https://live.bilibili.com/123
/live remove https://twitch.tv/a https://youtube.com/@b
```

## Design Decisions (User-Confirmed)

- **No mixing**: A single command is either all platform+ID or all URLs. No mixing allowed.
- **No batch limit**: Rely on existing group/global limits only.
- **Unified response format**: Even single-channel operations use the new summary format (breaking change to output format, not to command syntax).

## Constraints

### Hard Constraints (Technical)

1. **AstrBot command framework**: `cmd_add(self, event, platform, channel_id="")` only accepts 2 positional args. Batch args must be parsed from `event.message_str`.
2. **Store lock**: All mutations require `asyncio.Lock`. Batch should acquire lock once, not per-channel.
3. **Network validation**: Each channel requires async network call (`validate_channel`). Batch should validate concurrently via `asyncio.gather` for performance.
4. **Per-channel error isolation**: One invalid channel must not block others. Best-effort processing with per-channel result reporting.
5. **Limit checks**: Group and global limits must be checked incrementally as channels are added within the batch.
6. **Mode exclusivity**: First arg determines mode — if it's a valid platform name → platform+ID mode; if it looks like a URL → URL mode. Cannot mix.

### Soft Constraints (Conventions)

7. **i18n**: New keys needed for batch summary. All 3 locale files (en, zh-Hans, zh-Hant) must be updated.
8. **Response format**: Single aggregated message with per-channel status lines (success/duplicate/error).
9. **Immediate status check**: After batch add, check all newly added channels in one call (checkers already support `check_status([list])` batch API).

## Requirements

### R1: Batch Add — Explicit Platform

**Scenario**: `/live add twitch wpnebula imcyv scottybvb`

- First arg is a valid platform name, remaining args are channel IDs.
- All channels validated concurrently against the same platform checker.
- Store mutations applied sequentially under one lock acquisition.
- Response: single message listing each channel's result.

### R2: Batch Add — URL Mode

**Scenario**: `/live add https://twitch.tv/a https://youtube.com/@b`

- All args are URLs. Platform auto-detected per URL.
- Mixed platforms allowed within URL mode (each URL resolves independently).
- Same concurrent validation + sequential store mutation pattern.

### R3: Batch Remove — Explicit Platform

**Scenario**: `/live remove twitch wpnebula imcyv scottybvb`

- First arg is a valid platform name, remaining args are channel IDs.
- Remove is local-only (no network needed), processed sequentially under lock.

### R4: Batch Remove — URL Mode

**Scenario**: `/live remove https://twitch.tv/a https://youtube.com/@b`

- URLs resolved to platform + channel_id (local extraction first, network fallback).
- Mixed platforms allowed within URL mode.

### R5: Backward Compatibility

- Command syntax fully backward compatible — existing single-channel commands still work.
- Output format changes: single-channel now uses the same summary format as batch (unified).

## Success Criteria

1. `/live add twitch a b c` adds 3 channels, returns one summary message with 3 result lines.
2. `/live add <url1> <url2>` with mixed-platform URLs adds both, returns summary.
3. `/live remove twitch a b c` removes 3 channels, returns one summary message.
4. `/live add twitch a` (single channel) returns summary format (not old format).
5. If channel B is invalid in `/live add twitch a b c`, channels A and C still succeed.
6. Group/global limits respected: if limit is reached mid-batch, remaining channels report limit error.
7. `/live add twitch a https://youtube.com/@b` is rejected (mixing modes not allowed).
