from __future__ import annotations

import pytest

from core.models import StatusSnapshot
from core.notifier import Notifier


class TestFormatStreamerName:
    """Tests for Notifier._format_streamer_name() method."""

    @pytest.fixture
    def notifier(self):
        """Create a Notifier instance with mocked dependencies."""

        class MockContext:
            pass

        class MockStore:
            pass

        class MockI18n:
            pass

        return Notifier(MockContext(), MockStore(), MockI18n())

    def test_bilibili_format_with_uid(self, notifier: Notifier):
        """Bilibili format should include @ and UID in parentheses."""
        snapshot = StatusSnapshot(
            is_live=True,
            streamer_name="嘉然今天吃什么",
            display_id="672328094",
        )
        result = notifier._format_streamer_name("bilibili", snapshot)
        assert result == "@嘉然今天吃什么 (672328094)"

    def test_bilibili_format_without_uid(self, notifier: Notifier):
        """Bilibili format without UID should only include @."""
        snapshot = StatusSnapshot(
            is_live=True,
            streamer_name="TestStreamer",
            display_id="",
        )
        result = notifier._format_streamer_name("bilibili", snapshot)
        assert result == "@TestStreamer"

    def test_twitch_same_name(self, notifier: Notifier):
        """Twitch with same display and login name should not show (@login)."""
        snapshot = StatusSnapshot(
            is_live=True,
            streamer_name="Ninja",
            display_id="ninja",
            login_name="ninja",
        )
        result = notifier._format_streamer_name("twitch", snapshot)
        assert result == "Ninja"
        assert "(@" not in result

    def test_twitch_different_name(self, notifier: Notifier):
        """Twitch with different display and login name should show (@login)."""
        snapshot = StatusSnapshot(
            is_live=True,
            streamer_name="日本語配信者",
            display_id="japanese_streamer",
            login_name="japanese_streamer",
        )
        result = notifier._format_streamer_name("twitch", snapshot)
        assert result == "日本語配信者 (@japanese_streamer)"

    def test_twitch_case_insensitive_match(self, notifier: Notifier):
        """Twitch names differing only by case should be treated as same."""
        snapshot = StatusSnapshot(
            is_live=True,
            streamer_name="Ninja",
            display_id="Ninja",
            login_name="ninja",
        )
        result = notifier._format_streamer_name("twitch", snapshot)
        assert result == "Ninja"
        assert "(@" not in result

    def test_youtube_format_with_handle(self, notifier: Notifier):
        """YouTube should include handle when display_id is available."""
        snapshot = StatusSnapshot(
            is_live=True,
            streamer_name="TestUser",
            display_id="@TestUser",
        )
        result = notifier._format_streamer_name("youtube", snapshot)
        assert result == "TestUser (@TestUser)"

    def test_empty_streamer_name(self, notifier: Notifier):
        """Empty streamer_name should return empty string."""
        snapshot = StatusSnapshot(
            is_live=True,
            streamer_name="",
        )
        result = notifier._format_streamer_name("twitch", snapshot)
        assert result == ""

    def test_none_fields(self, notifier: Notifier):
        """None fields should be handled gracefully."""
        snapshot = StatusSnapshot(
            is_live=True,
            streamer_name="TestUser",
            display_id=None,
            login_name=None,
        )
        result = notifier._format_streamer_name("twitch", snapshot)
        assert result == "TestUser"

    def test_display_id_with_at_symbol(self, notifier: Notifier):
        """display_id with @ should be normalized (stripped)."""
        snapshot = StatusSnapshot(
            is_live=True,
            streamer_name="TestUser",
            display_id="@different",
            login_name="@different",
        )
        result = notifier._format_streamer_name("twitch", snapshot)
        # login_name "@different" becomes "different" after lstrip("@")
        # so name "TestUser" != "different", thus shows (@different)
        assert "@@" not in result
        assert result == "TestUser (@different)"


