# Design: Fix Live Notification Username Format

## Architecture

### Component Interaction

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              Platform Layer                              │
│  ┌─────────────────────┐            ┌─────────────────────┐             │
│  │   BilibiliChecker   │            │    TwitchChecker    │             │
│  │                     │            │                     │             │
│  │  - Fetch API data   │            │  - Fetch API data   │             │
│  │  - Extract uname    │            │  - Extract user_name│             │
│  │  - Set display_id   │            │  - Extract user_login│            │
│  │    to UID           │            │  - Set login_name   │             │
│  └──────────┬──────────┘            └──────────┬──────────┘             │
└─────────────┼──────────────────────────────────┼────────────────────────┘
              │                                  │
              ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            Data Model Layer                              │
│                      ┌─────────────────────┐                             │
│                      │   StatusSnapshot    │                             │
│                      │                     │                             │
│                      │  - streamer_name    │  # Display name             │
│                      │  - display_id       │  # UID / login              │
│                      │  - login_name       │  # Twitch only              │
│                      └──────────┬──────────┘                             │
└─────────────────────────────────┼───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Notification Layer                             │
│                      ┌─────────────────────┐                             │
│                      │      Notifier       │                             │
│                      │                     │                             │
│                      │  _format_streamer   │                             │
│                      │     _name()         │  # Platform-specific logic  │
│                      │                     │                             │
│                      │  Bilibili: @name    │                             │
│                      │            (uid)    │                             │
│                      │                     │                             │
│                      │  Twitch:  compare   │                             │
│                      │   display vs login  │                             │
│                      └──────────┬──────────┘                             │
└─────────────────────────────────┼───────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              Output Layer                                │
│                    Discord Embed / Plain Text                            │
└─────────────────────────────────────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: Data Model Update

**File**: `core/models.py`

Add `login_name` field to `StatusSnapshot`:

```python
@dataclass
class StatusSnapshot:
    is_live: bool
    stream_id: str = ""
    title: str = ""
    category: str = ""
    thumbnail_url: str = ""
    streamer_name: str = ""
    stream_url: str = ""
    success: bool = True
    display_id: str | None = None
    login_name: str | None = None  # NEW: For Twitch format logic
```

### Phase 2: Platform Adapter Updates

**File**: `platforms/bilibili.py`

Update `check_status()` to set `display_id`:

```python
results[uid] = StatusSnapshot(
    is_live=is_live,
    stream_id=room_id if is_live else "",
    title=info.get("title", ""),
    category=info.get("area_v2_name", ""),
    thumbnail_url=info.get("cover_from_user", ""),
    streamer_name=info.get("uname", uid),
    stream_url=f"https://live.bilibili.com/{room_id}" if room_id else "",
    display_id=uid,  # NEW: Set to UID
)
```

**File**: `platforms/twitch.py`

Update `check_status()` to set `login_name` and `display_id`:

```python
user_login = stream.get("user_login", uid).lower()
results[uid] = StatusSnapshot(
    is_live=True,
    stream_id=stream.get("id", ""),
    title=stream.get("title", ""),
    category=stream.get("game_name", ""),
    thumbnail_url=thumb,
    streamer_name=stream.get("user_name", uid),
    stream_url=f"https://www.twitch.tv/{uid}",
    display_id=user_login,  # NEW
    login_name=user_login,  # NEW
)
```

### Phase 3: Notifier Update

**File**: `core/notifier.py`

Add format function and update embed building:

```python
def _format_streamer_name(self, snapshot: StatusSnapshot, platform: str) -> str:
    """根據平台規則格式化主播名稱顯示。"""
    name = snapshot.streamer_name or "Unknown"
    display_id = snapshot.display_id or ""
    login_name = getattr(snapshot, "login_name", None)

    if platform == "bilibili":
        return f"@{name} ({display_id})"

    if platform == "twitch":
        if login_name and name.lower() != login_name.lower():
            return f"{name} (@{login_name})"
        return name

    return f"{name}（@{display_id}）"
```

Update `_build_live_embed()`:

```python
def _build_live_embed(self, lang: str, platform: str, snapshot: StatusSnapshot) -> MessageChain:
    template = self._i18n.get(lang, "notify.embed.live_title")
    title = self._truncate_title(template, snapshot.streamer_name)
    formatted_name = self._format_streamer_name(snapshot, platform)
    footer = formatted_name  # Use pre-formatted name
    # ... rest unchanged
```

### Phase 4: i18n Update (Optional)

**Files**: `i18n/zh-Hant.json`, `i18n/zh-Hans.json`, `i18n/en.json`

Current footer template can be simplified since formatting is now done in code:

```json
{
  "notify.embed.footer": "{formatted_name}"
}
```

Or keep backward compatible:

```python
# In notifier, pass formatted_name as both name and id
footer = self._i18n.get(
    lang,
    "notify.embed.footer",
    name=formatted_name,
    id=""
).rstrip("（@）")  # Remove trailing empty parens if any
```

## Decision Log

| Decision | Rationale |
|----------|-----------|
| Add `login_name` to `StatusSnapshot` | Needed for Twitch format comparison logic |
| Format in Notifier, not in i18n | Allows platform-specific conditional logic |
| Keep `display_id` usage | Reuse existing field for UID/login storage |
| Case-insensitive comparison | Twitch login names are case-insensitive |

## Testing Strategy

1. **Unit Tests**: Test `_format_streamer_name()` with various inputs
2. **Integration Tests**: Mock API responses, verify end-to-end flow
3. **Regression Tests**: Ensure existing tests still pass

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Backward compatibility | `login_name` is optional, defaults to None |
| Missing display_id | Fallback to existing behavior in formatter |
| i18n breaking changes | Keep template parameters, format in code |
