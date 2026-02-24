# Changelog

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
