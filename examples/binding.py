"""Per-request / per-component context with bind()."""

from multilog import ConsoleSink, LogLevel, configure, get_logger

configure(sinks=[ConsoleSink()], context={"service": "api"})
log = get_logger()

for request_id in ("req-1", "req-2"):
    rlog = log.bind(request_id=request_id)
    rlog.log("received", LogLevel.INFO)
    # bind() composes — nest it for sub-scopes:
    rlog.bind(stage="db").log("query done", LogLevel.DEBUG, {"ms": 12})
