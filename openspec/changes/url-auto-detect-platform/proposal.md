# URL Auto-Detect Platform

## Context

Currently `/live add` requires explicit platform + channel identifier:
- `/live add bilibili https://live.bilibili.com/22637261` (URL works, parsed in `BilibiliChecker.validate_channel`)
- `/live add youtube @GawrGura` (handle works, but URL does not)
- `/live add twitch shroud` (username works, but URL does not)

Users expect to paste URLs directly from their browser. Bilibili already demonstrates this pattern — extend it to YouTube and Twitch, then add auto-detection so the platform argument becomes optional.

## Requirements

### R1: YouTube URL support in `validate_channel`
- **Input**: `https://www.youtube.com/@GawrGura`, `https://youtube.com/channel/UCoSrY_IQQVpmIRZ9Xf-y93g`
- **Behavior**: Extract `@handle` or `UC...` channel_id from URL, delegate to existing resolution logic
- **Scenario**: `/live add youtube https://www.youtube.com/@GawrGura` → resolves to channel, adds monitor
- **Constraint**: Reuse existing `_resolve_handle` / `_get_channel_name` — no new HTTP calls

### R2: Twitch URL support in `validate_channel`
- **Input**: `https://www.twitch.tv/shroud`, `https://twitch.tv/shroud`
- **Behavior**: Extract username from URL path, delegate to existing Helix API validation
- **Scenario**: `/live add twitch https://www.twitch.tv/shroud` → resolves to user, adds monitor
- **Constraint**: Reuse existing `_get_with_retry` + Helix lookup — no new HTTP calls

### R3: Auto-detect platform from URL (separate path)
- **Input**: `/live add https://live.bilibili.com/22637261`
- **Behavior**: Two independent command paths coexist:
  - Path A (original): `/live add <platform> <channel_id>` — unchanged
  - Path B (new): `/live add <url>` — auto-detect platform from URL
- **Implementation**: Make `channel_id` parameter optional (`channel_id: str = ""`). When empty, treat first arg as URL and match against platform patterns:
  - `youtube.com` → `youtube`
  - `twitch.tv` → `twitch`
  - `live.bilibili.com` → `bilibili`
- **Scenario**: `/live add https://www.twitch.tv/shroud` → detects twitch, extracts `shroud`, adds monitor

### R4: Error handling for unrecognized URLs
- **Scenario**: `/live add https://unknown-site.com/foo` → show error with supported URL formats
- **Constraint**: New i18n key for unrecognized URL error (all 3 locales)

## Hard Constraints
- `cmd_add` must remain fully backward-compatible: `/live add bilibili 672328094` must still work
- No new dependencies — URL parsing uses `re` and `urllib.parse` (already imported)
- Each platform checker's `validate_channel` handles its own URL extraction internally (same pattern as Bilibili)
- Auto-detect logic lives in `main.py`, not in platform checkers
- `cmd_check` and `cmd_remove` are out of scope

## Success Criteria
1. `/live add youtube https://www.youtube.com/@GawrGura` adds monitor successfully
2. `/live add youtube https://www.youtube.com/channel/UCoSrY_IQQVpmIRZ9Xf-y93g` adds monitor successfully
3. `/live add twitch https://www.twitch.tv/shroud` adds monitor successfully
4. `/live add https://live.bilibili.com/22637261` auto-detects bilibili and adds monitor
5. `/live add https://www.youtube.com/@GawrGura` auto-detects youtube and adds monitor
6. `/live add https://www.twitch.tv/shroud` auto-detects twitch and adds monitor
7. `/live add bilibili 672328094` still works (backward compat)
8. `/live add youtube @GawrGura` still works (backward compat)
9. `/live add https://unknown.com/foo` shows clear error message
