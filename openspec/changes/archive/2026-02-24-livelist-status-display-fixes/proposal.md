# livelist-status-display-fixes

## Context

`/live list` 指令存在三個問題：
1. 新增頻道後狀態顯示 `[unknown]`，需等輪詢週期完成才初始化
2. YouTube 頻道括號中顯示 channel ID（`UC...`），而非更易讀的 `@handle`
3. 狀態標記使用純文字 `[live]`/`[offline]`/`[unknown]`，不夠直觀

## Constraint Sets

### Hard Constraints

1. **資料模型向後相容**：`MonitorEntry.from_dict` / `ChannelInfo.from_dict` 必須能載入不含 `display_id` 的舊資料，fallback 為 `channel_id`
2. **YouTube @handle 解析來源**：頁面 HTML 中 `canonicalBaseUrl":"/@handle"` 格式（已驗證 `/channel/{id}` 和 `/channel/{id}/streams` 頁面均存在此欄位），正則：`"canonicalBaseUrl"\s*:\s*"(/@[^"]+)"`
3. **Emoji 對映**：🟢=live, 🔴=offline, ❓=unknown（使用者確認），同步修改 `notify.live_start` 和 `notify.live_end` 的 emoji
4. **初始化時機**：`/live add` 成功後、持久化前，對單一頻道執行一次 `check_status`；失敗時不阻塞 add 操作
5. **i18n 模板變數**：status emoji 透過 `{status_emoji}` 變數傳入模板，不在模板中硬編碼

### Soft Constraints

1. **display_id 格式**：YouTube 使用 `@handle`（含 @ 前綴），Bilibili/Twitch 使用原 `channel_id`
2. **@handle 解析時機**：在 `validate_channel` 和 `_get_channel_name` 中一併解析，無需額外網路請求
3. **`_check_single` 可順帶解析**：`/streams` 頁面同樣包含 `canonicalBaseUrl`，poller 輪詢時可順帶更新 `display_id`（可選優化，非必要）

### Dependencies

| From | To | Relationship |
|------|----|-------------|
| R2 (display_id) | R1 (初始化) | R1 的 `check_status` 結果可用於更新 display_id |
| R3 (emoji) | i18n 模板 | 三種語言檔案須同步更新 |
| R2 | `ChannelInfo` 模型 | `display_id` 欄位新增 |
| R2 | `MonitorEntry` 模型 | `display_id` 欄位新增 |

### Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| YouTube HTML 結構變動導致 `canonicalBaseUrl` 消失 | @handle 無法解析 | fallback 為 channel_id |
| `/live add` 即時 check 觸發 rate limit | add 操作延遲 | 僅單頻道查詢，風險極低；失敗時靜默跳過 |
| 舊資料遷移 | 已存在的 MonitorEntry 無 display_id | `from_dict` fallback + 輪詢時可漸進更新 |

## Requirements

### R1: live add 時即時初始化狀態

- **場景**：使用者執行 `/live add youtube @EarendelXDFP`，隨後執行 `/live list`
- **現狀**：`MonitorEntry` 建立時 `initialized=False`，list 強制顯示 `unknown`
- **目標**：`add_monitor` 完成後，立即執行一次 `check_status` 並更新 `last_status` 與 `initialized=True`
- **約束**：初始化失敗時不阻塞 add 操作，僅保持 `unknown` 狀態

### R2: 儲存並顯示 @handle

- **場景**：`/live list` 中顯示 `Earendel ch. 厄倫蒂兒 (@EarendelXDFP)` 而非 `Earendel ch. 厄倫蒂兒（UCwzpXmWAFEVKH3VzwvSlY_w）`
- **目標**：
  - `ChannelInfo` 新增 `display_id: str` 欄位
  - `MonitorEntry` 新增 `display_id: str` 欄位
  - YouTube `validate_channel` / `_resolve_handle` / `_get_channel_name` 解析 `canonicalBaseUrl` 取得 `@handle`
  - i18n 模板中 `{channel_id}` 替換為 `{display_id}`
- **約束**：
  - @handle 取不到時 fallback 為 `channel_id`
  - Bilibili/Twitch 的 `display_id` 直接使用 `channel_id`
  - 資料模型需向後相容

### R3: Emoji 狀態標記

- **場景**：`/live list` 和通知訊息中使用 emoji 替代純文字
- **對映**：🟢=live, 🔴=offline, ❓=unknown
- **目標**：
  - i18n `cmd.list.entry` 使用 `{status_emoji}` 變數
  - `notify.live_start` 改用 🟢，`notify.live_end` 改用 🔴
- **約束**：emoji 對映在 Python 中定義，透過模板變數傳入

## Success Criteria

1. `/live add youtube @EarendelXDFP` 後立即 `/live list` 可看到 🔴 或 🟢 狀態（非 ❓）
2. `/live list` 中 YouTube 頻道顯示 `@handle`（如有），非 `UC...` ID
3. 所有狀態標記使用 emoji：🟢 直播中、🔴 離線、❓ 未知
4. 通知訊息中 `notify.live_start` 使用 🟢，`notify.live_end` 使用 🔴
5. 現有已儲存的資料可正常載入（向後相容）
6. Bilibili/Twitch 頻道不受影響

## Affected Files

| File | Change |
|------|--------|
| `core/models.py:12-62` | `ChannelInfo` + `MonitorEntry` 新增 `display_id` 欄位，更新 `to_dict` / `from_dict` |
| `platforms/youtube.py:113-162` | `validate_channel` / `_resolve_handle` / `_get_channel_name` 解析 `canonicalBaseUrl` |
| `platforms/bilibili.py` | `validate_channel` 回傳 `display_id=channel_id` |
| `platforms/twitch.py` | `validate_channel` 回傳 `display_id=channel_id` |
| `core/store.py:57-76` | `add_monitor` 存入 `display_id` |
| `main.py:139-213` | `cmd_add` 加入即時 check；`cmd_list` 傳入 `status_emoji` 和 `display_id` |
| `i18n/en.json:13,31-32` | `cmd.list.entry` + `notify.live_start` + `notify.live_end` 格式更新 |
| `i18n/zh-Hant.json:13,31-32` | 同上 |
| `i18n/zh-Hans.json:13,31-32` | 同上 |
