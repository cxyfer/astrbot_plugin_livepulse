from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from core.models import ChannelInfo
from platforms.base import RateLimitError

MAX_BATCH_SIZE = 20
_SEM_LIMIT = 5


@dataclass
class BatchItem:
    platform: str
    identifier: str


@dataclass
class BatchResultItem:
    identifier: str
    status: str
    platform: str = ""
    info: ChannelInfo | None = None
    error_key: str | None = None


@dataclass
class BatchResult:
    items: list[BatchResultItem] = field(default_factory=list)
    truncated: int = 0


def preprocess(items: list[BatchItem], max_size: int = MAX_BATCH_SIZE) -> tuple[list[BatchItem], int]:
    seen: set[str] = set()
    unique: list[BatchItem] = []
    for item in items:
        key = f"{item.platform}:{item.identifier}"
        if key not in seen:
            seen.add(key)
            unique.append(item)
    truncated = max(0, len(unique) - max_size)
    return unique[:max_size], truncated


def _looks_like_url(arg: str) -> bool:
    return "://" in arg or ("." in arg and "/" in arg)


def detect_mode(
    args: list[str],
    valid_platforms,
    detect_platform_from_url,
) -> tuple[str, list[BatchItem]]:
    first = args[0]

    if first.lower() in valid_platforms:
        platform = first.lower()
        ids = args[1:]
        if not ids:
            raise ValueError("no_ids")
        for a in ids:
            if _looks_like_url(a) or detect_platform_from_url(a) is not None:
                raise ValueError("mixed_mode")
        return "platform_id", [BatchItem(platform=platform, identifier=i) for i in ids]

    detected = detect_platform_from_url(first)
    if detected is not None:
        items: list[BatchItem] = []
        for a in args:
            p = detect_platform_from_url(a)
            if p is None:
                raise ValueError("mixed_mode")
            items.append(BatchItem(platform=p, identifier=a))
        return "url", items

    raise ValueError("unknown")


async def process_batch_add(
    store, origin: str, items: list[BatchItem],
    checkers: dict, session,
    max_per_group: int, max_global: int,
) -> BatchResult:
    sem = asyncio.Semaphore(_SEM_LIMIT)

    async def validate_one(item: BatchItem):
        checker = checkers.get(item.platform)
        if checker is None:
            return item, None, ValueError("no_checker")
        async with sem:
            try:
                return item, await checker.validate_channel(item.identifier, session), None
            except Exception as e:
                return item, None, e

    raw = await asyncio.gather(*(validate_one(it) for it in items), return_exceptions=True)

    success_pairs: list[tuple[str, ChannelInfo]] = []
    success_indices: list[int] = []
    results: list[BatchResultItem] = []

    for i, r in enumerate(raw):
        ident = items[i].identifier
        plat = items[i].platform
        if isinstance(r, BaseException):
            results.append(BatchResultItem(ident, "internal_error", platform=plat, error_key="cmd.batch.item_fail"))
            continue
        _, info, exc = r
        if exc is not None:
            status = "rate_limited" if isinstance(exc, RateLimitError) else "internal_error"
            results.append(BatchResultItem(ident, status, platform=plat, error_key="cmd.batch.item_fail"))
        elif info is None:
            results.append(BatchResultItem(ident, "not_found", platform=plat, error_key="cmd.batch.item_not_found"))
        else:
            success_pairs.append((items[i].platform, info))
            success_indices.append(i)
            results.append(BatchResultItem(ident, "pending", platform=plat, info=info))

    if success_pairs:
        store_results = await store.add_monitors_batch(origin, success_pairs, max_per_group, max_global)
        for j, err in enumerate(store_results):
            idx = success_indices[j]
            if err is None:
                results[idx].status = "success"
            elif "duplicate" in err:
                results[idx].status = "duplicate"
                results[idx].error_key = "cmd.batch.item_duplicate"
            elif "limit_group" in err:
                results[idx].status = "limit_group"
                results[idx].error_key = "cmd.batch.item_limit_group"
            elif "limit_global" in err:
                results[idx].status = "limit_global"
                results[idx].error_key = "cmd.batch.item_limit_global"

    return BatchResult(items=results)


async def process_batch_remove(
    store, origin: str, items: list[BatchItem],
    checkers: dict, session,
) -> BatchResult:
    sem = asyncio.Semaphore(_SEM_LIMIT)
    results: list[BatchResultItem] = [None] * len(items)  # type: ignore[list-item]
    remove_pairs: list[tuple[int, str, str]] = []  # (original_index, platform, channel_id)
    pending_network: list[int] = []

    for i, item in enumerate(items):
        checker = checkers.get(item.platform)
        is_url = "://" in item.identifier or ("." in item.identifier and "/" in item.identifier)

        if is_url:
            extracted = checker.extract_id_from_url(item.identifier) if checker else ""
            if extracted:
                cid = _resolve_local(store, origin, item.platform, extracted)
                remove_pairs.append((i, item.platform, cid))
            elif checker:
                pending_network.append(i)
            else:
                results[i] = BatchResultItem(item.identifier, "not_found", platform=item.platform, error_key="cmd.batch.item_not_found")
        else:
            cid = _resolve_local(store, origin, item.platform, item.identifier)
            remove_pairs.append((i, item.platform, cid))

    if pending_network:
        async def resolve(idx: int):
            item = items[idx]
            checker = checkers[item.platform]
            async with sem:
                try:
                    info = await checker.validate_channel(item.identifier, session)
                    return idx, info.channel_id if info else None, None
                except Exception as e:
                    return idx, None, e

        resolved = await asyncio.gather(*(resolve(idx) for idx in pending_network))
        for idx, cid, exc in resolved:
            if exc is not None:
                status = "rate_limited" if isinstance(exc, RateLimitError) else "internal_error"
                results[idx] = BatchResultItem(items[idx].identifier, status, platform=items[idx].platform, error_key="cmd.batch.item_fail")
            elif cid:
                remove_pairs.append((idx, items[idx].platform, cid))
            else:
                results[idx] = BatchResultItem(items[idx].identifier, "not_found", platform=items[idx].platform, error_key="cmd.batch.item_not_found")

    if remove_pairs:
        ordered = sorted(remove_pairs, key=lambda x: x[0])
        store_items = [(p, cid) for _, p, cid in ordered]
        store_results = await store.remove_monitors_batch(origin, store_items)
        for (orig_idx, _, _), removed in zip(ordered, store_results):
            if removed:
                results[orig_idx] = BatchResultItem(items[orig_idx].identifier, "removed", platform=items[orig_idx].platform)
            else:
                results[orig_idx] = BatchResultItem(items[orig_idx].identifier, "not_found", platform=items[orig_idx].platform, error_key="cmd.batch.item_not_found")

    return BatchResult(items=results)


def _resolve_local(store, origin: str, platform: str, identifier: str) -> str:
    gs = store.get_group(origin)
    if gs:
        plat = gs.monitors.get(platform, {})
        if identifier in plat:
            return identifier
        fallback = store.lookup_by_display_id(origin, platform, identifier)
        if fallback:
            return fallback
    return identifier
