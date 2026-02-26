# Specification: Platform Adapter Updates

## Overview

更新 Bilibili 和 Twitch 平台適配器，以支援新的用戶名顯示格式需求。

## Bilibili Adapter

### Current Implementation

```python
results[uid] = StatusSnapshot(
    is_live=is_live,
    stream_id=room_id if is_live else "",
    title=info.get("title", ""),
    category=info.get("area_v2_name", ""),
    thumbnail_url=info.get("cover_from_user", ""),
    streamer_name=info.get("uname", uid),
    stream_url=f"https://live.bilibili.com/{room_id}" if room_id else "",
)
```

### Required Changes

1. **Set `display_id` to UID**: Bilibili 的 `display_id` 應為數字 UID
2. **No `login_name` needed**: Bilibili 不需要此欄位

### Updated Implementation

```python
results[uid] = StatusSnapshot(
    is_live=is_live,
    stream_id=room_id if is_live else "",
    title=info.get("title", ""),
    category=info.get("area_v2_name", ""),
    thumbnail_url=info.get("cover_from_user", ""),
    streamer_name=info.get("uname", uid),
    stream_url=f"https://live.bilibili.com/{room_id}" if room_id else "",
    display_id=uid,  # Bilibili 使用 UID 作為 display_id
)
```

## Twitch Adapter

### Current Implementation

```python
results[uid] = StatusSnapshot(
    is_live=True,
    stream_id=stream.get("id", ""),
    title=stream.get("title", ""),
    category=stream.get("game_name", ""),
    thumbnail_url=thumb,
    streamer_name=stream.get("user_name", uid),  # display_name
    stream_url=f"https://www.twitch.tv/{uid}",
)
```

### Required Changes

1. **Add `login_name` field**: 儲存 user_login（全小寫）
2. **Set `display_id` to login name**: Twitch 的 `display_id` 應為 login name

### API Response Fields

Twitch Streams API 回傳欄位：
- `user_name`: Display name（保留大小寫，如 "ScottyBVB"）
- `user_login`: Login name（全小寫，如 "scottybvb"）

### Updated Implementation

```python
user_login = stream.get("user_login", uid).lower()
results[uid] = StatusSnapshot(
    is_live=True,
    stream_id=stream.get("id", ""),
    title=stream.get("title", ""),
    category=stream.get("game_name", ""),
    thumbnail_url=thumb,
    streamer_name=stream.get("user_name", uid),  # display_name
    stream_url=f"https://www.twitch.tv/{uid}",
    display_id=user_login,  # Twitch 使用 login name 作為 display_id
    login_name=user_login,  # 儲存 login name 供格式判斷使用
)
```

## Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Bilibili API   │────▶│  BilibiliChecker │────▶│ StatusSnapshot  │
│  - uname        │     │  .check_status() │     │ - streamer_name │
│  - uid          │     │                  │     │ - display_id    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
┌─────────────────┐     ┌──────────────────┐              │
│  Twitch API     │────▶│  TwitchChecker   │──────────────┘
│  - user_name    │     │  .check_status() │
│  - user_login   │     │                  │
└─────────────────┘     └──────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │     Notifier     │
                        │ _format_streamer │
                        │     _name()      │
                        └──────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  Discord Embed   │
                        │  or Plain Text   │
                        └──────────────────┘
```

## Testing Requirements

### Bilibili Adapter Tests

```python
async def test_bilibili_check_status_sets_display_id():
    """驗證 Bilibili adapter 正確設定 display_id 為 UID"""
    # Mock API response
    # Assert StatusSnapshot.display_id == uid
```

### Twitch Adapter Tests

```python
async def test_twitch_check_status_sets_login_name():
    """驗證 Twitch adapter 正確設定 login_name"""
    # Mock API response with user_name and user_login
    # Assert StatusSnapshot.login_name == user_login.lower()
    # Assert StatusSnapshot.display_id == user_login.lower()
```
