"""Send logs to Betterstack with console output side-by-side."""

from multilog import Logger, LogLevel
from multilog.sinks.betterstack import BetterstackSink
from multilog.sinks.console import ConsoleSink

logger = Logger(
    sinks=[
        ConsoleSink(),
        BetterstackSink(
            token="FyAaTuM96LKCWsf5NRzmt572",
            ingest_url="https://s1734751.eu-fsn-3.betterstackdata.com",
        ),
    ],
)

logger.log("Application started", LogLevel.INFO, {"version": "0.1.0"})
logger.log("Loading configuration", LogLevel.DEBUG, {"source": "env"})
logger.log("Disk usage at 90%", LogLevel.WARNING, {"disk": "/dev/sda1", "usage_pct": 90})
logger.log("Failed to reach database", LogLevel.ERROR, {"host": "db.internal", "timeout_ms": 5000})

logger.log_endpoint(
    endpoint_name="get_user",
    method="GET",
    path="/api/users/42",
    headers={"Authorization": "Bearer ***"},
    query_params={"fields": "name,email"},
)

try:
    result = 1 / 0
except Exception as exc:
    logger.log_exception("Unexpected error in calculation", exc, context={"input": "1/0"})

logger.close()
print("\nDone — check Betterstack Live Tail for the logs.")
