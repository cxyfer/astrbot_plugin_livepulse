## Context

LivePulse plugin monitors live-streaming channels across YouTube, Twitch, and Bilibili. Three UX issues affect `/live list`: stale `[unknown]` status after adding a channel (no immediate check), raw `UC...` IDs instead of `@handle` for YouTube, and plain-text status markers instead of emoji. The codebase follows a layered architecture: `main.py` (commands) → `core/store.py` (state) → `core/poller.py` (polling loop) → `platforms/*.py` (scrapers) → `core/notifier.py` (push). All state is persisted via `Store` with JSON serialization through `to_dict`/`from_dict`. Backward compatibility with existing persisted data is mandatory.

## Goals / Non-Goals

**Goals:**
- Immediate status initialization on `/live add` so `/live list` never shows ❓ for a reachable channel
- Display YouTube `@handle` instead of `UC...` channel IDs in list and notifications
- Replace text status markers with emoji (🟢/🔴/❓)
- Distinguish "query failed" from "actually offline" via `StatusSnapshot.success`
- Support `/live remove` by `@handle` in addition to `channel_id`
- Maintain backward compatibility with existing persisted data

**Non-Goals:**
- Changing polling intervals or backoff logic
- Adding new platform support
- Modifying the notification delivery mechanism (already fixed in `0ad102a`)
- Real-time display_id sync across groups (progressive update is sufficient)

## Decisions

### D1: Tri-state via `StatusSnapshot.success: bool` field

**Decision:** Add `success: bool = True` to `StatusSnapshot`. Platform checkers set `success=False` on non-`RateLimitError` exceptions instead of returning `StatusSnapshot(is_live=False)`.

**Rationale:** The current design conflates "query failed" with "channel is offline." This causes false `LIVE_END` transitions when a scrape fails mid-stream. A `success` field is the minimal change — it doesn't alter the return type or the `check_status` signature. The poller and `cmd_add` simply gate state updates on `success == True`.

**Alternative considered:** Returning `None` or raising a custom exception on failure. Rejected because it would require changing the `dict[str, StatusSnapshot]` return type of `check_status`, propagating changes to every caller. A boolean field is additive.

### D2: `display_id` fields on `ChannelInfo`, `MonitorEntry`, `StatusSnapshot`

**Decision:** Add `display_id: str` to `ChannelInfo` and `MonitorEntry`, and `display_id: str | None = None` to `StatusSnapshot`.

- `ChannelInfo.display_id`: Set at validation time. YouTube populates from `canonicalBaseUrl`, others use `channel_id`.
- `MonitorEntry.display_id`: Serialized in `to_dict`, deserialized in `from_dict` with fallback `d.get("display_id", d["channel_id"])`.
- `StatusSnapshot.display_id`: Optional. YouTube's `check_status` populates it from page HTML. Poller updates `MonitorEntry.display_id` when `success == True` and value is non-empty.

**Rationale:** Three-layer approach ensures: (1) initial `display_id` is set on add, (2) progressive updates via poller catch handle changes, (3) legacy data degrades gracefully to `channel_id`.

**Alternative considered:** Single source at `ChannelInfo` only, looked up at display time. Rejected because `ChannelInfo` is only available during `cmd_add`; the poller works with `MonitorEntry` and needs the display value persisted alongside it.

### D3: `@handle` extraction via `canonicalBaseUrl` regex

**Decision:** Extract `@handle` from YouTube page HTML using `"canonicalBaseUrl"\s*:\s*"(/@[^"]+)"`. Apply in `validate_channel`, `_get_channel_name`, and `check_status`.

**Rationale:** This field is present in both `/channel/{id}` and `/channel/{id}/streams` pages (verified). It requires no additional HTTP requests. The regex is specific enough to avoid false matches. Fallback to `channel_id` if not found.

**Alternative considered:** Using YouTube Data API. Rejected due to API key requirement and quota limits inconsistent with the plugin's scraping approach.

### D4: Immediate status check in `cmd_add`

