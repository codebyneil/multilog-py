"""Test all OpenTelemetry log levels."""

import asyncio
from multilog_py import Logger, LogLevel, ConsoleHandler


async def main():
    """Test all log levels."""
    print("=" * 60)
    print("Testing all OpenTelemetry log levels")
    print("=" * 60)

    logger = Logger(handlers=[ConsoleHandler(level=LogLevel.TRACE)])

    # Test all log levels
    await logger.log("Trace message - very detailed", LogLevel.TRACE, {"trace_id": "abc123"})
    await logger.log("Debug message - debugging info", LogLevel.DEBUG, {"debug_var": "value"})
    await logger.log("Info message - general information", LogLevel.INFO, {"user_id": "123"})
    await logger.log("Warning message - something to watch", LogLevel.WARN, {"memory_usage": "high"})
    await logger.log("Error message - something went wrong", LogLevel.ERROR, {"error_code": "E500"})
    await logger.log("Fatal message - critical failure", LogLevel.FATAL, {"system": "database", "status": "crashed"})

    await logger.close()

    print("\n" + "=" * 60)
    print("Testing log level filtering (INFO and above)")
    print("=" * 60)

    # Test filtering - only INFO and above
    logger = Logger(handlers=[ConsoleHandler(level=LogLevel.INFO)])

    await logger.log("This TRACE won't show", LogLevel.TRACE)
    await logger.log("This DEBUG won't show", LogLevel.DEBUG)
    await logger.log("This INFO will show", LogLevel.INFO)
    await logger.log("This WARN will show", LogLevel.WARN)
    await logger.log("This ERROR will show", LogLevel.ERROR)
    await logger.log("This FATAL will show", LogLevel.FATAL)

    await logger.close()


if __name__ == "__main__":
    asyncio.run(main())