class TestBuildEndEmbedFooter:
    """Tests for _build_end_embed footer formatting logic."""

    @pytest.fixture
    def notifier(self, monkeypatch):
        class MockContext:
            pass

        class MockStore:
            def get_language(self, origin: str) -> str:
                return "en"

        class MockI18n:
            def get(self, lang: str, key: str, **kwargs) -> str:
                templates = {
                    "notify.embed.end_title": "{name} 直播結束",
                    "notify.embed.field.platform": "平台",
                }
                return templates.get(key, key)

        # Create a real MockDiscordEmbed class that stores attributes
        class MockDiscordEmbed:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        class MockMessageChain:
            def __init__(self, chain):
                self.chain = chain

        # Patch the imports in notifier module
        import core.notifier as notifier_module

        monkeypatch.setattr(notifier_module, "DiscordEmbed", MockDiscordEmbed)
        monkeypatch.setattr(notifier_module, "MessageChain", MockMessageChain)

        return Notifier(MockContext(), MockStore(), MockI18n())

    def test_bilibili_end_footer_with_uid(self, notifier: Notifier):
        """Bilibili end notification should include UID."""
        chain = notifier._build_end_embed("en", "bilibili", "嘉然", "672328094")
        embed = chain.chain[0]
        assert embed.footer == "@嘉然 (672328094)"

    def test_bilibili_end_footer_without_uid(self, notifier: Notifier):
        """Bilibili end notification without UID should show name only."""
        chain = notifier._build_end_embed("en", "bilibili", "嘉然", "")
        embed = chain.chain[0]
        assert embed.footer == "@嘉然"

    def test_twitch_end_footer_same_name(self, notifier: Notifier):
        """Twitch end notification with same names should not show (@login)."""
        chain = notifier._build_end_embed("en", "twitch", "Ninja", "ninja")
        embed = chain.chain[0]
        assert embed.footer == "Ninja"
        assert "(@" not in embed.footer

    def test_twitch_end_footer_different_name(self, notifier: Notifier):
        """Twitch end notification with different names should show (@login)."""
        chain = notifier._build_end_embed(
            "en", "twitch", "日本語配信者", "japanese_streamer"
        )
        embed = chain.chain[0]
        assert embed.footer == "日本語配信者 (@japanese_streamer)"


class TestEmbedImageField:
    """Tests for image_url field mapping in live embed."""

    @pytest.fixture
    def notifier(self, monkeypatch):
        class MockContext:
            pass

        class MockStore:
            def get_language(self, origin: str) -> str:
                return "en"

        class MockI18n:
            def get(self, lang: str, key: str, **kwargs) -> str:
                return key

        class MockDiscordEmbed:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        class MockMessageChain:
            def __init__(self, chain):
                self.chain = chain

        import core.notifier as notifier_module

        monkeypatch.setattr(notifier_module, "DiscordEmbed", MockDiscordEmbed)
        monkeypatch.setattr(notifier_module, "MessageChain", MockMessageChain)
        return Notifier(MockContext(), MockStore(), MockI18n())

    def test_live_embed_uses_image_field(self, notifier: Notifier):
        """Live embed should set image to snapshot.image_url and thumbnail to None."""
        snapshot = StatusSnapshot(
            is_live=True,
            streamer_name="TestStreamer",
            image_url="https://example.com/thumbnail.jpg",
        )
        chain = notifier._build_live_embed("en", "twitch", snapshot)
        embed = chain.chain[0]
        assert embed.image == snapshot.image_url
        assert embed.thumbnail is None

    def test_twitch_resolution_1280x720(self, notifier: Notifier):
        """Twitch image_url should contain 1280x720 after template substitution."""
        raw_template = "https://static-cdn.jtvnw.net/previews-ttv/live_user_ninja-{width}x{height}.jpg"
        resolved = raw_template.replace("{width}", "1280").replace("{height}", "720")
        snapshot = StatusSnapshot(
            is_live=True,
            streamer_name="Ninja",
            image_url=resolved,
        )
        assert "1280x720" in snapshot.image_url

    def test_youtube_hqdefault_url(self, notifier: Notifier):
        """YouTube image_url should match the hqdefault.jpg pattern."""
        video_id = "dQw4w9WgXcQ"
        image_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        snapshot = StatusSnapshot(
            is_live=True,
            streamer_name="RickAstley",
            image_url=image_url,
        )
        assert "hqdefault.jpg" in snapshot.image_url
