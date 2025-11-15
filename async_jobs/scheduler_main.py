"""Scheduler main entry point."""
import argparse
import asyncio
import logging
import sys

import boto3
import psycopg

from async_jobs.config import AsyncJobsConfig
from async_jobs.ddl import get_ddl
from async_jobs.scheduler import run_scheduler_loop


def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


async def async_main():
    """Async main function."""
    parser = argparse.ArgumentParser(description="Async jobs scheduler")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    parser.add_argument("--init-db", action="store_true", help="Initialize database schema")
    args = parser.parse_args()

    setup_logging(args.log_level)
    logger = logging.getLogger("scheduler")

    # Load config
    config = AsyncJobsConfig.from_env()
    logger.info("Configuration loaded")

    # Initialize database pool
    db_pool = psycopg.AsyncConnectionPool(
        conninfo=config.db_dsn,
        min_size=2,
        max_size=10,
    )
    await db_pool.wait()
    logger.info("Database pool initialized")

    # Initialize database schema if requested
    if args.init_db:
        logger.info("Initializing database schema...")
        async with db_pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(get_ddl())
        logger.info("Database schema initialized")

    # Initialize SQS client
    sqs_client = boto3.client("sqs")
    logger.info("SQS client initialized")

    # Run scheduler
    try:
        await run_scheduler_loop(config, db_pool, sqs_client, logger)
    finally:
        await db_pool.close()


def main():
    """Main entry point."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
