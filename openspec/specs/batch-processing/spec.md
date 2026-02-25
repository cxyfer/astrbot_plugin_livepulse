# batch-processing Specification

## Purpose
TBD - created by archiving change batch-add-remove-channels. Update Purpose after archive.
## Requirements
### Requirement: Batch input preprocessing
The system SHALL preprocess batch channel inputs before validation by applying, in order:
1. **Silent dedup**: preserve insertion order, retain only the first occurrence of each identifier.
2. **Truncation**: if unique inputs exceed `MAX_BATCH_SIZE` (20), process only the first 20 and append a truncation notice to the response.

#### Scenario: Dedup within batch
- **WHEN** user sends `/live add twitch a a b`
- **THEN** the system SHALL deduplicate to `[a, b]` silently
- **AND** only 2 validation requests SHALL be issued

#### Scenario: Truncation at MAX_BATCH_SIZE
- **WHEN** user sends `/live add twitch` followed by 25 unique channel IDs
- **THEN** the system SHALL process only the first 20
- **AND** the response SHALL include a truncation notice via `cmd.batch.truncated` i18n key

#### Scenario: Dedup applied before truncation
- **WHEN** user sends 30 args containing 10 duplicates (20 unique)
- **THEN** dedup SHALL reduce to 20 unique inputs
- **AND** no truncation notice SHALL appear (20 = MAX_BATCH_SIZE)

#### Scenario: Single channel is batch N=1
- **WHEN** user sends `/live add twitch wpnebula` (single channel)
- **THEN** the system SHALL process it through the same batch path as multi-channel inputs

### Requirement: Batch mode detection and exclusivity
The system SHALL determine the batch mode from the first non-command argument:
- If the first arg matches a valid platform name (case-insensitive) → **platform+ID mode**: remaining args are channel IDs for that platform.
- If the first arg matches a URL pattern (contains both `.` and `/`, or matches `_HOST_PLATFORM_MAP`) → **URL mode**: all args are URLs, each auto-detected independently.
- Mixing modes SHALL be rejected: if mode is platform+ID but any subsequent arg looks like a URL (or vice versa), the system SHALL reject the entire command with `cmd.batch.mixed_mode` error and perform zero mutations.

#### Scenario: Platform+ID mode detection
- **WHEN** user sends `/live add twitch wpnebula imcyv scottybvb`
- **THEN** the system SHALL detect platform+ID mode with platform=twitch and IDs=[wpnebula, imcyv, scottybvb]

#### Scenario: URL mode detection
- **WHEN** user sends `/live add https://twitch.tv/a https://youtube.com/@b`
- **THEN** the system SHALL detect URL mode with each URL auto-detected to its platform independently

#### Scenario: Mixed mode rejection
- **WHEN** user sends `/live add twitch wpnebula https://youtube.com/@b`
- **THEN** the system SHALL reject the entire command with `cmd.batch.mixed_mode`
- **AND** zero store mutations SHALL occur

#### Scenario: Single URL is URL mode N=1
- **WHEN** user sends `/live add https://twitch.tv/shroud`
- **THEN** the system SHALL detect URL mode and process through the batch path

### Requirement: Concurrent validation with bounded parallelism
The system SHALL validate batch channels concurrently using `asyncio.gather(return_exceptions=True)` with an `asyncio.Semaphore(5)` to bound peak parallelism. Each validation failure SHALL be captured per-channel without aborting the batch.

#### Scenario: Concurrent validation respects semaphore
- **WHEN** a batch of 15 channels is submitted
- **THEN** at most 5 `validate_channel` calls SHALL execute concurrently at any point in time

#### Scenario: Validation failure does not abort batch
- **WHEN** channel B fails validation in batch `[A, B, C]`
- **THEN** channels A and C SHALL still be validated and processed

#### Scenario: Rate limit error captured per-channel
- **WHEN** `validate_channel` raises `RateLimitError` for channel B
- **THEN** channel B's result SHALL have status `rate_limited`
- **AND** channels A and C SHALL proceed normally

### Requirement: Store batch add method
`Store` SHALL provide `add_monitors_batch(origin, items: list[tuple[str, ChannelInfo]], max_per_group: int, max_global: int) -> list[str | None]` that:
1. Acquires `self.lock` once.
2. Iterates `items` sequentially, calling the existing `add_monitor` logic per item with incremental limit checks.
3. Persists to disk once after all mutations.
4. Releases the lock.
5. Returns a list of error keys (or `None` for success) corresponding to each input item.

