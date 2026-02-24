# Design: livelist-platform-grouping

## D1: Output format

Platform header as standalone line, entries indented with `- ` prefix. Blank line between platform groups. Only platforms with entries are shown.

```
{header}
{platform}
- {emoji} {name}（{display_id}）
- {emoji} {name}（{display_id}）

{platform}
- {emoji} {name}（{display_id}）
```

## D2: Platform ordering

Use `_VALID_PLATFORMS` tuple order (`youtube`, `twitch`, `bilibili`) for deterministic output regardless of dict insertion order.

## D3: i18n template changes

- `cmd.list.header`: unchanged
- `cmd.list.platform_header`: new key — `"{platform}"`
- `cmd.list.entry`: remove `{platform}`, add `- ` prefix — `"- {status_emoji} {name}（{display_id}）"`

All 3 locale files (en, zh-Hans, zh-Hant) updated identically for these keys.

## D4: URL decode strategy

- Display-layer only: `urllib.parse.unquote(display_id)` in `cmd_list` before formatting.
- Fallback: on any exception, use raw `display_id`.
- Storage layer unchanged — `lookup_by_display_id` continues to match raw values.
- `unquote` (not `unquote_plus`) to preserve `+` in handles.

## D5: Platform name display

Keep raw lowercase platform names (`youtube`, `twitch`, `bilibili`) — no localization. Matches user's requested format.
