"""Scheduler core logic."""

import asyncio
import json
import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

from async_jobs.config import AsyncJobsConfig
from async_jobs.service import JobService


logger = logging.getLogger(__name__)


async def run_scheduler_loop(
    config: AsyncJobsConfig,
    db_pool: Any,
    sqs_client: Any,
    logger: logging.Logger,
    sleep_interval_seconds: float = 5.0,
    shutdown_event: asyncio.Event = None,
) -> None:
    """
    Run the scheduler loop.

    Infinite loop that:
    - For each use_case in config:
      - Compute current running count
      - If below max_concurrent:
        - Select pending jobs ordered by deadline_at and respecting run_at
        - Mark jobs as running and set lease_expires_at
        - Send job IDs to the appropriate SQS queue for that use_case
    - Sleep for a small configurable interval

    Args:
        config: AsyncJobsConfig instance
        db_pool: Database connection pool
        sqs_client: Boto3 SQS client
        logger: Logger instance
        sleep_interval_seconds: Sleep interval between iterations
        shutdown_event: Optional asyncio.Event to signal shutdown
    """
    job_service = JobService(config, db_pool, logger)

    if shutdown_event is None:
        shutdown_event = asyncio.Event()

    logger.info("Scheduler loop started")

    while not shutdown_event.is_set():
        try:
            # Process each use case
            for use_case, use_case_config in config.per_use_case_config.items():
                if shutdown_event.is_set():
                    break

                max_concurrent = use_case_config.get("max_concurrent", 10)
                queue_url = config.get_queue_url_for_use_case(use_case)

                if not queue_url:
                    logger.warning(
                        f"No queue URL configured for use_case {use_case}, skipping"
                    )
                    continue

                try:
                    # Lease jobs for this use case
                    leased_jobs = await job_service.lease_jobs_for_use_case(
                        use_case=use_case,
                        max_concurrent=max_concurrent,
                        limit=100,  # Batch size
                    )

                    if not leased_jobs:
                        continue

                    logger.info(
                        f"Leased {len(leased_jobs)} jobs for use_case {use_case}"
                    )

                    # Send job IDs to SQS
                    for job in leased_jobs:
                        try:
                            sqs_client.send_message(
                                QueueUrl=queue_url,
                                MessageBody=json.dumps({"job_id": str(job.id)}),
                                MessageAttributes={
                                    "job_id": {
                                        "StringValue": str(job.id),
                                        "DataType": "String",
                                    },
                                    "use_case": {
                                        "StringValue": use_case,
                                        "DataType": "String",
                                    },
                                    "tenant_id": {
                                        "StringValue": job.tenant_id,
                                        "DataType": "String",
                                    },
                                },
                            )
                            logger.debug(
                                f"Sent job {job.id} to SQS queue {queue_url}"
                            )
                        except ClientError as e:
                            logger.error(
                                f"Failed to send job {job.id} to SQS: {e}",
                                exc_info=True,
                            )
                            # Mark job as enqueue_failed
                            # Note: This would require a store method to update enqueue_failed
                            # For now, we'll log and continue

                except Exception as e:
                    logger.error(
                        f"Error processing use_case {use_case}: {e}",
                        exc_info=True,
                    )
                    continue

            # Sleep before next iteration
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(), timeout=sleep_interval_seconds
                )
                # If we get here, shutdown was signaled
                break
            except asyncio.TimeoutError:
                # Normal timeout, continue loop
                pass

        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)
            # Sleep briefly before retrying
            await asyncio.sleep(1)

    logger.info("Scheduler loop stopped")
