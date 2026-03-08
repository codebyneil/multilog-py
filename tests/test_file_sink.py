"""Tests for FileSink append/overwrite semantics."""

import json
from pathlib import Path

from multilog.sinks.file import FileSink


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class TestFileSink:
    def test_append_false_truncates_once_then_appends(self, tmp_path):
        path = tmp_path / "app.jsonl"
        path.write_text('{"message":"old"}\n', encoding="utf-8")

        sink = FileSink(path, append=False)
        sink.emit({"message": "first", "level": "info"})
        sink.emit({"message": "second", "level": "info"})

        rows = _read_jsonl(path)
        assert [row["message"] for row in rows] == ["first", "second"]

    def test_append_true_preserves_existing_lines(self, tmp_path):
        path = tmp_path / "app.jsonl"
        path.write_text('{"message":"old"}\n', encoding="utf-8")

        sink = FileSink(path, append=True)
        sink.emit({"message": "new", "level": "info"})

        rows = _read_jsonl(path)
        assert [row["message"] for row in rows] == ["old", "new"]
