## 1. Project Scaffolding

- [x] 1.1 Create directory structure: `platforms/`, `core/`, `i18n/` with `__init__.py` files
- [x] 1.2 Update `metadata.yaml` with plugin name `astrbot_plugin_livepulse`, display name, description, version `v1.0.0`, author, and repo URL
- [x] 1.3 Create `requirements.txt` with `aiohttp>=3.8.0` and `beautifulsoup4>=4.12.0`
- [x] 1.4 Create `_conf_schema.json` with all config fields: `twitch_client_id`, `twitch_client_secret`, `youtube_interval`, `twitch_interval`, `bilibili_interval`, `default_language`, `max_monitors_per_group`, `max_global_channels`, `enable_notifications`, `enable_end_notifications`, `include_thumbnail`, `youtube_timeout`, `twitch_timeout`, `bilibili_timeout`

## 2. Data Models

- [x] 2.1 Implement `core/models.py`: dataclasses `MonitorEntry`, `GroupState`, `StatusSnapshot`, `ChannelInfo`, and `Transition` enum (live_start, live_end)
- [x] 2.2 Implement JSON serialization/deserialization methods for all models (to_dict / from_dict)

## 3. i18n

- [x] 3.1 Implement `i18n/__init__.py` with `I18nManager` class: load JSON files, `get(locale, key, **kwargs)` with en fallback
- [x] 3.2 Create `i18n/en.json` with all message keys: command responses (add/remove/list/check/lang/notify/end_notify/status), notification templates (live_start, live_end), and error messages
- [x] 3.3 Create `i18n/zh.json` with all message keys matching en.json

## 4. Persistence

- [x] 4.1 Implement `core/persistence.py`: `PersistenceManager` with `load()`, `save(state)` using atomic write (temp file + `os.replace`), backup to `.bak` before save
- [x] 4.2 Implement crash recovery: attempt `data.json`, fall back to `data.json.bak`, then empty state
- [x] 4.3 Implement schema versioning: `schema_version` field, migration registry, unknown-version rejection

## 5. State Store

- [x] 5.1 Implement `core/store.py`: `Store` class with `asyncio.Lock`, `groups` dict, and `reverse_index` dict
- [x] 5.2 Implement mutation methods: `add_monitor()`, `remove_monitor()`, `set_language()`, `set_notify()`, `set_end_notify()`, `update_status()`, `increment_failure()`, `reset_failure()`
- [x] 5.3 Implement `snapshot(platform)` method returning frozen copy of `{channel_id: set[group_origins]}` for poller use
- [x] 5.4 Implement `persist()` method that delegates to `PersistenceManager.save()` and maintains reverse index consistency
- [x] 5.5 Implement limit enforcement: per-group max (`max_monitors_per_group`) and global unique channel max (`max_global_channels`)

## 6. Platform Checkers

- [x] 6.1 Implement `platforms/base.py`: `BasePlatformChecker` ABC with abstract methods `check_status(channel_ids, session)` and `validate_channel(channel_id, session)`
- [x] 6.2 Implement `platforms/bilibili.py`: `BilibiliChecker` with batch POST to `get_status_info_by_uids`, chunking at 50 UIDs, partial result handling (missing UID = unknown)
- [x] 6.3 Implement `platforms/twitch.py`: `TwitchChecker` with Helix API `streams` endpoint, OAuth token manager (Client Credentials grant, refresh at expires_at - 300s, single-flight lock, 401 retry)
- [x] 6.4 Implement `platforms/youtube.py`: `YouTubeChecker` with HTML scraping of `/channel/{ID}/live`, multi-signal detection (`"isLive":true`, `hqdefault_live.jpg`), parse failure = unknown status
- [x] 6.5 Implement YouTube `@handle` resolution in `validate_channel()`: fetch `https://www.youtube.com/@handle`, extract Channel ID from redirect/metadata, return resolved `UCxxxxx`

## 7. Notifier

