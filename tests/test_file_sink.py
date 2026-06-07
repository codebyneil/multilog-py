"""Tests for FileSink: append/overwrite, concurrent writes, lifecycle."""

import json
import threading
from pathlib import Path

import pytest

from multilog.exceptions import SinkError
from multilog.sinks.file import FileSink


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class TestAppendVsOverwrite:
    def test_append_false_truncates_once_then_appends(self, tmp_path):
        path = tmp_path / "app.jsonl"
        path.write_text('{"message":"old"}\n', encoding="utf-8")

        sink = FileSink(path, append=False)
        sink.emit({"message": "first", "level": "info"})
        sink.emit({"message": "second", "level": "info"})
        sink.close()

        rows = _read_jsonl(path)
        assert [row["message"] for row in rows] == ["first", "second"]

    def test_append_true_preserves_existing_lines(self, tmp_path):
        path = tmp_path / "app.jsonl"
        path.write_text('{"message":"old"}\n', encoding="utf-8")

        sink = FileSink(path, append=True)
        sink.emit({"message": "new", "level": "info"})
        sink.close()

        rows = _read_jsonl(path)
        assert [row["message"] for row in rows] == ["old", "new"]


class TestConcurrentWrites:
    def test_many_threads_no_interleaved_lines(self, tmp_path):
        """50 threads × 100 emits → 5000 intact JSON lines, no truncation."""
        path = tmp_path / "concurrent.jsonl"
        sink = FileSink(path)

        n_threads = 50
        per_thread = 100

        def write_many(tid: int):
            for i in range(per_thread):
                sink.emit(
                    {
                        "message": f"t{tid}-i{i}",
                        "level": "info",
                        "tid": tid,
                        "i": i,
                        # Big-ish payload to push past PIPE_BUF and surface
                        # interleave bugs if the lock were missing.
                        "filler": "x" * 4096,
                    }
                )

        threads = [threading.Thread(target=write_many, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        sink.close()

        rows = _read_jsonl(path)
        assert len(rows) == n_threads * per_thread
        # Every line must be intact, parseable JSON with all expected fields.
        for row in rows:
            assert "tid" in row and "i" in row and "filler" in row

        # Every (tid, i) pair must appear exactly once.
        seen = {(row["tid"], row["i"]) for row in rows}
        assert seen == {(t, i) for t in range(n_threads) for i in range(per_thread)}


class TestLifecycle:
    def test_close_flushes_and_closes(self, tmp_path):
        path = tmp_path / "app.jsonl"
        sink = FileSink(path)
        sink.emit({"message": "before-close", "level": "info"})
        sink.close()

        assert sink._closed is True
        rows = _read_jsonl(path)
        assert rows[0]["message"] == "before-close"

    def test_close_is_idempotent(self, tmp_path):
        sink = FileSink(tmp_path / "app.jsonl")
        sink.close()
        sink.close()  # must not raise

    def test_emit_after_close_raises_sink_error(self, tmp_path):
        sink = FileSink(tmp_path / "app.jsonl")
        sink.close()

        with pytest.raises(SinkError, match="closed"):
            sink.emit({"message": "too-late", "level": "info"})

    def test_nested_directory_auto_created(self, tmp_path):
        path = tmp_path / "deep" / "nested" / "logs" / "app.jsonl"
        sink = FileSink(path)
        sink.emit({"message": "hi", "level": "info"})
        sink.close()

        assert path.exists()
        rows = _read_jsonl(path)
        assert rows[0]["message"] == "hi"

    def test_flush_makes_writes_visible_and_returns_true(self, tmp_path):
        path = tmp_path / "app.jsonl"
        sink = FileSink(path)
        sink.emit({"message": "x", "level": "info"})

        assert sink.flush() is True
        assert _read_jsonl(path)[0]["message"] == "x"

        sink.close()

    def test_flush_after_close_is_safe(self, tmp_path):
        sink = FileSink(tmp_path / "app.jsonl")
        sink.close()
        assert sink.flush() is True  # must not raise on a closed handle
