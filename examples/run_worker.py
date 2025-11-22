"""Example worker script using the async_jobs library."""

import argparse
import asyncio
import importlib
import logging
import os
import signal
import sys

import aioboto3
import asyncpg

from async_jobs import AsyncJobsConfig, job_registry, run_worker_loop

# Global shutdown event
shutdown_event = asyncio.Event()


def handle_signal(signum, frame):
    """Handle shutdown signals."""
    logging.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()


async def main(queue_url: str, handlers_module: str = None):
    """Main function to run the worker."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("worker")

    try:
        # Load configuration
        logger.info("Loading configuration from environment")
        config = AsyncJobsConfig.from_env()

        # Import handlers module to register handlers
        if handlers_module:
            logger.info(f"Importing handlers module: {handlers_module}")
            try:
                importlib.import_module(handlers_module)
                logger.info(f"Registered handlers: {list(job_registry.all_handlers().keys())}")
            except ImportError as e:
                logger.error(f"Failed to import handlers module: {str(e)}")
                sys.exit(1)

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
        
        # Get endpoint URL from environment if set (for Localstack)
        endpoint_url = os.getenv("AWS_ENDPOINT_URL")
        
        sqs_kwargs = {}
        if endpoint_url:
            sqs_kwargs["endpoint_url"] = endpoint_url
            logger.info(f"Using SQS endpoint: {endpoint_url}")
        
        async with session.client("sqs", **sqs_kwargs) as sqs_client:
            # Run worker loop
            try:
                await run_worker_loop(
                    config, db_pool, sqs_client, job_registry, queue_url, logger,
                    shutdown_event=shutdown_event
                )
            except asyncio.CancelledError:
                logger.info("Worker loop cancelled")
            finally:
                # Clean up
                logger.info("Closing database pool")
                await db_pool.close()

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Async jobs worker")
    parser.add_argument(
        "--queue",
        required=True,
        help="SQS queue URL to poll for jobs",
    )
    parser.add_argument(
        "--handlers-module",
        default=None,
        help="Python module containing job handlers (e.g., 'myapp.jobs.handlers')",
    )

    args = parser.parse_args()

    # Set up signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Run async main
    try:
        asyncio.run(main(args.queue, args.handlers_module))
    except KeyboardInterrupt:
        pass
