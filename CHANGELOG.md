# Changelog

## v1.1.7 (2026-03-16)

### 🐛 Bug Fixes

- **Image setting persistence**: preserve the saved notification image toggle across plugin updates by migrating legacy `include_thumbnail` values to `include_image`

### ♻️ Refactoring

- **Image field**: rename `thumbnail_url` to `image_url` and upgrade live stream notification image quality for Discord embeds and platform snapshots

---

## v1.1.6 (2026-03-01)

### 🐛 Bug Fixes

- **Channel name formatting**: restore `@handle` display for YouTube channels and fix Twitch fallback to use `login_name` or `display_id` when display name differs

---

## v1.1.5 (2026-02-27)

### 🐛 Bug Fixes

- **Legacy loader compatibility**: make `config` param optional to support AstrBot's legacy plugin loader (context-only invocation)
- **Lifecycle cleanup**: wrap `initialize()` in try/except to clean up resources on failure; move `_initialized` flag assignment after all side effects to allow safe retry
- **Task cleanup**: replace manual cancel/await loops with `asyncio.gather(*tasks, return_exceptions=True)` in both failure path and `terminate()`
- **Argument parsing**: unify `notify`/`end_notify` commands to use `_parse_batch_args` for consistent batch handling

### ⚡️ Performance

- **YouTube concurrent checks**: add semaphore-limited concurrent requests to avoid sequential bottleneck
- **Bilibili rate limit**: handle HTTP 429 with `RateLimitError` propagation
- **Channel-level backoff**: track per-channel failures and apply exponential backoff in poller

### 🧪 Tests

- Add unit tests covering argument parsing, lifecycle failure/retry, channel backoff, Bilibili 429 handling, and YouTube concurrency

### ♻️ Refactoring

- **Storage API**: replace `get_astrbot_data_path()` with `StarTools.get_data_dir` public API

---

## v1.1.4 (2026-02-27)

### ♻️ Refactoring

- **Storage migration**: replace hardcoded `~/.astrbot/livepulse` path with `get_astrbot_data_path() / plugin_data / self.name`; auto-migrate legacy data on startup

### 📝 Documentation

- Add batch add/remove examples and clarify command syntax in README
- Fix license badge and link to match AGPL-3.0

---

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
