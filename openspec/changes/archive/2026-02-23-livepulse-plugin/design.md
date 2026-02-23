## Context

LivePulse is a new AstrBot plugin that monitors live stream status across YouTube, Twitch, and Bilibili. The codebase currently contains only a template `main.py` (helloworld plugin) and `metadata.yaml`. This is a greenfield implementation.

The plugin operates within the AstrBot Star framework, which constrains:
- Entry class must inherit `Star` with `@register()` decorator in `main.py`
- Commands use `@filter.command_group()` / `@group.command()` decorators
- Async-only I/O (`aiohttp`, no `requests`)
- Persistent data stored in `~/.astrbot/` (not plugin directory)
- Configuration via `_conf_schema.json` + `AstrBotConfig` injection
- Active messages via `self.context.send_message(unified_msg_origin, MessageChain)`

## Goals / Non-Goals

**Goals:**
- Multi-platform live stream monitoring (YouTube, Twitch, Bilibili) with per-group isolation
- Extensible platform architecture via abstract base class
- Reliable notification delivery with deduplication and auto-disable on persistent failures
- Atomic JSON persistence with crash recovery
- i18n support (en/zh) with fallback mechanism

**Non-Goals:**
- SQLite or database persistence (JSON is sufficient for MVP)
- Per-group polling interval overrides (removed per user decision; global-only)
- Permission management (all commands open to all users)
- VOD/replay detection or recording
- Integration with AstrBot's LLM pipeline
- Support for platforms beyond YouTube/Twitch/Bilibili

## Decisions

### D1: Module Structure — Sub-directory layout

```
astrbot_plugin_livepulse/
├── main.py                    # AstrBot entry: @register, command group, lifecycle
├── metadata.yaml
├── requirements.txt
├── _conf_schema.json
├── platforms/
│   ├── __init__.py
│   ├── base.py                # BasePlatformChecker ABC
│   ├── youtube.py             # YouTube HTML scraper + @handle resolver
│   ├── twitch.py              # Twitch Helix API + OAuth token manager
│   └── bilibili.py            # Bilibili batch API
├── core/
│   ├── __init__.py
│   ├── models.py              # Dataclasses: GroupState, MonitorEntry, StatusSnapshot
│   ├── store.py               # In-memory state + asyncio.Lock + snapshot API
│   ├── persistence.py         # JSON load/save, atomic write, schema migration
│   ├── poller.py              # Per-platform poll loop orchestration
│   └── notifier.py            # Notification dispatch + failure tracking + auto-disable
└── i18n/
    ├── __init__.py             # I18nManager: key lookup with fallback
    ├── en.json
    └── zh.json
```

**Rationale**: The plugin has 3 distinct platform implementations, a polling engine, persistence logic, and i18n — too much for a single file. Sub-directories group related concerns. `main.py` remains the AstrBot-mandated entry point, delegating to modules.

**Alternative considered**: Flat structure with all modules in root. Rejected because 10+ files in root becomes hard to navigate, and platform logic benefits from grouping.

### D2: Platform Abstraction — BasePlatformChecker ABC

```python
class BasePlatformChecker(ABC):
    platform_name: str  # "youtube" | "twitch" | "bilibili"

    @abstractmethod
    async def check_status(self, channel_ids: list[str], session: ClientSession) -> dict[str, StatusSnapshot]:
        """Check live status for a batch of channel IDs. Returns {channel_id: StatusSnapshot}."""

    @abstractmethod
    async def validate_channel(self, channel_id: str, session: ClientSession) -> ChannelInfo | None:
        """Validate and resolve a channel identifier. Returns None if invalid."""
```

Each platform implements `check_status` (batch where possible) and `validate_channel` (used by `/live add`). The poller calls `check_status` without knowing platform internals.

**Rationale**: Uniform interface enables the poller to treat all platforms identically. Adding a new platform requires only implementing the ABC + registering it.

**Alternative considered**: Duck typing with no base class. Rejected because explicit interface prevents accidental omission of required methods.

