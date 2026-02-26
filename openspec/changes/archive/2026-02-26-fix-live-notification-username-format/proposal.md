# Proposal: Fix Live Notification Username Format

## Context

目前的直播通知訊息中，用戶名顯示格式存在以下問題：

### Bilibili 平台
- **目前格式**：`嘉然今天吃什么（@嘉然今天吃什么）`
- **問題**：用戶名重複顯示，且未顯示 UID 資訊
- **期望格式**：`@嘉然今天吃什么 (672328094)`

### Twitch 平台
- **目前格式**：`scottybvb（@scottybvb）`
- **問題**：
  - 顯示的是 login name（全小寫），而非 display name（保留原始大小寫）
  - 重複顯示用戶名
- **期望格式**：
  - 若 display_name ≠ login_name（小寫比較）：`ScottyBVB (@scottybvb)`
  - 若 display_name == login_name（小寫比較）：`ScottyBVB`

## Requirements

### R1: Bilibili 用戶名格式
**Scenario**: 當 Bilibili 主播開始直播時
**Given**: 系統獲取到 Bilibili API 回傳的用戶資訊
**When**: 發送直播通知
**Then**: 用戶名顯示格式為 `@用戶名 (UID)`

### R2: Twitch 用戶名格式（不同名稱）
**Scenario**: 當 Twitch 主播的 display_name 與 login_name 不同時
**Given**: display_name.lower() != login_name.lower()
**When**: 發送直播通知
**Then**: 用戶名顯示格式為 `DisplayName (@loginname)`

### R3: Twitch 用戶名格式（相同名稱）
**Scenario**: 當 Twitch 主播的 display_name 與 login_name 相同時
**Given**: display_name.lower() == login_name.lower()
**When**: 發送直播通知
**Then**: 用戶名僅顯示 `DisplayName`

### R4: 向後相容性
**Scenario**: 現有監控頻道
**Given**: 已存在的監控資料
**When**: 系統讀取舊資料
**Then**: 應正常運作，不影響現有功能

## Success Criteria

- [ ] Bilibili 通知顯示格式為 `@用戶名 (UID)`
- [ ] Twitch 通知正確區分 display_name 和 login_name
- [ ] 當 display_name 與 login_name 小寫相同時，只顯示 display_name
- [ ] 當 display_name 與 login_name 小寫不同時，顯示 `DisplayName (@loginname)`
- [ ] 所有現有測試通過
- [ ] 新增單元測試覆蓋新邏輯

## Dependencies

- `core/models.py` - StatusSnapshot 和 ChannelInfo 資料結構
- `platforms/bilibili.py` - Bilibili API 資料獲取
- `platforms/twitch.py` - Twitch API 資料獲取
- `core/notifier.py` - 通知訊息建構
- `i18n/*.json` - 多語言訊息模板

## Scope

**In Scope**:
- 修改 Bilibili 平台的用戶名顯示邏輯
- 修改 Twitch 平台的用戶名顯示邏輯
- 更新 i18n 訊息模板
- 新增單元測試

**Out of Scope**:
- YouTube 平台（目前無此需求）
- 資料庫遷移
- UI 介面變更
