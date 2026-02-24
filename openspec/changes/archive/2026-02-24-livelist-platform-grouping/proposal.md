# livelist-platform-grouping

## Context

`/live list` 目前以平鋪格式顯示所有監控頻道，每行重複標示平台名稱，且 YouTube 的 `display_id`（來自 `canonicalBaseUrl`）含有 URL 編碼的中文字元。

**現行輸出：**
```
本群監控清單：
  🔴 youtube | Earendel ch. 厄倫蒂兒（@EarendelXDFP）
  🔴 youtube | 森森鈴蘭 / Lily Linglan（@%E6%A3%AE%E6%A3%AE%E9%88%B4%E8%98%ADLilyLinglan）
  🟢 youtube | 柴崎楓音 / Shibasaki Fuune（@shibasakifuunethebox9424）
  🔴 bilibili | 翼侯大人（2978046）
```

## Requirements

### R1: 依平台分組顯示

**目標輸出：**
```
本群監控清單：
youtube
- 🔴 Earendel ch. 厄倫蒂兒（@EarendelXDFP）
- 🟢 柴崎楓音 / Shibasaki Fuune（@shibasakifuunethebox9424）

bilibili
- 🔴 翼侯大人（2978046）
```

- 每個平台顯示一次標題行，頻道縮排列於其下
- 平台區塊之間以空行分隔
- 僅顯示有頻道的平台

### R2: 修正 URL 編碼的中文用戶名

- `@%E6%A3%AE%E6%A3%AE%E9%88%B4%E8%98%ADLilyLinglan` → `@森森鈴蘭LilyLinglan`
- 在顯示層對 `display_id` 執行 URL decode
- 解碼失敗時 fallback 為原始值

## Constraints

- **C1**: 資料已按 `monitors[platform][channel_id]` 分組儲存，無需重構資料結構
- **C2**: 影響範圍限於 `main.py:cmd_list` 及 3 個 i18n JSON（en / zh-Hans / zh-Hant）
- **C3**: i18n 需新增 `cmd.list.platform_header` 與修改 `cmd.list.entry`（移除 `{platform}`）
- **C4**: URL decode 使用 `urllib.parse.unquote`，僅影響顯示層

## Success Criteria

- SC1: `/live list` 輸出按平台分組，平台標題獨立一行，頻道以 `- ` 前綴列出
- SC2: 平台區塊間有空行分隔
- SC3: 含 URL 編碼中文的 `display_id` 正確顯示為 Unicode 字元
- SC4: 無頻道的平台不顯示
- SC5: 不影響其他指令（add / remove / check / notify 等）

## Tasks

1. 修改 3 個 i18n JSON：新增 `cmd.list.platform_header`，修改 `cmd.list.entry` 移除 `{platform}`
2. 修改 `main.py:cmd_list`：按平台輸出標題行 + 頻道列表，對 `display_id` 執行 `urllib.parse.unquote`
