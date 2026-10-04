"""Level arguments given as strings behave exactly like LogLevel members, and the
documented slice syntax type-checks for users."""

import shutil
import subprocess
import textwrap

import pytest
from conftest import RecordingSink

from multilog import ConsoleSink, FileSink, Logger, LogLevel


class TestSinkLevelCoercion:
    def test_min_level_value_string_filters_by_severity(self):
        """Regression: a plain string used to fall through to alphabetical str ordering,
        so min_level="error" emitted trace, info and warn as well."""
        sink = RecordingSink(min_level="error")
        log = Logger(sinks=[sink])

        for level in LogLevel:
            log.log("x", level)

        assert [p["level"] for p in sink.payloads] == [LogLevel.ERROR, LogLevel.FATAL]

    @pytest.mark.parametrize("given", ["warn", "WARN", LogLevel.WARN])
    def test_min_level_is_stored_as_a_member(self, given):
        assert RecordingSink(min_level=given).min_level is LogLevel.WARN

    def test_only_strings_are_coerced_to_members(self):
        sink = RecordingSink(only={"info", "FATAL"})
        assert sink.only == frozenset({LogLevel.INFO, LogLevel.FATAL})
        assert all(type(level) is LogLevel for level in sink.only)

    @pytest.mark.parametrize("bad", ["verbose", "", "Error", 3, None])
    def test_invalid_min_level_raises_value_error(self, bad):
        with pytest.raises(ValueError, match="is not a LogLevel"):
            RecordingSink(min_level=bad)

    def test_invalid_only_member_raises_value_error(self):
        with pytest.raises(ValueError, match="is not a LogLevel"):
            RecordingSink(only=[LogLevel.INFO, "loud"])

    def test_builtin_sinks_accept_strings(self, tmp_path):
        assert ConsoleSink(min_level="warn").min_level is LogLevel.WARN
        file_sink = FileSink(tmp_path / "x.jsonl", only=["error"])
        try:
            assert file_sink.only == frozenset({LogLevel.ERROR})
        finally:
            file_sink.close()


class TestComparisonsWithStrings:
    def test_value_strings_compare_by_severity_not_alphabetically(self):
        assert not (LogLevel.WARN >= "error")
        assert not (LogLevel.INFO >= "error")
        assert LogLevel.FATAL >= "warn"
        assert LogLevel.INFO < "error"
        assert LogLevel.INFO <= "info"
        assert LogLevel.ERROR > "warn"

    def test_string_on_the_left_uses_severity_too(self):
        # Python tries the str subclass's reflected operator first, so plain
        # str ordering never gets a say.
        # The string is deliberately on the left: that is the case under test.
        assert "error" > LogLevel.WARN  # noqa: SIM300
        assert "trace" < LogLevel.DEBUG  # noqa: SIM300
        assert not ("warn" >= LogLevel.ERROR)  # noqa: SIM300

    @pytest.mark.parametrize("other", ["verbose", "ERROR", 42, None, 3.14])
    def test_non_level_operands_are_not_implemented(self, other):
        # Name strings ("ERROR") are deliberately not levels here, matching
        # StrEnum equality, which also only recognizes the value ("error").
        assert LogLevel.INFO.__ge__(other) is NotImplemented
        assert LogLevel.INFO.__gt__(other) is NotImplemented
        assert LogLevel.INFO.__le__(other) is NotImplemented
        assert LogLevel.INFO.__lt__(other) is NotImplemented


@pytest.mark.skipif(shutil.which("ty") is None, reason="ty type checker not installed")
def test_documented_slice_syntax_type_checks(tmp_path):
    """Regression: `LogLevel[LogLevel.INFO:]` was rejected by the type checker because
    `__getitem__` was typed to take only a string and return a single member."""
    probe = tmp_path / "probe.py"
    probe.write_text(
        textwrap.dedent(
            """
            from multilog import LogLevel

            levels: list[LogLevel] = LogLevel[LogLevel.INFO:]
            more: list[LogLevel] = LogLevel["info":"fatal"]
            one: LogLevel = LogLevel["INFO"]
            """
        ),
        encoding="utf-8",
    )
    result = subprocess.run(["ty", "check", str(probe)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
