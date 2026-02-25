## MODIFIED Requirements

### Requirement: /live add command
The system SHALL provide `/live add` to add monitors to the current group. The command SHALL support two input modes, determined by the first non-command argument:

**Platform+ID mode**: `/live add <platform> <id1> [id2] [id3] ...`
- First arg matches a valid platform name (case-insensitive) → remaining args are channel IDs for that platform.
- All IDs validated concurrently against the same platform checker.

**URL mode**: `/live add <url1> [url2] [url3] ...`
- First arg matches a URL pattern → all args are URLs, each auto-detected to its platform independently via `_HOST_PLATFORM_MAP`.
- Mixed platforms within URL mode are allowed (each URL resolves independently).

**Batch preprocessing**: Before validation, the system SHALL apply silent dedup (preserve insertion order, retain first occurrence) and truncation at `MAX_BATCH_SIZE` (20).

**Mode exclusivity**: If mode is platform+ID but any subsequent arg looks like a URL (or vice versa), the system SHALL reject the entire command with `cmd.batch.mixed_mode` and perform zero mutations.

**Validation**: All channels SHALL be validated concurrently via `asyncio.gather(return_exceptions=True)` with `asyncio.Semaphore(5)`. Per-channel failures are captured without aborting the batch.

**Store mutation**: After validation, the system SHALL call `Store.add_monitors_batch()` which acquires the lock once, applies incremental limit checks per channel, persists once, and releases the lock.

**No immediate status check**: The system SHALL NOT perform `check_status` after batch add (including N=1). Newly added channels SHALL have `last_status = "unknown"` and `initialized = False` until the poller processes them.

**Response**: A single aggregated message using the batch response format (summary line + per-channel result lines).

The `cmd_add` signature SHALL remain `async def cmd_add(self, event, platform: str, channel_id: str = "")`. Batch args SHALL be parsed from `event.message_str`.

The auto-detect path SHALL NOT lowercase the raw URL before passing to `validate_channel`. The explicit path (when platform is provided) SHALL lowercase `platform` as before.

#### Scenario: Single channel add (backward compatible syntax)
- **WHEN** user sends `/live add youtube UCxxxxx`
- **THEN** the system SHALL process it through the batch path (N=1)
- **AND** respond with the unified batch summary format

#### Scenario: Batch add with explicit platform
- **WHEN** user sends `/live add twitch wpnebula imcyv scottybvb`
- **THEN** the system SHALL parse `twitch` as platform and `[wpnebula, imcyv, scottybvb]` as IDs from `event.message_str`
- **AND** validate all 3 concurrently
- **AND** respond with one summary message containing 3 result lines

#### Scenario: Batch add with URLs
- **WHEN** user sends `/live add https://twitch.tv/a https://youtube.com/@b`
- **THEN** the system SHALL detect URL mode
- **AND** auto-detect each URL's platform independently
- **AND** respond with one summary message

#### Scenario: Single URL add
- **WHEN** user sends `/live add https://twitch.tv/shroud`
- **THEN** the system SHALL detect URL mode (N=1) and process through batch path

#### Scenario: Mixed mode rejection
- **WHEN** user sends `/live add twitch wpnebula https://youtube.com/@b`
- **THEN** the system SHALL reject with `cmd.batch.mixed_mode`
- **AND** zero store mutations SHALL occur

#### Scenario: Partial failure in batch
- **WHEN** user sends `/live add twitch a b c` and channel `b` is invalid
- **THEN** channels `a` and `c` SHALL succeed
- **AND** channel `b` SHALL report failure in the summary

#### Scenario: Limit reached mid-batch
- **WHEN** group limit is 30, current count is 29, and user batch-adds `[a, b, c]`
- **THEN** `a` SHALL succeed (count=30)
- **AND** `b` and `c` SHALL report `cmd.add.limit_group`

#### Scenario: Duplicate within batch input
- **WHEN** user sends `/live add twitch a a b`
- **THEN** the system SHALL silently deduplicate to `[a, b]`

#### Scenario: Truncation at MAX_BATCH_SIZE
- **WHEN** user sends `/live add twitch` followed by 25 unique IDs
- **THEN** only the first 20 SHALL be processed
- **AND** the response SHALL include a truncation notice