- [x] 7.1 Implement `core/notifier.py`: `Notifier` class with `send_live_notification()` and `send_end_notification()` methods
- [x] 7.2 Implement `MessageChain` construction: text content (name, title, category, link) + `Comp.Image.fromURL(thumbnail)` when `include_thumbnail` is enabled
- [x] 7.3 Implement image fallback: on image send failure, retry with text-only chain (exactly one notification delivered)
- [x] 7.4 Implement effective notification rule: `global_enable AND group_enable` for live-start; additionally `global_end_enable AND group_end_enable` for live-end
- [x] 7.5 Implement failure tracking: per-group `send_failure_count` increment on exception, reset on success, auto-disable at 10 consecutive failures

## 8. Poller Engine

- [x] 8.1 Implement `core/poller.py`: `PlatformPoller` class with supervisor loop (catch exceptions, auto-restart with backoff base=30s, mult=2, max=300s, jitter=±10%)
- [x] 8.2 Implement poll cycle: snapshot → deduplicate → check_status → compute transitions → dispatch notifications → update state → persist → sleep
- [x] 8.3 Implement transition computation: compare new status against `MonitorEntry.last_status` per group, handle first-observation suppression (`initialized=False`)
- [x] 8.4 Implement rate limit detection: HTTP 429 / YouTube block page → platform-level exponential backoff
- [x] 8.5 Implement per-channel error tracking: consecutive failures → per-channel backoff (skip channel until delay expires)

## 9. Command Handlers (main.py)

- [x] 9.1 Rewrite `main.py`: `@register("livepulse", ...)` class with `__init__(self, context, config)`, wire up Store, I18nManager, Notifier, platform checkers
- [x] 9.2 Implement `initialize()`: load persisted data, create shared `aiohttp.ClientSession`, start 3 poller tasks (skip Twitch if credentials missing)
- [x] 9.3 Implement `terminate()`: cancel all poller tasks, await them, close ClientSession, flush persistence; idempotent guard via `_terminated` flag
- [x] 9.4 Implement `@filter.command_group("live")` and `/live add <platform> <channel_id>`: validate platform, call `checker.validate_channel()`, enforce limits, call `store.add_monitor()`, respond with i18n
- [x] 9.5 Implement `/live remove <platform> <channel_id>`: call `store.remove_monitor()`, respond with i18n
- [x] 9.6 Implement `/live list`: iterate group's monitors from store, format with current status and platform, respond with i18n
- [x] 9.7 Implement `/live check <platform> <channel_id>`: one-off `checker.check_status()` call, format result, no state mutation
- [x] 9.8 Implement `/live lang <en|zh>`: validate code, call `store.set_language()`, respond with i18n
- [x] 9.9 Implement `/live notify <on|off>`: call `store.set_notify()`, reset failure counter on enable, respond with i18n
- [x] 9.10 Implement `/live end_notify <on|off>`: call `store.set_end_notify()`, respond with i18n
- [x] 9.11 Implement `/live status`: aggregate poller health, per-platform monitor counts, total unique channels, total groups, respond with i18n

## 10. Integration Testing

- [x] 10.1 Verify full lifecycle: plugin init → add monitors across platforms → pollers detect live/offline transitions → notifications delivered to correct groups → terminate cleans up
- [x] 10.2 Verify group isolation: add same channel in two groups, remove from one, confirm other unaffected
- [x] 10.3 Verify persistence round-trip: add monitors, restart plugin, confirm all state restored
- [x] 10.4 Verify first-observation suppression: add a monitor for an already-live channel, confirm no notification sent
- [x] 10.5 Verify auto-disable: simulate 10 consecutive send failures, confirm group notifications disabled
- [x] 10.6 Verify Twitch credentials missing: start plugin without Twitch config, confirm Twitch poller skipped and `/live add twitch` returns error
- [x] 10.7 Verify i18n: switch group language, confirm all responses use correct locale; test fallback on missing key
