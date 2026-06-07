"""Betterstack sink: batching (default), on_error observability, and sync mode.

Reads credentials from the environment so no secrets live in the repo:
    export BETTERSTACK_TOKEN=...   BETTERSTACK_INGEST_URL=https://sNNNN.region.betterstackdata.com
    uv run python examples/betterstack.py
"""

import os

from multilog import BetterstackSink, ConsoleSink, LogLevel, configure, get_logger

token = os.environ.get("BETTERSTACK_TOKEN")
url = os.environ.get("BETTERSTACK_INGEST_URL")
if not (token and url):
    raise SystemExit("Set BETTERSTACK_TOKEN and BETTERSTACK_INGEST_URL to run this example.")


def on_error(exc, payloads):
    # Delivery failures are observable here instead of vanishing to stderr.
    print(f"betterstack delivery failed: {type(exc).__name__}: {exc} ({len(payloads)} events)")


# Batching (default): non-blocking — a background worker delivers in batches.
configure(sinks=[ConsoleSink(), BetterstackSink(token, url, on_error=on_error)])
log = get_logger()
for i in range(5):
    log.log("batched event", LogLevel.INFO, {"i": i})
log.close()  # flushes the batch worker before exit

# Synchronous mode — the right choice for a short-lived CLI, where a background
# worker would never get a chance to flush.
cli_sink = BetterstackSink(token, url, batch=False, on_error=on_error, register_atexit=False)
configure(sinks=[ConsoleSink(), cli_sink], name="cli")
get_logger("cli").log("one-shot CLI event", LogLevel.INFO)
get_logger("cli").close()

print("done — check Betterstack Live Tail for the events.")