### D3: State Management — asyncio.Lock + Immutable Snapshots

The `Store` class holds all runtime state in memory:
- `groups: dict[str, GroupState]` — keyed by `unified_msg_origin`
- `reverse_index: dict[str, dict[str, set[str]]]` — `{platform: {channel_id: {group_origins}}}` for dedup

**Concurrency model**:
- **Reads (pollers)**: `store.snapshot(platform)` returns a frozen copy of channel IDs and their subscribing groups. No lock held during polling.
- **Writes (commands, poller state updates)**: `async with store.lock:` serializes all mutations.
- The lock is an `asyncio.Lock` (single-threaded event loop, no threading needed).

**Rationale**: Pollers run long I/O operations; holding a lock during HTTP calls would serialize all platforms. Snapshot-then-update avoids this.

**Alternative considered**: No lock, relying on GIL. Rejected because `await` points in async code can interleave coroutines, causing lost updates.

### D4: Persistence — JSON with Atomic Write + Single Writer

```python
# Atomic write pattern
async def save(self, state: dict) -> None:
    tmp = self.path.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    os.replace(str(tmp), str(self.path))
```

- **Single writer**: All persistence goes through `Store.persist()`, which is called under the lock.
- **Schema versioning**: Top-level `"schema_version": 1` field. Migration functions keyed by version number.
- **Crash recovery**: If `data.json` fails to parse, attempt `data.json.bak`. If both fail, start empty and log warning.
- **Backup**: Before each save, copy current file to `.bak`.
- **Data directory**: `~/.astrbot/livepulse/`

**Rationale**: JSON is human-readable, zero-dependency, and sufficient for the expected data volume (500 channels max). Atomic write via `os.replace` is POSIX-atomic.

**Alternative considered**: SQLite. Better concurrency and queryability, but adds complexity for a plugin of this scale.

### D5: Polling Architecture — Per-Platform with Dedup + Fanout

```
Plugin.initialize()
├── youtube_poller_task  (interval: config.youtube_interval)
├── twitch_poller_task   (interval: config.twitch_interval)
└── bilibili_poller_task (interval: config.bilibili_interval)

Each poller cycle:
1. snapshot = store.snapshot(platform)         # {channel_id: set[group_origins]}
2. unique_ids = list(snapshot.keys())          # deduplicated
3. statuses = checker.check_status(unique_ids) # batch query
4. for channel_id, status in statuses:
     for group_origin in snapshot[channel_id]:
       transition = compute_transition(group_origin, channel_id, status)
       if transition: notifier.enqueue(group_origin, transition)
5. async with store.lock: store.apply_status_updates(...)
6. store.persist()
7. await asyncio.sleep(effective_interval)
```

**Deduplication**: The reverse index ensures each channel is queried once per cycle regardless of how many groups subscribe to it.

**Effective interval**: Global config only (per-group overrides removed). Backoff multiplier applied on rate limit or consecutive errors.

**Auto-restart**: Each poller is wrapped in a supervisor loop that catches unhandled exceptions and restarts after exponential backoff (base=30s, mult=2, max=300s).

### D6: Notification Dispatch — Notifier with Failure Tracking

The `Notifier` class handles:
1. **Message formatting**: Build `MessageChain` with text + optional `Comp.Image.fromURL()`.
2. **Delivery**: Call `self.context.send_message(origin, chain)`.
3. **Image fallback**: On image send failure, retry with text-only chain.
4. **Failure counter**: Per-group `consecutive_failures` counter. Incremented on `send_message` exception, reset on success.
5. **Auto-disable**: When counter reaches 10, set `group.notify_enabled = False` and log.

**Effective notification rule**: `config.enable_notifications AND group.notify_enabled` must both be true. For end notifications, additionally `config.enable_end_notifications AND group.end_notify_enabled`.

### D7: Twitch OAuth Token Manager

