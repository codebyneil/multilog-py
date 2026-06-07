"""Async logging with get_async_logger (shares state with the sync logger)."""

import asyncio

from multilog import ConsoleSink, LogLevel, configure, get_async_logger, get_logger


async def main():
    configure(sinks=[ConsoleSink()], context={"service": "worker"})
    log = get_async_logger()

    await log.log("worker started", LogLevel.INFO)

    # bind() works the same on the async logger:
    task_log = log.bind(task_id="t-42")
    await task_log.log("processing", LogLevel.DEBUG, {"items": 3})

    try:
        raise RuntimeError("kaboom")
    except RuntimeError as exc:
        await log.log_exception("task failed", exc, level=LogLevel.ERROR)

    # The sync and async handles for a name share sinks and context:
    get_logger().log("from the sync handle, same sinks", LogLevel.INFO)

    await log.close()


if __name__ == "__main__":
    asyncio.run(main())
