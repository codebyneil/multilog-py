"""Sink exports for multilog-py."""

import contextlib

from multilog.sinks.base import BaseSink
from multilog.sinks.betterstack import BetterstackSink
from multilog.sinks.console import ConsoleSink
from multilog.sinks.file import FileSink

with contextlib.suppress(ImportError):
    from multilog.sinks.rich_console import RichConsoleSink

__all__ = [
    "BaseSink",
    "BetterstackSink",
    "ConsoleSink",
    "FileSink",
    "RichConsoleSink",
]
