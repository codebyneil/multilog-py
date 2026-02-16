"""Tests for ConsoleSink and RichConsoleSink."""

from io import StringIO

from rich.console import Console

from multilog.sinks.console import ConsoleSink
from multilog.sinks.rich_console import _MULTILOG_THEME, RichConsoleSink

# --- ConsoleSink (plain text) ---


class TestConsoleSinkPlain:
    def test_info_writes_to_stdout(self, capsys):
        sink = ConsoleSink()
        sink._emit({"level": "info", "message": "hello", "timestamp_ms": 1718450096789})
        captured = capsys.readouterr()
        assert "hello" in captured.out
        assert captured.err == ""

    def test_error_writes_to_stderr(self, capsys):
        sink = ConsoleSink()
        sink._emit({"level": "error", "message": "boom", "timestamp_ms": 1718450096789})
        captured = capsys.readouterr()
        assert "boom" in captured.err
        assert captured.out == ""

    def test_warning_writes_to_stderr(self, capsys):
        sink = ConsoleSink()
        sink._emit({"level": "warning", "message": "careful", "timestamp_ms": 1718450096789})
        captured = capsys.readouterr()
        assert "careful" in captured.err

    def test_critical_writes_to_stderr(self, capsys):
        sink = ConsoleSink()
        sink._emit({"level": "critical", "message": "dead", "timestamp_ms": 1718450096789})
        captured = capsys.readouterr()
        assert "dead" in captured.err

    def test_debug_writes_to_stdout(self, capsys):
        sink = ConsoleSink()
        sink._emit({"level": "debug", "message": "dbg", "timestamp_ms": 0})
        captured = capsys.readouterr()
        assert "dbg" in captured.out
        assert captured.err == ""

    def test_no_ansi_codes(self, capsys):
        sink = ConsoleSink()
        sink._emit({"level": "info", "message": "test", "timestamp_ms": 0})
        captured = capsys.readouterr()
        assert "\033[" not in captured.out

    def test_context_appended_as_json(self, capsys):
        sink = ConsoleSink()
        sink._emit({"level": "info", "message": "hi", "timestamp_ms": 0, "user": "alice"})
        captured = capsys.readouterr()
        assert '{"user": "alice"}' in captured.out

    def test_timestamp_format(self, capsys):
        sink = ConsoleSink()
        sink._emit({"level": "info", "message": "ts", "timestamp_ms": 1718450096789})
        captured = capsys.readouterr()
        assert "2024-06-15" in captured.out

    def test_level_fixed_width_8_chars(self, capsys):
        sink = ConsoleSink()
        sink._emit({"level": "info", "message": "test", "timestamp_ms": 0})
        captured = capsys.readouterr()
        assert "INFO    " in captured.out  # 8 chars, left-aligned


# --- RichConsoleSink ---


class TestRichConsoleSink:
    def _make_sink(self, **kwargs):
        """Create a RichConsoleSink with StringIO consoles for testability."""
        sink = RichConsoleSink(**kwargs)
        stdout_buf = StringIO()
        stderr_buf = StringIO()
        sink._stdout_console = Console(
            file=stdout_buf, highlight=False, no_color=True, theme=_MULTILOG_THEME
        )
        sink._stderr_console = Console(
            file=stderr_buf, highlight=False, no_color=True, theme=_MULTILOG_THEME
        )
        return sink, stdout_buf, stderr_buf

    def test_info_writes_to_stdout(self):
        sink, stdout, stderr = self._make_sink()
        sink._emit({"level": "info", "message": "hello", "timestamp_ms": 1718450096789})
        assert "hello" in stdout.getvalue()
        assert stderr.getvalue() == ""

    def test_error_writes_to_stderr(self):
        sink, stdout, stderr = self._make_sink()
        sink._emit({"level": "error", "message": "boom", "timestamp_ms": 1718450096789})
        assert "boom" in stderr.getvalue()
        assert stdout.getvalue() == ""

    def test_warning_writes_to_stderr(self):
        sink, stdout, stderr = self._make_sink()
        sink._emit({"level": "warning", "message": "careful", "timestamp_ms": 0})
        assert "careful" in stderr.getvalue()

    def test_critical_writes_to_stderr(self):
        sink, stdout, stderr = self._make_sink()
        sink._emit({"level": "critical", "message": "dead", "timestamp_ms": 0})
        assert "dead" in stderr.getvalue()

    def test_debug_writes_to_stdout(self):
        sink, stdout, stderr = self._make_sink()
        sink._emit({"level": "debug", "message": "dbg", "timestamp_ms": 0})
        assert "dbg" in stdout.getvalue()
        assert stderr.getvalue() == ""

    def test_timestamp_format(self):
        sink, stdout, _ = self._make_sink()
        sink._emit({"level": "info", "message": "ts", "timestamp_ms": 1718450096789})
        assert "2024-06-15" in stdout.getvalue()

    def test_level_in_output(self):
        sink, stdout, _ = self._make_sink()
        sink._emit({"level": "info", "message": "test", "timestamp_ms": 0})
        assert "INFO" in stdout.getvalue()

    def test_context_pretty_printed(self):
        sink, stdout, _ = self._make_sink(pretty_context=True)
        sink._emit({"level": "info", "message": "ctx", "timestamp_ms": 0, "user": "bob"})
        output = stdout.getvalue()
        assert "user" in output
        assert "bob" in output

    def test_context_json_when_pretty_disabled(self):
        sink, stdout, _ = self._make_sink(pretty_context=False)
        sink._emit({"level": "info", "message": "ctx", "timestamp_ms": 0, "user": "bob"})
        output = stdout.getvalue()
        assert '"user"' in output
        assert '"bob"' in output

    def test_no_context_when_empty(self):
        sink, stdout, _ = self._make_sink()
        sink._emit({"level": "info", "message": "bare", "timestamp_ms": 0})
        output = stdout.getvalue()
        # Should only have timestamp, level, message — no extra braces/dict
        assert "bare" in output
        lines = output.strip().split("\n")
        assert len(lines) == 1

    def test_markup_injection_safe(self):
        """Messages containing rich markup syntax should not be interpreted."""
        sink, stdout, _ = self._make_sink()
        sink._emit({
            "level": "info",
            "message": "[bold red]not styled[/bold red]",
            "timestamp_ms": 0,
        })
        output = stdout.getvalue()
        # The markup should appear literally, not be interpreted
        assert "[bold red]" in output
