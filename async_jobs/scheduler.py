"""Scheduler for async jobs."""

import asyncio
import json
import logging
from datetime import timedelta
from typing import Any

from psycopg_pool import AsyncConnectionPool

from async_jobs.config import AsyncJobsConfig
from async_jobs.service import JobService
from async_jobs.store import JobStore


async def run_scheduler_loop(
    config: AsyncJobsConfig,
    db_pool: AsyncConnectionPool,
    sqs_client: Any,
    logger: logging.Logger,
):
    """Run the scheduler loop."""
    store = JobStore(db_pool)
    service = JobService(config, store)

    logger.info("Scheduler starting...")

    while True:
        try:
            # Process each use case
            for use_case, use_case_config in config.use_case_configs.items():
                try:
                    # Determine how many jobs we can schedule
                    max_concurrent = use_case_config.max_concurrent

                    # Lease jobs for this use case
                    lease_duration = timedelta(seconds=config.lease_duration_seconds)
                    jobs = await service.lease_jobs_for_use_case(
                        use_case=use_case,
                        max_jobs=max_concurrent,
                        lease_duration=lease_duration,
                    )

                    if jobs:
                        logger.info(f"Leased {len(jobs)} jobs for use_case={use_case}")

                        # Push job IDs to SQS
                        queue_url = use_case_config.sqs_queue
                        for job in jobs:
                            message_body = json.dumps({"job_id": str(job.id)})
                            sqs_client.send_message(
                                QueueUrl=queue_url,
                                MessageBody=message_body,
                            )
                            logger.debug(f"Pushed job {job.id} to SQS queue {queue_url}")

                except Exception as e:
                    logger.error(f"Error scheduling use_case={use_case}: {e}", exc_info=True)

            # Sleep before next iteration
            await asyncio.sleep(config.scheduler_interval_seconds)

        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)
            await asyncio.sleep(config.scheduler_interval_seconds)
