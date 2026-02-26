# Changelog

## v1.1.3 (2026-02-26)

### ✨ New Features

- **Batch add/remove channels**: support multiple channel IDs in `/live add` and `/live remove` commands
- **URL auto-detect platform**: automatically detect platform from URL in `/live add` and `/live remove`
- **Platform-specific username formatting**: show @username for Twitch/YouTube, 暱稱 (@ID) for Bilibili

### 🧪 Tests

- Add unit and integration tests for batch processing

### 📝 Documentation

- Add Twitch app registration guide with 2FA note
- Add supported channel ID formats table and Bilibili URL example
- Reorder credential notes and upgrade Twitch 2FA callout level

### 🎨 Style

- Format codebase with ruff

---

## v1.1.2 (2026-02-25)

### ✨ New Features

- **Redesign Discord embed**: show streamer name in embed title, use emoji-prefixed fields for stream details, and add footer with platform info

---

## v1.1.1 (2026-02-25)

### 🐛 Bug Fixes

- Fix Discord embed construction failing due to pydantic v1 `__setattr__` rejecting undeclared fields on `DiscordEmbed`

---

## v1.1.0 (2026-02-24)

### ✨ New Features

- **Discord embed notifications**: live events now use Discord embed format for richer notification display
- **Test notification command**: add `/test_notify` command to preview notification appearance

### 🐛 Bug Fixes

- Add error logging for silent notification failures in test_notify

---

## v1.0.0 (2026-02-24)

### ✨ New Features

- **Multi-platform live stream monitoring**: support YouTube, Twitch, and Bilibili live detection and notifications
- **Group live list by platform**: list output grouped by platform with decoded display_id
- **Quick notification query**: view current notification settings with no arguments
- **Live status emoji**: show status emoji and display_id in list, immediate check on add
- **Separate zh-Hans / zh-Hant**: split zh locale into zh-Hans and zh-Hant using IETF locale tags

### 🐛 Bug Fixes

- Fix Bilibili / YouTube channel validation and live detection logic
- Add shared UA header, fix YouTube block detection, surface rate limit errors
- Move DEFAULT_USER_AGENT to base.py to fix plugin import issue
- Inline UA strings to avoid sys.modules cache issue
- Use MessageChain instead of raw list for notification delivery
