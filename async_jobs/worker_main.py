"""CLI entrypoint for worker."""

import argparse
import asyncio
import importlib
import logging
import os
import signal
import sys

import asyncpg
import boto3

from async_jobs.config import AsyncJobsConfig
from async_jobs.registry import job_registry
from async_jobs.worker import run_worker_loop


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


def load_handlers():
    """Load job handlers from configured module."""
    handlers_module = os.getenv("ASYNC_JOBS_HANDLERS_MODULE")
    if handlers_module:
        try:
            importlib.import_module(handlers_module)
            logging.info(f"Loaded handlers from {handlers_module}")
        except ImportError as e:
            logging.warning(f"Failed to import handlers module {handlers_module}: {e}")
    else:
        logging.warning(
            "ASYNC_JOBS_HANDLERS_MODULE not set, no handlers will be available"
        )


def main():
    """Main entrypoint for worker."""
    setup_logging()
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Async Jobs Worker")
    parser.add_argument(
        "--queue",
        required=True,
        help="Queue name to process (e.g., 'async-notifications')",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=10,
        help="Max messages to receive per poll (default: 10)",
    )
    parser.add_argument(
        "--wait-time-seconds",
        type=int,
        default=20,
        help="Long poll wait time in seconds (default: 20)",
    )

    args = parser.parse_args()

    try:
        config = AsyncJobsConfig.from_env()
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        sys.exit(1)

    # Load handlers
    load_handlers()

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

            logger.info(f"Starting worker loop for queue: {args.queue}...")
            await run_worker_loop(
                config=config,
                db_pool=db_pool,
                sqs_client=sqs_client,
                registry=job_registry,
                queue_name=args.queue,
                logger=logger,
                shutdown_event=shutdown_event,
                max_messages=args.max_messages,
                wait_time_seconds=args.wait_time_seconds,
            )
        except Exception as e:
            logger.error(f"Fatal error in worker: {e}", exc_info=True)
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
