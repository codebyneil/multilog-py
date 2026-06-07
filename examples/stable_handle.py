"""The stable-handle guarantee: capture a handle before configure() runs.

This is the exact scenario that used to silently drop logs in hand-rolled
logger singletons. With multilog it just works.
"""

from multilog import ConsoleSink, LogLevel, configure, get_logger

# Captured early — imagine this is a module-level `log = get_logger("app")`
# evaluated at import time, before the app has configured anything.
log = get_logger("app")

# Later, during startup, sinks are installed *in place* on the same handle.
configure(sinks=[ConsoleSink()])

# The handle captured earlier routes to the sinks configured later.
log.log("this reaches the sink configured after capture", LogLevel.INFO)

# ...because it is literally the same object, forever:
print("handle identity stable:", get_logger("app") is log)
