## Context

The current Discord Embed notifications display minimal structure: static titles ("🟢 Now LIVE!" / "🔴 Stream Ended"), streamer name buried in the footer, and fields without emoji decoration. The redesign merges the streamer name into the title, enriches fields with emoji prefixes, adds a dedicated Link field, and enhances the footer to show both name and display ID.

Affected code surface: `core/notifier.py` (embed builders), `core/poller.py` (display_id propagation), `core/models.py` (`_PendingNotification`), `main.py` (test_notify), and all three i18n JSON files.

Key constraints:
- DiscordEmbed must be constructed via `_make_embed()` using the Pydantic v1 `__new__` + `object.__setattr__` bypass.
- Discord API enforces a 256-character limit on embed titles.
- The `send_end_notification` path currently lacks access to `display_id`; the poller must propagate it.

## Goals / Non-Goals

**Goals:**
- Merge streamer name into embed title with i18n template support
- Add emoji-prefixed fields (📡 Platform, 🎮 Category, 🔗 Link)
- Enhance footer to display `{name}（@{id}）` format
- Protect against title length overflow via name truncation
- Propagate `display_id` through the end-notification data path

**Non-Goals:**
- Modifying plain-text notification format (non-Discord targets unchanged)
- Adding new fields beyond Platform, Category, Link (e.g., viewer count, duration)
- Refactoring embed builders into a declarative/factory pattern
- Sanitizing streamer names for Discord Markdown (accepted as-is)
- Changing the `_make_embed` Pydantic v1 bypass mechanism

## Decisions

### D1: Title truncation — truncate name only, preserve template

**Decision**: Compute `budget = 256 - len(template.format(name=""))`, then truncate `streamer_name` to `budget - 1` chars + `…` if it exceeds `budget`.

**Rationale**: Truncating the full title could cut off meaningful suffixes like "is LIVE!" or "直播開始！", producing confusing text. Truncating only the name portion preserves the template structure and keeps the meaning intact across all locales.

**Implementation**: A private helper `_truncate_title(template: str, name: str) -> str` computes the budget per invocation, accounting for locale-dependent template lengths.

**Alternatives considered**:
- Truncate entire title string at 256 → Loses template suffix, poor UX
- Don't truncate, rely on Discord API → Discord silently truncates or rejects; behavior is undocumented and unreliable

### D2: Footer format — i18n template with `{name}` and `{id}`

**Decision**: Add `notify.embed.footer` i18n key with value `{name}（@{id}）`. When `display_id` is empty, fall back to `streamer_name` as `{id}`.

**Rationale**: Using an i18n template for the footer allows locales to adjust formatting (e.g., different bracket styles or ordering). The fallback to `streamer_name` ensures the footer is always meaningful even if display_id is unavailable.

**Implementation**: `footer = self._i18n.get(lang, "notify.embed.footer", name=streamer_name, id=display_id or streamer_name)`.

**Alternatives considered**:
- Hardcode `f"{name}（@{id}）"` → Not localizable
- Use two separate i18n keys (with/without ID) → Over-engineered; the fallback substitution is sufficient
- Omit footer entirely (per original proposal) → User explicitly requested keeping footer with enhanced format

### D3: display_id propagation for end notifications

**Decision**: Add `display_id: str` field to `_PendingNotification`. Populate from `entry.display_id` (MonitorEntry) rather than `snapshot.display_id`. Add `display_id: str = ""` parameter to `send_end_notification` and `_build_end_embed`.

**Rationale**: At LIVE_END time, the current poll returns an "offline" snapshot whose `display_id` may be `None` (platform checkers don't always populate it on offline checks). The `MonitorEntry.display_id` is reliably updated during prior live checks and defaults to `channel_id` via `__post_init__`, making it the most robust source.

**Alternatives considered**:
- Pass entire `snapshot` to `send_end_notification` → Larger signature change with unused fields; breaks the explicit interface
- Store `display_id` separately in the notifier → Introduces state management complexity

### D4: Category and stream_url conditionality — strip before truthy check

**Decision**: Use `.strip()` on `snapshot.category` and `snapshot.stream_url` before truthy evaluation for field inclusion.

**Rationale**: Whitespace-only strings are truthy in Python but produce visually empty Discord fields. Stripping prevents degenerate fields from appearing in the embed.

### D5: Link field value format — raw URL

**Decision**: The Link field value is the raw `stream_url` string, not a Markdown hyperlink.

**Rationale**: Discord embed field values do not render Markdown links — only the `description` field supports Markdown. Using raw URLs ensures Discord auto-links them. The title already provides a clickable link via the `url` attribute, but the Link field provides explicit visibility on mobile clients where title links are less obvious.

### D6: Field ordering — fixed deterministic order

**Decision**: Fields are always ordered: Platform (inline) → Category (inline, conditional) → Link (non-inline, conditional).

**Rationale**: Fixed ordering ensures consistent visual layout across all notifications. The 2-inline + 1-full-width pattern follows Discord embed best practices for information density.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| `footer=None` via `object.__setattr__` may serialize incorrectly | Test with `test_notify` command against real Discord. If issues arise, omit `footer` key from `_make_embed` kwargs entirely. |
| i18n `{name}` placeholder missing in a locale file → raw `{name}` displayed | `I18nManager.get()` catches format errors and returns template as-is. Add i18n key consistency validation (P9 property). |
| Multi-byte Unicode in streamer names affects truncation budget calculation | Python `len()` counts codepoints, which matches Discord's limit. No special handling needed. |
| `display_id` propagation adds a field to `_PendingNotification` | Minimal impact; `_PendingNotification` is a private dataclass used only within `poller.py`. |
| `test_notify` must be updated to match new signatures | Low risk; single call site with hardcoded test values. |

## Open Questions

None — all decisions have been resolved through multi-model analysis and user confirmation.
