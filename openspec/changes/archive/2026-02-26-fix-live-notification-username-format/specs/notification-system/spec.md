# Specification: Notification Username Format

## Overview

定義直播通知訊息中用戶名的顯示格式規則。

## Data Model

### StatusSnapshot Extension

```python
@dataclass
class StatusSnapshot:
    is_live: bool
    stream_id: str = ""
    title: str = ""
    category: str = ""
    thumbnail_url: str = ""
    streamer_name: str = ""          # Display name (保留原始大小寫)
    stream_url: str = ""
    success: bool = True
    display_id: str | None = None    # 平台特定 ID (Bilibili UID / Twitch login)
    login_name: str | None = None    # Twitch login name (全小寫)
```

## Format Rules

### Bilibili Format

**Rule**: `@{streamer_name} ({display_id})`

**Example**:
- Input: `streamer_name="嘉然今天吃什么"`, `display_id="672328094"`
- Output: `@嘉然今天吃什么 (672328094)`

### Twitch Format

**Rule**:
1. 若 `login_name` 為空或 `streamer_name.lower() == login_name.lower()`:
   - Output: `{streamer_name}`
2. 否則:
   - Output: `{streamer_name} (@{login_name})`

**Examples**:
| streamer_name | login_name | Output |
|--------------|------------|--------|
| ScottyBVB | scottybvb | `ScottyBVB` |
| 日本語配信者 | japanese_streamer | `日本語配信者 (@japanese_streamer)` |
| xqc | xqc | `xqc` |

## i18n Template Changes

### Current Templates

```json
{
  "notify.live_start": "🟢 {name} 正在 {platform} 直播！\n{title}\n{category}\n{url}",
  "notify.embed.footer": "{name}（@{id}）"
}
```

### New Templates

```json
{
  "notify.live_start": "🟢 {name} 正在 {platform} 直播！\n{title}\n{category}\n{url}",
  "notify.embed.footer": "{formatted_name}"
}
```

註：`formatted_name` 由 Notifier 根據平台規則預先格式化，不再於 i18n 模板中組合。

## Notifier Logic

### Format Function

```python
def _format_streamer_name(self, snapshot: StatusSnapshot, platform: str) -> str:
    """根據平台規則格式化主播名稱顯示。"""
    name = snapshot.streamer_name or "Unknown"
    display_id = snapshot.display_id or ""
    login_name = getattr(snapshot, "login_name", None)

    if platform == "bilibili":
        # Bilibili: @用戶名 (UID)
        return f"@{name} ({display_id})"

    if platform == "twitch":
        # Twitch: 比較 display_name 和 login_name
        if login_name and name.lower() != login_name.lower():
            return f"{name} (@{login_name})"
        return name

    # Default: 使用原始格式
    return f"{name}（@{display_id}）"
```

### Embed Building

```python
def _build_live_embed(self, lang: str, platform: str, snapshot: StatusSnapshot) -> MessageChain:
    formatted_name = self._format_streamer_name(snapshot, platform)
    template = self._i18n.get(lang, "notify.embed.live_title")
    title = self._truncate_title(template, snapshot.streamer_name)
    footer = formatted_name  # 直接使用格式化後的名稱
    # ... rest of embed building
```

## Testing Requirements

### Unit Tests

1. **Bilibili Format Test**
   ```python
   def test_bilibili_username_format():
       snapshot = StatusSnapshot(
           is_live=True,
           streamer_name="嘉然今天吃什么",
           display_id="672328094"
       )
       result = notifier._format_streamer_name(snapshot, "bilibili")
       assert result == "@嘉然今天吃什么 (672328094)"
   ```

2. **Twitch Same Name Test**
   ```python
   def test_twitch_same_name_format():
       snapshot = StatusSnapshot(
           is_live=True,
           streamer_name="ScottyBVB",
           display_id="scottybvb",
           login_name="scottybvb"
       )
       result = notifier._format_streamer_name(snapshot, "twitch")
       assert result == "ScottyBVB"
   ```

3. **Twitch Different Name Test**
   ```python
   def test_twitch_different_name_format():
       snapshot = StatusSnapshot(
           is_live=True,
           streamer_name="日本語配信者",
           display_id="japanese_streamer",
           login_name="japanese_streamer"
       )
       result = notifier._format_streamer_name(snapshot, "twitch")
       assert result == "日本語配信者 (@japanese_streamer)"
   ```

## Backward Compatibility

- `StatusSnapshot` 新增 `login_name` 欄位為可選，不影響現有資料
- `ChannelInfo` 結構保持不變
- 舊版資料缺少 `login_name` 時，Twitch 顯示邏輯退化為只顯示 `streamer_name`
