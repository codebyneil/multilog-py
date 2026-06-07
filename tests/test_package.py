"""Coverage for package-level concerns (version resolution)."""

import subprocess
import sys
import textwrap

import multilog


def test_version_is_nonempty_string():
    assert isinstance(multilog.__version__, str)
    assert multilog.__version__


def test_public_surface_is_exported():
    for name in (
        "get_logger",
        "get_async_logger",
        "configure",
        "logger",
        "Logger",
        "AsyncLogger",
        "LogLevel",
        "BaseSink",
        "ConsoleSink",
        "FileSink",
        "BetterstackSink",
        "OverflowPolicy",
        "MultilogError",
        "SinkError",
        "QueueFull",
    ):
        assert hasattr(multilog, name), name
        assert name in multilog.__all__, name


def test_version_falls_back_when_package_metadata_missing():
    """If importlib.metadata can't find the package, __version__ falls back to 0.0.0.

    Runs in a subprocess so patching importlib.metadata can't contaminate other
    tests' already-imported references.
    """
    code = textwrap.dedent(
        """
        import sys
        import importlib.metadata as md

        def _raise(_name):
            raise md.PackageNotFoundError(_name)

        md.version = _raise
        sys.modules.pop("multilog", None)
        import multilog
        assert multilog.__version__ == "0.0.0", multilog.__version__
        print("OK")
        """
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
