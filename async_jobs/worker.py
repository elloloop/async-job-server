"""Worker for async jobs."""
import asyncio
import json
import logging
import traceback
from datetime import datetime
from typing import Any
from uuid import UUID

import boto3
import psycopg

from async_jobs.config import AsyncJobsConfig
from async_jobs.models import JobContext
from async_jobs.registry import JobRegistry
from async_jobs.service import JobService
from async_jobs.store import JobStore


def calculate_backoff_seconds(backoff_policy: dict, attempt: int) -> int:
    """Calculate backoff delay based on policy and attempt number."""
    backoff_type = backoff_policy.get("type", "exponential")
    base_delay = backoff_policy.get("base_delay_seconds", 60)
    max_delay = backoff_policy.get("max_delay_seconds", 3600)

    if backoff_type == "exponential":
        delay = base_delay * (2 ** (attempt - 1))
    elif backoff_type == "linear":
        delay = base_delay * attempt
    elif backoff_type == "constant":
        delay = base_delay
    else:
        delay = base_delay

    return min(delay, max_delay)


async def run_worker_loop(
    config: AsyncJobsConfig,
    db_pool: psycopg.AsyncConnectionPool,
    sqs_client: Any,
    registry: JobRegistry,
    queue_name: str,
    logger: logging.Logger,
):
    """Run the worker loop."""
    store = JobStore(db_pool)
    service = JobService(config, store)

    logger.info(f"Worker starting for queue: {queue_name}")

    while True:
        try:
            # Poll SQS for messages
            response = sqs_client.receive_message(
                QueueUrl=queue_name,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=config.worker_poll_interval_seconds,
                VisibilityTimeout=config.worker_visibility_timeout_seconds,
            )

            messages = response.get("Messages", [])
            if not messages:
                continue

            for message in messages:
                receipt_handle = message["ReceiptHandle"]
                try:
                    # Parse job ID from message
                    body = json.loads(message["Body"])
                    job_id = UUID(body["job_id"])

                    logger.info(f"Processing job {job_id}")

                    # Get job from database
                    job = await service.get_job(job_id)

                    # Check if handler exists
                    if not registry.has_handler(job.type):
                        logger.error(f"No handler for job type {job.type}, marking as dead")
                        await service.mark_job_dead(
                            job_id=job_id,
                            error={
                                "error": "NoHandlerError",
                                "message": f"No handler registered for job type: {job.type}",
                            },
                        )
                        sqs_client.delete_message(
                            QueueUrl=queue_name, ReceiptHandle=receipt_handle
                        )
                        continue

                    # Get handler
                    handler = registry.get_handler(job.type)

                    # Create context
                    context = JobContext(
                        job_id=job.id,
                        tenant_id=job.tenant_id,
                        use_case=job.use_case,
                        type=job.type,
                        attempt=job.attempts + 1,
                    )

                    # Execute handler
                    try:
                        result = await handler(context, job.payload)
                        logger.info(f"Job {job_id} succeeded")
                        await service.mark_job_succeeded(job_id)
                        sqs_client.delete_message(
                            QueueUrl=queue_name, ReceiptHandle=receipt_handle
                        )
                    except Exception as handler_error:
                        logger.error(f"Job {job_id} failed: {handler_error}", exc_info=True)

                        # Determine if we should retry
                        attempts = job.attempts + 1
                        if attempts < job.max_attempts:
                            # Retry with backoff
                            backoff_seconds = calculate_backoff_seconds(
                                job.backoff_policy, attempts
                            )
                            logger.info(
                                f"Job {job_id} will retry (attempt {attempts}/{job.max_attempts}) "
                                f"after {backoff_seconds}s"
                            )
                            await service.mark_job_retry(
                                job_id=job_id,
                                error={
                                    "error": type(handler_error).__name__,
                                    "message": str(handler_error),
                                    "traceback": traceback.format_exc(),
                                },
                                backoff_seconds=backoff_seconds,
                            )
                            sqs_client.delete_message(
                                QueueUrl=queue_name, ReceiptHandle=receipt_handle
                            )
                        else:
                            # Mark as dead
                            logger.error(
                                f"Job {job_id} exceeded max attempts ({job.max_attempts}), "
                                f"marking as dead"
                            )
                            await service.mark_job_dead(
                                job_id=job_id,
                                error={
                                    "error": type(handler_error).__name__,
                                    "message": str(handler_error),
                                    "traceback": traceback.format_exc(),
                                },
                            )
                            sqs_client.delete_message(
                                QueueUrl=queue_name, ReceiptHandle=receipt_handle
                            )

                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    # Don't delete message, let it become visible again

        except Exception as e:
            logger.error(f"Error in worker loop: {e}", exc_info=True)
            await asyncio.sleep(1)
