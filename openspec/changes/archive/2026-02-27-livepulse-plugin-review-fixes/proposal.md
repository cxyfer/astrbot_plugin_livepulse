# Proposal: Fix Plugin Review Issues (Issue #5489)

## Context

AstrBot 官方 PR review bot 對 `astrbot_plugin_livepulse` 提出了五項問題，涵蓋功能性 bug、框架規範違反、架構缺陷及效能瓶頸。本次修改針對所有問題逐一修復，不影響現有功能。

### 問題來源
- GitHub Issue: AstrBotDevs/AstrBot#5489
- 審核工具: `astrpluginreviewer` (自動化 AI 代碼審核)

---

## Requirements

### R1: 修正命令參數解析 bug（main.py）

**Scenario**: 用戶執行 `live notify on` 或 `live end_notify off`
**Given**: `event.message_str` 為 `"live notify on"` 或 `"live end_notify off"`
**When**: `cmd_notify` / `cmd_end_notify` 解析 `parts[1]`
**Then**: `parts[1]` 取到的是 `"notify"` / `"end_notify"` 而非 `"on"` / `"off"`，導致永遠走向 invalid 分支

**Root Cause**: 兩個方法均使用：
```python
parts = event.message_str.strip().split()
arg = parts[1] if len(parts) > 1 else None
```
對於 `live notify on`，`parts = ["live", "notify", "on"]`，`parts[1]` = `"notify"`，非期望的 `"on"`。

**Fix**: 改用既有的 `_parse_batch_args(event, "notify")` / `_parse_batch_args(event, "end_notify")` 方法，其已正確處理前綴去除並回傳剩餘參數列表；取 `args[0] if args else None` 作為 `arg`。不得使用 `parts[-1]`，該方式無法拒絕格式錯誤的輸入（如 `live notify foo on`）。

---

### R2: 修正初始化狀態位設置時機（main.py）

**Scenario**: `initialize()` 過程中發生異常（網路錯誤、Checker 初始化失敗）
**Given**: `self._initialized = True` 在 try block 最開頭執行
**When**: 後續非同步操作拋出例外
**Then**: 插件進入「已初始化但實際未完成」的不一致狀態，`initialize()` 無法重試

**Fix**: 將 `self._initialized = True` 移至所有關鍵初始化步驟完成之後，確保原子性。同時在 `except` 區塊加入資源清理：取消已啟動的 pollers/tasks、關閉已建立的 `ClientSession`、清空部分填充的集合，確保重試時不會洩漏資源或產生重複狀態。

---

### R3: 實作通道級退避邏輯（core/poller.py）

**Scenario**: 個別頻道持續回傳 `success=False`（非限流原因）
**Given**: `_channel_failures: dict[str, int]` 與 `_channel_backoff_until: dict[str, float]` 已宣告但從未寫入
**When**: `_poll_loop` 執行 backoff 過濾 `self._channel_backoff_until.get(cid, 0) <= now`
**Then**: 過濾條件恆為 True（0 <= now），通道級退避形同虛設

**Fix**: 在 `_process_results()` 中，當通道回傳 `success=False` 時，遞增 `_channel_failures[cid]` 並依失敗次數計算指數退避，寫入 `_channel_backoff_until[cid]`；成功時清除記錄。

---

### R4: 統一 Bilibili 限流異常處理（platforms/bilibili.py）

**Scenario**: `cmd_add` 期間觸發 Bilibili API 限流
**Given**: `_validate_uid()` 和 `_resolve_room_id()` 收到 HTTP 429 回應
**When**: 例外被 `except Exception` 攔截並記錄為一般錯誤
**Then**: 限流被誤判為「頻道不存在」，影響批次處理反饋一致性

**Fix**: 在 `_resolve_room_id()`（使用 `session.get`）和 `_validate_uid()`（使用 `session.post`）的回應處理中，於 `resp.raise_for_status()` 之前加入 HTTP 429 檢查並拋出 `RateLimitError("bilibili")`。**關鍵**：兩個方法的 `except Exception` 區塊必須同時補充 `except RateLimitError: raise`（置於 generic handler 之前），否則新拋出的 `RateLimitError` 仍會被 `except Exception` 攔截並轉為 `None`，修復無效。

---

### R5: YouTube 批量狀態檢查改為並發請求（platforms/youtube.py）

**Scenario**: 監控頻道數量 > 10 時的輪詢週期
**Given**: `check_status()` 以 for 迴圈串行 `await self._check_single(cid, session)`
**When**: 每個請求耗時 ~1-2 秒，監控 50 個頻道
**Then**: 單一輪詢週期需 50-100 秒，降低實時性並放大超時概率

**Fix**: 以 worker wrapper 包裝 `_check_single()`，在 wrapper 內捕獲非限流例外並回傳 `StatusSnapshot(success=False)`（與現有串行行為一致），`RateLimitError` 則直接 re-raise。使用 `asyncio.Semaphore(10)` 限制並發上限（必須明確，不可省略）並搭配 `asyncio.gather(*tasks, return_exceptions=False)` 執行。Semaphore 防止連線池耗盡並控制對目標伺服器的請求頻率。

---

## Success Criteria

- [ ] `live notify on` / `live notify off` 命令正確切換狀態，不走向 invalid 分支
- [ ] `live end_notify on` / `live end_notify off` 命令正確切換狀態
- [ ] `initialize()` 在中途異常後可重新執行而不卡在已初始化狀態
- [ ] 個別頻道連續失敗後被暫時跳過，恢復後自動恢復輪詢
- [ ] `cmd_add` 遭遇 Bilibili 429 時，回傳限流錯誤訊息而非「頻道不存在」
- [ ] YouTube 多頻道輪詢改為並發，牆鐘時間接近 O(max_latency) 而非 O(n×latency)
- [ ] 所有現有測試通過
- [ ] 新增針對修復邏輯的單元測試

---

## Dependencies

| 文件 | 修改類型 |
|------|---------|
| `main.py` | R1: 參數解析；R2: 初始化時機 |
| `core/poller.py` | R3: 通道級退避寫入邏輯 |
| `platforms/bilibili.py` | R4: HTTP 429 上拋 |
| `platforms/youtube.py` | R5: asyncio.gather 並發 |

---

## Scope

**In Scope**:
- 以上五項 review 指出的問題
- 對應的單元測試補充

**Out of Scope**:
- `@filter.command_group("live")` 的 event 參數問題（已確認框架設計：group 方法不需 event，子命令方法才需要，當前代碼符合規範）
- `StarTools.get_data_dir()` 遷移（專案已使用 `plugin_data` 慣例，與框架最新規範一致，無需改動）
- Twitch / YouTube 的 `_resolve_*` 方法中 429 處理（影響範圍不在本次 review 明確要求內）
- 效能監控、指標收集等額外功能

---

## Risks

| 風險 | 影響 | 緩解 |
|------|------|------|
| R5 並發改動可能超出 aiohttp 連線池上限 | 連線被拒或超時增加 | 加入 `asyncio.Semaphore(10)` 上限控制 |
| R3 退避閾值設定不當導致頻道長期被跳過 | 漏報直播開始 | 限制最大退避時間（如 5 分鐘上限）並在成功時立即清零 |
| R2 初始化移位後若最後一步仍失敗 | `_initialized` 仍為 False，重試可能重複建立資源 | 在 except 清理已建立的 session/tasks/pollers，確保重試時狀態乾淨 |