#### Scenario: Auto-detect YouTube from URL (preserved)
- **WHEN** user sends `/live add https://www.youtube.com/@GawrGura`
- **THEN** the system SHALL detect `youtube` from the URL host via `_HOST_PLATFORM_MAP`
- **AND** pass the full raw URL to `YouTubeChecker.validate_channel`

#### Scenario: Auto-detect Bilibili from URL (preserved)
- **WHEN** user sends `/live add https://live.bilibili.com/22637261`
- **THEN** the system SHALL detect `bilibili` from the URL host
- **AND** pass the full raw URL to `BilibiliChecker.validate_channel`

#### Scenario: Unrecognized URL (preserved)
- **WHEN** user sends `/live add https://unknown-site.com/foo`
- **THEN** the system SHALL respond with `cmd.add.unrecognized_url`

#### Scenario: Add monitor with invalid platform (preserved)
- **WHEN** user sends `/live add tiktok xxx`
- **THEN** the system SHALL respond with `cmd.add.invalid_platform`

#### Scenario: Rate limit error during batch validation
- **WHEN** `validate_channel` raises `RateLimitError` for one channel in a batch
- **THEN** that channel's result SHALL show `rate_limited` status
- **AND** other channels SHALL proceed normally

### Requirement: /live remove command
The system SHALL provide `/live remove` to remove monitors from the current group. The command SHALL support two input modes, with the same detection logic as `/live add`:

**Platform+ID mode**: `/live remove <platform> <id1> [id2] [id3] ...`
- First arg matches a valid platform name → remaining args are channel IDs or display_ids for that platform.
- Remove is local-only for platform+ID mode (no network needed), processed sequentially under lock.

**URL mode**: `/live remove <url1> [url2] [url3] ...`
- All args are URLs. Platform auto-detected per URL.
- URL resolution MAY require network calls (e.g., Bilibili room_id → uid).
- URL resolution uses concurrent validation with `asyncio.Semaphore(5)`.

**Batch preprocessing**: Same as add — silent dedup, truncation at MAX_BATCH_SIZE (20).

**Mode exclusivity**: Same as add — mixed modes rejected with `cmd.batch.mixed_mode`.

**Store mutation**: After resolution, the system SHALL call `Store.remove_monitors_batch()` which acquires the lock once, removes sequentially, persists once, and releases the lock.

**Display_id matching**: When `<identifier>` does not match any `channel_id` directly, the system SHALL look up the corresponding `channel_id` via `display_id` matching within the group's monitors for the given platform.

**Response**: A single aggregated message using the batch response format.

#### Scenario: Single channel remove (backward compatible syntax)
- **WHEN** user sends `/live remove youtube UCxxxxx`
- **THEN** the system SHALL process through batch path (N=1) and respond with unified format

#### Scenario: Batch remove with explicit platform
- **WHEN** user sends `/live remove twitch wpnebula imcyv scottybvb`
- **THEN** the system SHALL remove all 3 from the group under one lock acquisition
- **AND** respond with one summary message

#### Scenario: Batch remove with URLs
- **WHEN** user sends `/live remove https://twitch.tv/a https://youtube.com/@b`
- **THEN** the system SHALL resolve each URL to platform+channel_id
- **AND** remove both and respond with one summary

#### Scenario: Batch remove with mixed results
- **WHEN** user sends `/live remove twitch a b c` and only `a` and `c` exist
- **THEN** `a` and `c` SHALL be removed
- **AND** `b` SHALL report not found in the summary

#### Scenario: Remove by @handle (preserved)
- **WHEN** user sends `/live remove youtube @handle` and a monitor with `display_id == "@handle"` exists
- **THEN** the system SHALL resolve to `channel_id` and remove it

#### Scenario: Remove non-existent monitor (preserved)
- **WHEN** user sends `/live remove youtube UCxxxxx` and no monitor matches
- **THEN** the system SHALL report not found (no error, no state change)

#### Scenario: Bilibili URL remove requires network
- **WHEN** user sends `/live remove https://live.bilibili.com/22637261`
- **THEN** the system SHALL resolve the room_id to uid via network call
- **AND** remove the monitor matching the resolved uid
