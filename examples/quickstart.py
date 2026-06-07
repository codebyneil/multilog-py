"""Quick start: configure() once, get_logger() anywhere."""

from multilog import ConsoleSink, LogLevel, configure, get_logger

configure(sinks=[ConsoleSink()], context={"service": "demo"})
log = get_logger()

log.log("user signed up", LogLevel.INFO, {"user_id": 7})
log.log("slow query", LogLevel.WARN, {"ms": 1200})

try:
    int("not-a-number")
except ValueError as exc:
    log.log_exception("could not parse input", exc, level=LogLevel.ERROR)
