"""Scheduler CLI entrypoint."""

import asyncio
import logging
import signal
import sys

import aioboto3
import asyncpg

from async_jobs.config import AsyncJobsConfig
from async_jobs.scheduler import run_scheduler_loop

# Global flag for graceful shutdown
shutdown_requested = False


def handle_signal(signum, frame):
    """Handle shutdown signals."""
    global shutdown_requested
    logging.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True


async def async_main():
    """Async main function."""
    global shutdown_requested

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("async_jobs.scheduler")

    try:
        # Load configuration
        logger.info("Loading configuration from environment")
        config = AsyncJobsConfig.from_env()

        # Create database pool
        logger.info("Connecting to database")
        db_pool = await asyncpg.create_pool(
            config.db_dsn,
            min_size=2,
            max_size=10,
        )

        # Create SQS client
        logger.info("Initializing SQS client")
        session = aioboto3.Session()
        async with session.client("sqs") as sqs_client:
            # Run scheduler loop
            try:
                await run_scheduler_loop(config, db_pool, sqs_client, logger)
            except asyncio.CancelledError:
                logger.info("Scheduler loop cancelled")
            finally:
                # Clean up
                logger.info("Closing database pool")
                await db_pool.close()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


def main():
    """Main entrypoint for scheduler CLI."""
    # Set up signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Run async main
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
