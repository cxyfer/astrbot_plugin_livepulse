# Tasks: livelist-platform-grouping

## Task 1: Update i18n templates ✅

Files: `i18n/en.json`, `i18n/zh-Hans.json`, `i18n/zh-Hant.json`

For each file:
- Add key `"cmd.list.platform_header"` with value `"{platform}"`
- Change `"cmd.list.entry"` to `"- {status_emoji} {name} ({display_id})"` (en) / `"- {status_emoji} {name}（{display_id}）"` (zh-Hans, zh-Hant)
  - Remove `{platform} | ` prefix and leading 2-space indent

## Task 2: Refactor `cmd_list` in `main.py` ✅

File: `main.py` (lines 223-237)

- Add `from urllib.parse import unquote` to imports
- Replace `cmd_list` body:
  1. Build header line
  2. Iterate platforms in `_VALID_PLATFORMS` order (skip if platform not in `gs.monitors` or empty)
  3. For each platform: append platform header via `cmd.list.platform_header`, then each entry via `cmd.list.entry` with `unquote(entry.display_id)`
  4. Insert blank line between platform sections (not after last)
  5. Join and yield
