# Spec: livelist-platform-grouping

## S1: Platform-grouped output

- **GIVEN** a group with monitors on N platforms (N ≥ 1)
- **WHEN** `/live list` is executed
- **THEN** output starts with header line, followed by N platform sections
- **AND** each section has: platform name line → `- {emoji} {name}（{display_id}）` per entry
- **AND** sections are separated by exactly one blank line
- **AND** no trailing blank line after last section

### PBT Properties

- **P1 (Completeness)**: Every entry in `gs.monitors` appears exactly once in output.
  - Falsification: Add entry, run list, assert entry text present.
- **P2 (No empty sections)**: Platform header only appears if platform has ≥ 1 entry.
  - Falsification: Create monitors dict with empty platform dict, assert platform name absent from output.
- **P3 (Deterministic order)**: Platform sections follow `_VALID_PLATFORMS` order regardless of insertion order.
  - Falsification: Insert bilibili before youtube, assert youtube section appears first.

## S2: URL-decoded display_id

- **GIVEN** a monitor entry with URL-encoded `display_id` (e.g. `@%E6%A3%AE%E6%A3%AE%E9%88%B4%E8%98%ADLilyLinglan`)
- **WHEN** `/live list` is executed
- **THEN** output shows decoded value (`@森森鈴蘭LilyLinglan`)

- **GIVEN** a monitor entry with non-encoded `display_id` (e.g. `2978046`)
- **WHEN** `/live list` is executed
- **THEN** output shows value unchanged

- **GIVEN** a monitor entry with malformed percent-encoding in `display_id`
- **WHEN** `/live list` is executed
- **THEN** output shows raw value (no crash, no replacement chars)

### PBT Properties

- **P4 (Round-trip safe)**: `unquote(display_id)` on already-decoded string returns same string.
  - Falsification: Pass plain ASCII handle, assert output unchanged.
- **P5 (Decode correctness)**: `unquote(encoded)` produces expected Unicode.
  - Falsification: Encode known CJK string, pass to unquote, assert equality.

## S3: No side effects

- **GIVEN** any `/live list` execution
- **THEN** no writes to store, no mutation of `MonitorEntry` fields
- **AND** other commands (`add`, `remove`, `check`, `notify`) unaffected
