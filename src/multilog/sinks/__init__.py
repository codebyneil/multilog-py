"""Sink exports for multilog-py."""

from multilog.sinks.base import BaseSink
from multilog.sinks.betterstack import BetterstackSink
from multilog.sinks.console import ConsoleSink
from multilog.sinks.file import FileSink

__all__ = [
    "BaseSink",
    "BetterstackSink",
    "ConsoleSink",
    "FileSink",
]
