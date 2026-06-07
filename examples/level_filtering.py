"""Per-sink threshold (min_level) and explicit allow-set (only)."""

from multilog import ConsoleSink, LogLevel, configure, get_logger

log = get_logger()

print("--- min_level=WARN: only WARN and above print ---")
configure(sinks=[ConsoleSink(min_level=LogLevel.WARN)])
for level in LogLevel:
    log.log(f"{level.value} message", level)

print("--- only={INFO, ERROR}: exactly those two, ignoring threshold ---")
configure(sinks=[ConsoleSink(only={LogLevel.INFO, LogLevel.ERROR})])
for level in LogLevel:
    log.log(f"{level.value} message", level)
