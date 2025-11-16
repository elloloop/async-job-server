"""Worker logic for async jobs."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg

from async_jobs.config import AsyncJobsConfig
from async_jobs.errors import JobNotFoundError
from async_jobs.models import JobStatus
from async_jobs.registry import JobRegistry
from async_jobs.service import JobService


async def run_worker_loop(
    config: AsyncJobsConfig,
    db_pool: asyncpg.Pool,
    sqs_client: Any,
    registry: JobRegistry,
    queue_url: str,
    logger: logging.Logger,
    max_messages: int = 10,
    wait_time_seconds: int = 20,
) -> None:
    """
    Run the worker loop that processes jobs from SQS.

    Args:
        config: Async jobs configuration
        db_pool: Database connection pool
        sqs_client: AWS SQS client (boto3/aioboto3)
        registry: Job handler registry
        queue_url: SQS queue URL to poll
        logger: Logger instance
        max_messages: Maximum messages to receive per poll
        wait_time_seconds: Long polling wait time
    """
    job_service = JobService(config, db_pool, logger)

    logger.info(f"Starting worker loop for queue {queue_url}")

    while True:
        try:
            # Long poll SQS for messages
            response = await sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=wait_time_seconds,
                AttributeNames=["All"],
            )

            messages = response.get("Messages", [])

            if not messages:
                logger.debug("No messages received from SQS")
                continue

            logger.info(f"Received {len(messages)} messages from SQS")

            # Process each message
            for message in messages:
                receipt_handle = message["ReceiptHandle"]

                try:
                    # Parse message body
                    body = json.loads(message["Body"])
                    job_id = UUID(body["job_id"])

                    # Load job from database
                    try:
                        job = await job_service.get_job(job_id)
                    except JobNotFoundError:
                        logger.warning(f"Job {job_id} not found, deleting message")
                        await sqs_client.delete_message(
                            QueueUrl=queue_url, ReceiptHandle=receipt_handle
                        )
                        continue

                    # Check if job is still in running state
                    if job.status != JobStatus.running:
                        logger.warning(
                            f"Job {job_id} is not in running state (status={job.status.value}), "
                            f"deleting message"
                        )
                        await sqs_client.delete_message(
                            QueueUrl=queue_url, ReceiptHandle=receipt_handle
                        )
                        continue

                    # Get handler
                    handler = registry.get_handler(job.type)
                    if not handler:
                        logger.error(f"No handler found for job type {job.type}")
                        error = {
                            "error": f"No handler for type {job.type}",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                        await job_service.mark_job_dead(job.id, error)
                        await sqs_client.delete_message(
                            QueueUrl=queue_url, ReceiptHandle=receipt_handle
                        )
                        continue

                    # Execute handler
                    logger.info(f"Executing job {job_id} (type={job.type})")

                    try:
                        # Create context for handler
                        ctx = {"job": job, "logger": logger}
                        await handler(ctx, job.payload)

                        # Mark as succeeded
                        await job_service.mark_job_succeeded(job.id)

                        # Delete message
                        await sqs_client.delete_message(
                            QueueUrl=queue_url, ReceiptHandle=receipt_handle
                        )

                        logger.info(f"Job {job_id} completed successfully")

                    except Exception as e:
                        logger.error(f"Job {job_id} failed: {str(e)}", exc_info=True)

                        error = {
                            "error": str(e),
                            "type": type(e).__name__,
                            "timestamp": datetime.utcnow().isoformat(),
                        }

                        # Check if we should retry
                        if job.attempts + 1 < job.max_attempts:
                            # Calculate backoff
                            backoff_seconds = _calculate_backoff(
                                job.backoff_policy, job.attempts + 1
                            )

                            await job_service.mark_job_retry(job.id, error, backoff_seconds)

                            logger.info(
                                f"Job {job_id} will retry (attempt {job.attempts + 1}/"
                                f"{job.max_attempts}) after {backoff_seconds}s"
                            )
                        else:
                            # Mark as dead (permanent failure)
                            await job_service.mark_job_dead(job.id, error)
                            logger.error(
                                f"Job {job_id} marked as dead after {job.max_attempts} attempts"
                            )

                        # Delete message from SQS
                        await sqs_client.delete_message(
                            QueueUrl=queue_url, ReceiptHandle=receipt_handle
                        )

                except Exception as e:
                    logger.error(f"Error processing message: {str(e)}", exc_info=True)
                    # Don't delete message - it will become visible again

        except Exception as e:
            logger.error(f"Error in worker loop: {str(e)}", exc_info=True)
            await asyncio.sleep(5)  # Brief pause before retrying


def _calculate_backoff(backoff_policy: dict[str, Any], attempt: int) -> int:
    """
    Calculate backoff delay based on policy and attempt number.

    Args:
        backoff_policy: Backoff policy configuration
        attempt: Current attempt number (1-indexed)

    Returns:
        Backoff delay in seconds
    """
    policy_type = backoff_policy.get("type", "exponential")
    base_seconds = backoff_policy.get("base_seconds", 10)

    if policy_type == "exponential":
        # Exponential backoff: base * 2^(attempt-1)
        # Capped at 1 hour
        delay = base_seconds * (2 ** (attempt - 1))
        return min(delay, 3600)
    elif policy_type == "linear":
        # Linear backoff: base * attempt
        delay = base_seconds * attempt
        return min(delay, 3600)
    elif policy_type == "constant":
        # Constant backoff
        return base_seconds
    else:
        # Default to exponential
        delay = base_seconds * (2 ** (attempt - 1))
        return min(delay, 3600)
