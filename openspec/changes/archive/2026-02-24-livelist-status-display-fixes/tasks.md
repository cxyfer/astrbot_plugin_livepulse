## 1. Data Model Changes

- [x] 1.1 Add `success: bool = True` field to `StatusSnapshot` in `core/models.py`
- [x] 1.2 Add `display_id: str | None = None` field to `StatusSnapshot` in `core/models.py`
- [x] 1.3 Add `display_id: str` field to `ChannelInfo`, update `to_dict` and `from_dict` in `core/models.py`
- [x] 1.4 Add `display_id: str` field to `MonitorEntry`, update `to_dict` and `from_dict` with fallback `d.get("display_id", d["channel_id"])` in `core/models.py`
- [x] 1.5 Add `STATUS_EMOJI: dict[str, str]` constant (`live`→🟢, `offline`→🔴, `unknown`→❓) to `core/models.py`

## 2. Platform Checkers

- [x] 2.1 YouTube: extract `@handle` from `canonicalBaseUrl` in `validate_channel` / `_resolve_handle` / `_get_channel_name`, return `ChannelInfo` with `display_id`
- [x] 2.2 YouTube: populate `StatusSnapshot.display_id` from `canonicalBaseUrl` in `check_status`
- [x] 2.3 YouTube: set `success=False` on non-`RateLimitError` exceptions in `check_status` instead of returning `StatusSnapshot(is_live=False)`
- [x] 2.4 Twitch: set `display_id=channel_id` in `validate_channel` return, set `success=False` on failures in `check_status`
- [x] 2.5 Bilibili: set `display_id=channel_id` in `validate_channel` return, set `success=False` on failures in `check_status`

## 3. Store Layer

- [x] 3.1 Update `add_monitor` to accept and store `display_id` on `MonitorEntry`
- [x] 3.2 Add `lookup_by_display_id(origin, platform, display_id) -> str | None` method to `Store`

## 4. Poller Updates

- [x] 4.1 Gate `update_status` and `_compute_transition` on `StatusSnapshot.success == True` in `_process_results`
- [x] 4.2 Update `MonitorEntry.display_id` from `StatusSnapshot.display_id` when `success == True` and value is non-empty, in `_process_results`

## 5. Command Handlers

- [x] 5.1 `cmd_add`: perform immediate `check_status` after `add_monitor`, update `last_status` / `initialized` / `display_id` on success
- [x] 5.2 `cmd_list`: compute `status_emoji` via `STATUS_EMOJI`, pass `status_emoji` and `display_id` to i18n template
- [x] 5.3 `cmd_remove`: attempt `channel_id` match first, fallback to `store.lookup_by_display_id` for `@handle` removal

## 6. i18n Templates

- [x] 6.1 Update `cmd.list.entry` to `{status_emoji} {platform} | {name} ({display_id})` in all 3 language files
- [x] 6.2 Update `notify.live_start` leading emoji to 🟢 in all 3 language files
- [x] 6.3 Update `notify.live_end` leading emoji to 🔴 in all 3 language files

## 7. Verification

- [x] 7.1 Verify backward compatibility: load persisted data without `display_id` field, confirm fallback to `channel_id`
- [x] 7.2 Verify `/live add youtube @handle` → immediate check → `/live list` shows 🟢 or 🔴 with `@handle`
- [x] 7.3 Verify `/live remove youtube @handle` resolves and removes correctly
- [x] 7.4 Verify `success=False` check does not overwrite existing `last_status` or trigger transitions
