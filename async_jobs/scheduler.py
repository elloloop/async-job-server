"""Scheduler logic for async jobs."""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

import asyncpg

from async_jobs.config import AsyncJobsConfig
from async_jobs.service import JobService


async def run_scheduler_loop(
    config: AsyncJobsConfig,
    db_pool: asyncpg.Pool,
    sqs_client: Any,
    logger: logging.Logger,
    loop_interval_seconds: int = 5,
) -> None:
    """
    Run the scheduler loop that leases pending jobs and sends them to SQS.

    Args:
        config: Async jobs configuration
        db_pool: Database connection pool
        sqs_client: AWS SQS client (boto3/aioboto3)
        logger: Logger instance
        loop_interval_seconds: Time to sleep between iterations
    """
    job_service = JobService(config, db_pool, logger)
    lease_duration = timedelta(minutes=10)

    logger.info("Starting scheduler loop")

    while True:
        try:
            # Process each use case
            for use_case, use_case_config in config.per_use_case_config.items():
                max_concurrent = use_case_config["max_concurrent"]
                queue_url = use_case_config["queue"]

                # Lease jobs for this use case
                jobs = await job_service.lease_jobs_for_use_case(
                    use_case=use_case,
                    max_count=max_concurrent,
                    lease_duration=lease_duration,
                )

                if jobs:
                    logger.info(f"Leased {len(jobs)} jobs for use_case {use_case}")

                    # Send job IDs to SQS
                    for job in jobs:
                        message_body = json.dumps({"job_id": str(job.id)})

                        try:
                            await sqs_client.send_message(
                                QueueUrl=queue_url,
                                MessageBody=message_body,
                            )
                            logger.debug(f"Sent job {job.id} to SQS queue {queue_url}")
                        except Exception as e:
                            logger.error(
                                f"Failed to send job {job.id} to SQS: {str(e)}"
                            )
                            # Job will be rescheduled when lease expires

        except Exception as e:
            logger.error(f"Error in scheduler loop: {str(e)}", exc_info=True)

        # Sleep before next iteration
        await asyncio.sleep(loop_interval_seconds)