#### Scenario: Incremental limit check during batch add
- **WHEN** group limit is 30 and current count is 28
- **AND** user batch-adds 5 valid channels
- **THEN** the first 2 SHALL succeed (count reaches 30)
- **AND** the remaining 3 SHALL return `cmd.add.limit_group`

#### Scenario: Single lock acquisition for batch
- **WHEN** a batch of 10 channels is added
- **THEN** `self.lock` SHALL be acquired exactly once (not 10 times)

#### Scenario: Single persist after batch
- **WHEN** a batch of 10 channels is added
- **THEN** `_persist()` SHALL be called exactly once after all mutations complete

#### Scenario: Duplicate within store detected per-channel
- **WHEN** channel A already exists in the group and batch is `[A, B]`
- **THEN** A SHALL return `cmd.add.duplicate` and B SHALL succeed

### Requirement: Store batch remove method
`Store` SHALL provide `remove_monitors_batch(origin, items: list[tuple[str, str]]) -> list[bool]` that:
1. Acquires `self.lock` once.
2. Iterates `items` sequentially, calling the existing `remove_monitor` logic per item.
3. Persists to disk once after all mutations.
4. Releases the lock.
5. Returns a list of booleans (True=removed, False=not found) corresponding to each input item.

#### Scenario: Batch remove with mixed results
- **WHEN** batch remove is `[(twitch, a), (twitch, b)]` and only `a` exists
- **THEN** the result SHALL be `[True, False]`

#### Scenario: Single lock acquisition for batch remove
- **WHEN** a batch of 5 channels is removed
- **THEN** `self.lock` SHALL be acquired exactly once

### Requirement: Batch response format
The system SHALL produce a single aggregated response message for all batch operations (including N=1). The response SHALL consist of:
1. A summary line using `cmd.batch.summary_add` or `cmd.batch.summary_remove` with success/failure counts.
2. Per-channel result lines using `cmd.batch.item_*` i18n keys.
3. If truncation occurred, a trailing line using `cmd.batch.truncated`.

#### Scenario: Batch add response with mixed results
- **WHEN** batch add of `[A, B, C]` results in A=success, B=duplicate, C=invalid
- **THEN** the response SHALL contain one summary line and 3 per-channel result lines

#### Scenario: Single channel add uses same format
- **WHEN** `/live add twitch wpnebula` succeeds (N=1)
- **THEN** the response SHALL use the same summary + per-channel format as batch

#### Scenario: Truncation notice appended
- **WHEN** 25 inputs are provided and truncated to 20
- **THEN** the response SHALL end with a truncation notice indicating 5 inputs were skipped

### Requirement: Batch i18n keys
All 3 locale files (en.json, zh-Hans.json, zh-Hant.json) SHALL include the following new keys:
- `cmd.batch.summary_add`: batch add summary with `{success}`, `{fail}` placeholders
- `cmd.batch.summary_remove`: batch remove summary with `{success}`, `{fail}` placeholders
- `cmd.batch.item_success`: per-channel success line with `{platform}`, `{name}`, `{id}` placeholders
- `cmd.batch.item_duplicate`: per-channel duplicate line with `{id}` placeholder
- `cmd.batch.item_removed`: per-channel removed line with `{platform}`, `{id}` placeholder
- `cmd.batch.item_not_found`: per-channel not-found line with `{id}` placeholder
- `cmd.batch.item_fail`: per-channel failure line with `{id}`, `{reason}` placeholders
- `cmd.batch.item_limit_group`: per-channel group limit line with `{id}` placeholder
- `cmd.batch.item_limit_global`: per-channel global limit line with `{id}` placeholder
- `cmd.batch.truncated`: truncation notice with `{max}`, `{total}` placeholders
- `cmd.batch.mixed_mode`: mode mixing rejection message

#### Scenario: All locales have identical placeholder sets
- **WHEN** the i18n system loads any `cmd.batch.*` key
- **THEN** all 3 locale files SHALL define the key with identical `{placeholder}` sets

### Requirement: No immediate status check after batch add
The system SHALL NOT perform `check_status` after batch add (including N=1). Newly added channels SHALL have `last_status = "unknown"` and `initialized = False` until the poller processes them on its next cycle.

#### Scenario: Batch add skips check_status
- **WHEN** a batch of 3 channels is successfully added
- **THEN** zero `check_status` calls SHALL be made
- **AND** all 3 entries SHALL have `initialized = False`

#### Scenario: Single add also skips check_status
- **WHEN** `/live add twitch wpnebula` succeeds (N=1 batch)
- **THEN** zero `check_status` calls SHALL be made

