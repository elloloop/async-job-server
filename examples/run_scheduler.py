"""Example scheduler script using the async_jobs library."""

import asyncio
import logging
import os
import signal
import sys

import aioboto3
import asyncpg

from async_jobs import AsyncJobsConfig, run_scheduler_loop

# Global shutdown event
shutdown_event = asyncio.Event()


def handle_signal(signum, frame):
    """Handle shutdown signals."""
    logging.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()


async def main():
    """Main function to run the scheduler."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("scheduler")

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
        
        # Get endpoint URL from environment if set (for Localstack)
        endpoint_url = os.getenv("AWS_ENDPOINT_URL")
        
        sqs_kwargs = {}
        if endpoint_url:
            sqs_kwargs["endpoint_url"] = endpoint_url
            logger.info(f"Using SQS endpoint: {endpoint_url}")
        
        async with session.client("sqs", **sqs_kwargs) as sqs_client:
            # Run scheduler loop
            try:
                await run_scheduler_loop(
                    config, db_pool, sqs_client, logger, shutdown_event=shutdown_event
                )
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


if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Run async main
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
