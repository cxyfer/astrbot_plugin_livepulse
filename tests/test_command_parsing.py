"""Task 1.4: notify / end_notify argument parsing via _parse_batch_args."""
from __future__ import annotations

from unittest.mock import MagicMock


def _make_event(message_str: str) -> MagicMock:
    ev = MagicMock()
    ev.message_str = message_str
    return ev


class TestParseBatchArgs:
    def setup_method(self):
        from main import LivePulsePlugin

        self.plugin = object.__new__(LivePulsePlugin)

    def _parse(self, subcommand: str, message: str) -> list[str]:
        return self.plugin._parse_batch_args(_make_event(message), subcommand)

    def test_notify_on(self):
        assert self._parse("notify", "live notify on") == ["on"]

    def test_notify_off(self):
        assert self._parse("notify", "live notify off") == ["off"]

    def test_notify_no_arg(self):
        assert self._parse("notify", "live notify") == []

    def test_notify_invalid_arg_preserved(self):
        assert self._parse("notify", "live notify foo") == ["foo"]

    def test_notify_slash_prefix(self):
        assert self._parse("notify", "/live notify on") == ["on"]

    def test_end_notify_on(self):
        assert self._parse("end_notify", "live end_notify on") == ["on"]

    def test_end_notify_off(self):
        assert self._parse("end_notify", "live end_notify off") == ["off"]

    def test_end_notify_no_arg(self):
        assert self._parse("end_notify", "live end_notify") == []

    def test_end_notify_slash_prefix(self):
        assert self._parse("end_notify", "/live end_notify off") == ["off"]

    def test_case_insensitive_prefix(self):
        assert self._parse("notify", "Live Notify ON") == ["ON"]

    def test_extra_whitespace(self):
        assert self._parse("notify", "  live notify   on  ") == ["on"]
