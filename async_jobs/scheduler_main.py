"""CLI entrypoint for scheduler."""

import asyncio
import logging
import os
import signal
import sys

import asyncpg
import boto3

from async_jobs.config import AsyncJobsConfig
from async_jobs.scheduler import run_scheduler_loop


def setup_logging():
    """Setup logging configuration."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


async def create_db_pool(config: AsyncJobsConfig):
    """Create database connection pool."""
    return await asyncpg.create_pool(config.db_dsn, min_size=2, max_size=10)


def main():
    """Main entrypoint for scheduler."""
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        config = AsyncJobsConfig.from_env()
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    # Setup SQS client
    sqs_client = boto3.client("sqs")

    # Setup shutdown event
    shutdown_event = asyncio.Event()

    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}, shutting down...")
        shutdown_event.set()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    async def run():
        """Async main function."""
        db_pool = None
        try:
            logger.info("Creating database connection pool...")
            db_pool = await create_db_pool(config)

            logger.info("Starting scheduler loop...")
            await run_scheduler_loop(
                config=config,
                db_pool=db_pool,
                sqs_client=sqs_client,
                logger=logger,
                shutdown_event=shutdown_event,
            )
        except Exception as e:
            logger.error(f"Fatal error in scheduler: {e}", exc_info=True)
            sys.exit(1)
        finally:
            if db_pool:
                logger.info("Closing database connection pool...")
                await db_pool.close()

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
