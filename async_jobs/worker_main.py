"""CLI entrypoint and programmatic interface for worker."""

import argparse
import asyncio
import importlib
import logging
import os
import signal
import sys
from typing import Optional

import asyncpg
import boto3

from async_jobs.config import AsyncJobsConfig
from async_jobs.registry import JobRegistry, job_registry
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


async def run_worker(
    queue_name: str,
    config: Optional[AsyncJobsConfig] = None,
    db_pool=None,
    sqs_client=None,
    registry: Optional[JobRegistry] = None,
    logger: Optional[logging.Logger] = None,
    shutdown_event: Optional[asyncio.Event] = None,
    max_messages: int = 10,
    wait_time_seconds: int = 20,
    handlers_module: Optional[str] = None,
):
    """
    Run the worker programmatically.

    This function can be imported and used in your own code to run a worker
    with custom configuration or as part of a larger application.

    Args:
        queue_name: Queue name to process (e.g., 'async-notifications')
        config: AsyncJobsConfig instance. If None, will load from environment.
        db_pool: Database connection pool. If None, will create from config.
        sqs_client: Boto3 SQS client. If None, will create default client.
        registry: JobRegistry instance. If None, will use global job_registry.
        logger: Logger instance. If None, will create default logger.
        shutdown_event: Optional asyncio.Event for graceful shutdown.
        max_messages: Max messages to receive per poll.
        wait_time_seconds: Long poll wait time in seconds.
        handlers_module: Module path to load handlers from. If None, uses ASYNC_JOBS_HANDLERS_MODULE env var.

    Example:
        ```python
        from async_jobs import run_worker, AsyncJobsConfig, job_registry
        import asyncio

        config = AsyncJobsConfig.from_env()
        asyncio.run(run_worker(
            queue_name="async-notifications",
            config=config,
            registry=job_registry,
            handlers_module="myapp.jobs.handlers"
        ))
        ```
    """
    if config is None:
        config = AsyncJobsConfig.from_env()

    if logger is None:
        logger = logging.getLogger(__name__)

    if sqs_client is None:
        sqs_client = boto3.client("sqs")

    if registry is None:
        registry = job_registry

    if shutdown_event is None:
        shutdown_event = asyncio.Event()

    # Load handlers if module specified
    if handlers_module:
        try:
            importlib.import_module(handlers_module)
            logger.info(f"Loaded handlers from {handlers_module}")
        except ImportError as e:
            logger.warning(f"Failed to import handlers module {handlers_module}: {e}")
    else:
        load_handlers()

    db_pool_provided = db_pool is not None
    if db_pool is None:
        db_pool = await create_db_pool(config)

    try:
        await run_worker_loop(
            config=config,
            db_pool=db_pool,
            sqs_client=sqs_client,
            registry=registry,
            queue_name=queue_name,
            logger=logger,
            shutdown_event=shutdown_event,
            max_messages=max_messages,
            wait_time_seconds=wait_time_seconds,
        )
    finally:
        if not db_pool_provided and db_pool:
            await db_pool.close()


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
        try:
            logger.info(f"Starting worker for queue: {args.queue}...")
            await run_worker(
                queue_name=args.queue,
                config=config,
                sqs_client=sqs_client,
                registry=job_registry,
                logger=logger,
                shutdown_event=shutdown_event,
                max_messages=args.max_messages,
                wait_time_seconds=args.wait_time_seconds,
            )
        except Exception as e:
            logger.error(f"Fatal error in worker: {e}", exc_info=True)
            sys.exit(1)

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
