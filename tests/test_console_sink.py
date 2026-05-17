"""Tests for ConsoleSink: stdout/stderr routing, color, format."""

import re

import pytest

from multilog import ConsoleSink, LogLevel


def _payload(level: str, message: str = "hi", **extra):
    return {
        "timestamp_ms": 1_700_000_000_000,
        "message": message,
        "level": level,
        **extra,
    }


class TestStreamRouting:
    @pytest.mark.parametrize("level", ["trace", "debug", "info"])
    def test_low_levels_go_to_stdout(self, capsys, level):
        ConsoleSink(use_color=False)._emit(_payload(level))
        captured = capsys.readouterr()
        assert captured.out != ""
        assert captured.err == ""

    @pytest.mark.parametrize("level", ["warn", "error", "fatal"])
    def test_high_levels_go_to_stderr(self, capsys, level):
        ConsoleSink(use_color=False)._emit(_payload(level))
        captured = capsys.readouterr()
        assert captured.err != ""
        assert captured.out == ""


class TestColor:
    def test_color_off_has_no_ansi(self, capsys):
        ConsoleSink(use_color=False)._emit(_payload("info"))
        out = capsys.readouterr().out
        assert "\033[" not in out

    def test_color_on_wraps_level_in_ansi(self, capsys):
        ConsoleSink(use_color=True)._emit(_payload("info"))
        out = capsys.readouterr().out
        # INFO color is green (32), reset (0) is at end of the level span.
        assert "\033[32m" in out
        assert "\033[0m" in out

    def test_each_level_has_distinct_color(self, capsys):
        sink = ConsoleSink(use_color=True)
        for level in LogLevel:
            sink._emit(_payload(level.value))
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        # All six ANSI color escapes used by the sink.
        for code in ("90", "36", "32", "33", "31", "35"):
            assert f"\033[{code}m" in combined, f"missing color {code}"


class TestFormatting:
    def test_timestamp_format_is_iso_with_ms(self, capsys):
        ConsoleSink(use_color=False)._emit(_payload("info"))
        out = capsys.readouterr().out
        # YYYY-MM-DD HH:MM:SS.mmm at start
        assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}  ", out)

    def test_level_padded_to_5_chars(self, capsys):
        ConsoleSink(use_color=False)._emit(_payload("info"))
        out = capsys.readouterr().out
        # "INFO " (5 chars) — INFO is 4, padded to 5 with one trailing space.
        assert "  INFO   hi" in out

    def test_context_appended_as_json(self, capsys):
        ConsoleSink(use_color=False)._emit(_payload("info", user_id=42))
        out = capsys.readouterr().out
        assert '{"user_id": 42}' in out

    def test_no_context_section_when_empty(self, capsys):
        ConsoleSink(use_color=False)._emit(_payload("info"))
        out = capsys.readouterr().out
        # No trailing JSON object after the message.
        assert not out.rstrip().endswith("}")
