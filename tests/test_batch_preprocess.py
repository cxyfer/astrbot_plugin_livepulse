from __future__ import annotations

import pytest

from core.batch import preprocess, detect_mode, BatchItem, MAX_BATCH_SIZE


# --- helpers ---

_VALID_PLATFORMS = ("youtube", "twitch", "bilibili")


def _detect_platform(raw: str) -> str | None:
    from urllib.parse import urlparse
    _HOST_MAP = {
        "youtube.com": "youtube", "www.youtube.com": "youtube", "m.youtube.com": "youtube",
        "twitch.tv": "twitch", "www.twitch.tv": "twitch", "m.twitch.tv": "twitch",
        "live.bilibili.com": "bilibili",
    }
    url = raw if "://" in raw else f"https://{raw}"
    try:
        host = urlparse(url).hostname
    except ValueError:
        return None
    if host is None:
        return None
    return _HOST_MAP.get(host.lower())


# ===== 6.1 preprocess tests =====

class TestPreprocess:
    def test_dedup_preserves_order(self):
        items = [BatchItem("twitch", "a"), BatchItem("twitch", "b"), BatchItem("twitch", "a")]
        result, trunc = preprocess(items)
        assert [i.identifier for i in result] == ["a", "b"]
        assert trunc == 0

    def test_truncation(self):
        items = [BatchItem("twitch", str(i)) for i in range(25)]
        result, trunc = preprocess(items)
        assert len(result) == MAX_BATCH_SIZE
        assert trunc == 5

    def test_dedup_before_truncation(self):
        items = [BatchItem("twitch", str(i % 18)) for i in range(30)]
        result, trunc = preprocess(items)
        assert len(result) == 18
        assert trunc == 0

    def test_empty_input(self):
        result, trunc = preprocess([])
        assert result == []
        assert trunc == 0

    def test_single_input(self):
        items = [BatchItem("twitch", "foo")]
        result, trunc = preprocess(items)
        assert len(result) == 1
        assert result[0].identifier == "foo"
        assert trunc == 0

    def test_cross_platform_no_dedup(self):
        items = [BatchItem("twitch", "foo"), BatchItem("youtube", "foo")]
        result, trunc = preprocess(items)
        assert len(result) == 2
        assert trunc == 0


# ===== 6.2 detect_mode tests =====

class TestDetectMode:
    def test_platform_id_single(self):
        mode, items = detect_mode(["twitch", "wpnebula"], _VALID_PLATFORMS, _detect_platform)
        assert mode == "platform_id"
        assert len(items) == 1
        assert items[0] == BatchItem("twitch", "wpnebula")

    def test_platform_id_multiple(self):
        mode, items = detect_mode(["twitch", "a", "b", "c"], _VALID_PLATFORMS, _detect_platform)
        assert mode == "platform_id"
        assert len(items) == 3

    def test_url_single(self):
        mode, items = detect_mode(["https://www.twitch.tv/wpnebula"], _VALID_PLATFORMS, _detect_platform)
        assert mode == "url"
        assert len(items) == 1
        assert items[0].platform == "twitch"

    def test_url_multiple(self):
        urls = ["https://www.twitch.tv/a", "https://www.youtube.com/c/b"]
        mode, items = detect_mode(urls, _VALID_PLATFORMS, _detect_platform)
        assert mode == "url"
        assert len(items) == 2

    def test_mixed_mode_platform_then_url(self):
        with pytest.raises(ValueError, match="mixed_mode"):
            detect_mode(["twitch", "a", "https://www.twitch.tv/b"], _VALID_PLATFORMS, _detect_platform)

    def test_mixed_mode_url_then_platform_id(self):
        with pytest.raises(ValueError, match="mixed_mode"):
            detect_mode(["https://www.twitch.tv/a", "someid"], _VALID_PLATFORMS, _detect_platform)

    def test_invalid_platform(self):
        with pytest.raises(ValueError, match="unknown"):
            detect_mode(["invalid_thing"], _VALID_PLATFORMS, _detect_platform)

    def test_platform_no_ids(self):
        with pytest.raises(ValueError, match="no_ids"):
            detect_mode(["twitch"], _VALID_PLATFORMS, _detect_platform)

    def test_case_insensitive_platform(self):
        mode, items = detect_mode(["Twitch", "foo"], _VALID_PLATFORMS, _detect_platform)
        assert mode == "platform_id"
        assert items[0].platform == "twitch"

    def test_bare_url_in_platform_mode_rejected(self):
        with pytest.raises(ValueError, match="mixed_mode"):
            detect_mode(["twitch", "foo", "unknown-site.com/bar"], _VALID_PLATFORMS, _detect_platform)