Encapsulated in `TwitchChecker`:
- Obtain token via `POST https://id.twitch.tv/oauth2/token` (Client Credentials grant).
- Store `access_token` and `expires_at` in memory (not persisted — tokens are short-lived).
- Refresh when `now >= expires_at - 300s`.
- On 401 response: refresh token and retry once. If retry fails, mark channels as `unknown`.
- Single-flight refresh: use an `asyncio.Lock` to prevent concurrent refresh requests.

### D8: YouTube @handle Resolution

On `/live add youtube @handle`:
1. `GET https://www.youtube.com/@handle` — follow redirect to canonical URL.
2. Extract Channel ID from page metadata or canonical URL pattern.
3. Store the resolved `UCxxxxx` ID permanently. All polling uses the ID only.
4. If resolution fails, reject the add command with an error.

Cache is not needed since resolution happens only at add time, not during polling.

### D9: i18n Architecture

```python
class I18nManager:
    def __init__(self, i18n_dir: Path):
        self.strings: dict[str, dict[str, str]] = {}  # {locale: {key: value}}
        # Load en.json and zh.json at init

    def get(self, locale: str, key: str, **kwargs) -> str:
        text = self.strings.get(locale, {}).get(key)
        if text is None:
            text = self.strings["en"].get(key, f"[{key}]")  # fallback to en
        return text.format(**kwargs) if kwargs else text
```

Keys follow pattern: `cmd.add.success`, `cmd.add.duplicate`, `notify.live_start`, `notify.live_end`, `error.limit_reached`, etc.

### D10: Data Model

```python
@dataclass
class MonitorEntry:
    channel_id: str          # canonical ID (UCxxxxx / username / UID)
    channel_name: str        # display name from API
    last_status: str         # "live" | "offline" | "unknown"
    last_stream_id: str      # platform-specific session identifier for dedup
    initialized: bool        # False until first poll (suppresses first notification)

@dataclass
class GroupState:
    language: str            # "en" | "zh"
    notify_enabled: bool     # True by default
    end_notify_enabled: bool # True by default
    monitors: dict[str, dict[str, MonitorEntry]]  # {platform: {channel_id: entry}}
    send_failure_count: int  # consecutive send_message failures

@dataclass
class StatusSnapshot:
    is_live: bool
    stream_id: str           # unique session identifier
    title: str
    category: str            # game_name for Twitch, empty for others
    thumbnail_url: str
    streamer_name: str
    stream_url: str          # direct link to stream
```

### D11: AstrBot Integration Points

- **`__init__(self, context, config)`**: Store config, instantiate Store, I18nManager, platform checkers.
- **`initialize()`**: Load persisted data, create aiohttp.ClientSession, start poller tasks.
- **`terminate()`**: Cancel all poller tasks (await them), close ClientSession, flush persistence. Idempotent guard via `self._terminated` flag.
- **Command group**: `@filter.command_group("live")` in `main.py`, with `@live.command("add")`, etc.
- **Active messages**: `await self.context.send_message(origin, chain)` for notifications.

## Risks / Trade-offs

| Risk | Severity | Mitigation |
|------|----------|------------|
| YouTube HTML structure changes break scraper | High | Multi-signal detection (`"isLive":true`, `hqdefault_live.jpg`, page metadata). Treat parse failure as `unknown`, not offline. Log warnings for monitoring. |
| Twitch OAuth token stampede on mass 401 | Medium | Single-flight refresh lock. Only one refresh in-flight at a time. |
| JSON corruption on crash during write | Medium | Atomic write via temp file + `os.replace`. Backup file before each save. Fallback to `.bak` on load failure. |
| YouTube rate limiting / IP blocking | Medium | Conservative 300s default interval. Fixed modern User-Agent. Exponential backoff on block detection. |
| Memory growth with many groups | Low | Global cap of 500 unique channels. Reverse index avoids O(groups * channels) scans. Auto-disable stale groups. |
| Plugin hot-reload creates duplicate pollers | Medium | Idempotent `terminate()` cancels all tasks. `initialize()` guard prevents double-start. |
| Bilibili API returns partial batch results | Medium | Treat missing UIDs as `unknown`. Never infer offline from absence. |
