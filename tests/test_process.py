"""Process-level tests: atexit flush on interpreter shutdown, and fork safety."""

import contextlib
import json
import os
import subprocess
import sys
import textwrap
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest


class _CollectingServer:
    """A tiny local HTTP server that records JSON arrays posted to it."""

    def __init__(self):
        self.events: list = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                with contextlib.suppress(Exception):
                    outer.events.extend(json.loads(body))
                self.send_response(202)
                self.end_headers()

            def log_message(self, *args):  # silence
                pass

        self._server = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._server.shutdown()
        self._server.server_close()


class TestAtexitFlush:
    def test_events_flushed_on_interpreter_exit_without_close(self):
        """A batching sink with register_atexit=True flushes pending events when
        the process exits even though close() is never called."""
        with _CollectingServer() as server:
            code = textwrap.dedent(
                f"""
                from multilog import configure, get_logger, BetterstackSink, ConsoleSink, LogLevel

                sink = BetterstackSink(
                    token="t",
                    ingest_url="http://127.0.0.1:{server.port}",
                    batch=True,
                    flush_interval=5.0,   # long, so only atexit triggers the flush
                    register_atexit=True,
                )
                configure(sinks=[sink])
                log = get_logger()
                for i in range(7):
                    log.log("atexit event", LogLevel.INFO, {{"i": i}})
                # NOTE: deliberately no close() — rely on the atexit hook.
                """
            )
            result = subprocess.run(
                [sys.executable, "-c", code], capture_output=True, text=True, timeout=30
            )
            assert result.returncode == 0, result.stderr

        messages = [e for e in server.events if e.get("message") == "atexit event"]
        assert len(messages) == 7
        assert {e["i"] for e in messages} == set(range(7))


@pytest.mark.skipif(not hasattr(os, "fork"), reason="requires POSIX fork")
class TestForkSafety:
    # Python 3.12+ warns that forking a multi-threaded process is risky — which is
    # exactly the documented caveat. The child here does minimal work then _exit.
    @pytest.mark.filterwarnings("ignore::DeprecationWarning")
    def test_child_can_configure_and_log_after_fork(self):
        """A forked child can install fresh sinks and log without hanging or crashing."""
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:  # child
            os.close(r)
            code = 0
            try:
                from multilog import ConsoleSink, LogLevel, configure, get_logger

                configure(sinks=[ConsoleSink(use_color=False)], name="forked")
                get_logger("forked").log("hello from child", LogLevel.INFO)
            except BaseException:
                code = 1
            os.write(w, bytes([code]))
            os.close(w)
            os._exit(code)
        else:  # parent
            os.close(w)
            status = os.read(r, 1)
            os.close(r)
            _, exit_status = os.waitpid(pid, 0)
            assert status == bytes([0])  # child reported success
            assert os.WIFEXITED(exit_status) and os.WEXITSTATUS(exit_status) == 0