**Decision:** After `add_monitor` and before persistence response, call `checker.check_status([channel_id], session)` once. On success: update `last_status`, `initialized=True`, `display_id`. On failure: keep defaults, proceed silently.

**Rationale:** Eliminates the "first poll" gap where `/live list` shows ❓. Single-channel check has negligible rate-limit risk. Failure is non-blocking — the poller will eventually initialize the entry.

**Implementation flow:**
1. `cmd_add` validates channel → gets `ChannelInfo` with `display_id`
2. `store.add_monitor(...)` creates `MonitorEntry(display_id=info.display_id, initialized=False)`
3. Try `checker.check_status([channel_id], session)`
4. If `success == True`: `store.update_status(...)` sets `last_status`, `initialized=True`; also update `display_id` if present
5. `store.persist()`
6. Return success message (regardless of check result)

**Suppression note:** Setting `initialized=True` after the immediate check means the poller's `_compute_transition` will NOT suppress the first observation. This is correct — if the channel is live, we don't want a notification on add (already handled by the fact that `last_status` is set to `"live"` so no `offline→live` transition occurs).

### D5: `Store.lookup_by_display_id` for remove

**Decision:** Add `lookup_by_display_id(origin, platform, display_id) -> str | None` to `Store`. `cmd_remove` first attempts direct `channel_id` match; on miss, calls `lookup_by_display_id`.

**Rationale:** Linear scan over a group's platform monitors is O(n) where n ≤ 30 (per-group limit). No index needed.

### D6: Emoji mapping constant

**Decision:** Define `STATUS_EMOJI: dict[str, str] = {"live": "🟢", "offline": "🔴", "unknown": "❓"}` in `core/models.py`. Use in `cmd_list` and pass as `{status_emoji}` template variable to i18n.

**Rationale:** Single source of truth. Placing in `models.py` keeps it co-located with `Transition` and status-related constants. Template variable approach avoids hardcoding emoji in i18n files for the status field, while notification emoji (🟢/🔴 in `notify.live_start`/`notify.live_end`) are hardcoded in i18n templates since they are static per template.

### D7: i18n template updates

**Decision:** Update all three language files (`en.json`, `zh-Hant.json`, `zh-Hans.json`):
- `cmd.list.entry`: `"  {status_emoji} {platform} | {name} ({display_id})"`
- `notify.live_start`: Replace leading emoji with `🟢`
- `notify.live_end`: Replace leading emoji with `🔴`

**Rationale:** Status emoji in list is dynamic (passed as variable), notification emoji is static (part of template). This separation keeps the mapping constant authoritative for list display while allowing i18n translators to control notification phrasing.

## Risks / Trade-offs

**[YouTube HTML structure change]** → `canonicalBaseUrl` field disappears from page HTML.
Mitigation: `display_id` fallbacks to `channel_id` at every extraction point. Progressive update via poller means a future fix propagates automatically.

**[Immediate check rate limit]** → Burst `/live add` commands trigger YouTube rate limit.
Mitigation: Single-channel check per add. Rate limit is already handled by `RateLimitError` flow. If rate-limited, check fails silently and poller picks up later.

**[Legacy data migration]** → Existing `MonitorEntry` dicts lack `display_id` key.
Mitigation: `from_dict` uses `d.get("display_id", d["channel_id"])`. Poller progressive update fills in correct `@handle` on next successful check. Zero-downtime, no migration script needed.

**[Notification suppression edge case]** → `cmd_add` immediate check sets `initialized=True` + `last_status="live"`. If the channel goes offline before next poll, the poller sees `live→offline` and sends `LIVE_END`. This is correct behavior but may surprise users who just added a live channel.
Mitigation: Acceptable — user subscribed to notifications, receiving an end notification is expected.

**[success=False accumulation]** → Persistent scraping failures keep `initialized=False` indefinitely for entries where immediate check also failed.
Mitigation: Status shows ❓ which accurately reflects the unknown state. No incorrect notifications are sent. User can re-add the channel if needed.
