"""Worker core logic."""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from async_jobs.config import AsyncJobsConfig
from async_jobs.errors import JobNotFoundError
from async_jobs.models import JobStatus
from async_jobs.registry import JobRegistry
from async_jobs.service import JobService


logger = logging.getLogger(__name__)


async def run_worker_loop(
    config: AsyncJobsConfig,
    db_pool: Any,
    sqs_client: Any,
    registry: JobRegistry,
    queue_name: str,
    logger: logging.Logger,
    shutdown_event: asyncio.Event = None,
    max_messages: int = 10,
    wait_time_seconds: int = 20,
) -> None:
    """
    Run the worker loop.

    Long-polls SQS for the given queue:
    - For each message:
      - Parse job_id
      - Load job from DB
      - If job.status != 'running': delete message and continue
      - Resolve handler from registry
      - Execute handler
      - Update job state: succeeded, retry, or dead
        - Handle backoff and increment attempts
      - Delete SQS message

    Args:
        config: AsyncJobsConfig instance
        db_pool: Database connection pool
        sqs_client: Boto3 SQS client
        registry: JobRegistry instance
        queue_name: Queue name (e.g., "async-notifications")
        logger: Logger instance
        shutdown_event: Optional asyncio.Event to signal shutdown
        max_messages: Max messages to receive per poll
        wait_time_seconds: Long poll wait time
    """
    job_service = JobService(config, db_pool, logger)

    # Find queue URL from config
    queue_url = None
    for use_case, url in config.use_case_to_queue.items():
        # Try to match by queue name or URL
        if queue_name in url or url.endswith(f"/{queue_name}"):
            queue_url = url
            break

    if not queue_url:
        # Try to get queue URL directly
        try:
            response = sqs_client.get_queue_url(QueueName=queue_name)
            queue_url = response["QueueUrl"]
        except ClientError as e:
            logger.error(f"Failed to get queue URL for {queue_name}: {e}")
            raise

    if shutdown_event is None:
        shutdown_event = asyncio.Event()

    logger.info(f"Worker loop started for queue {queue_name} ({queue_url})")

    while not shutdown_event.is_set():
        try:
            # Receive messages from SQS
            try:
                response = sqs_client.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=max_messages,
                    WaitTimeSeconds=wait_time_seconds,
                    MessageAttributeNames=["All"],
                )
            except ClientError as e:
                logger.error(f"Error receiving messages from SQS: {e}")
                await asyncio.sleep(1)
                continue

            messages = response.get("Messages", [])
            if not messages:
                continue

            logger.debug(f"Received {len(messages)} messages from queue")

            # Process each message
            for message in messages:
                if shutdown_event.is_set():
                    break

                receipt_handle = message["ReceiptHandle"]
                message_body = json.loads(message["Body"])

                try:
                    job_id_str = message_body.get("job_id")
                    if not job_id_str:
                        logger.warning(
                            f"Message missing job_id, deleting: {message_body}"
                        )
                        sqs_client.delete_message(
                            QueueUrl=queue_url, ReceiptHandle=receipt_handle
                        )
                        continue

                    from uuid import UUID

                    try:
                        job_id = UUID(job_id_str)
                    except ValueError:
                        logger.warning(f"Invalid job_id format: {job_id_str}")
                        sqs_client.delete_message(
                            QueueUrl=queue_url, ReceiptHandle=receipt_handle
                        )
                        continue

                    # Load job from DB
                    try:
                        job = await job_service.get_job(job_id)
                    except JobNotFoundError:
                        logger.warning(f"Job {job_id} not found, deleting message")
                        sqs_client.delete_message(
                            QueueUrl=queue_url, ReceiptHandle=receipt_handle
                        )
                        continue

                    # Check if job is in running state
                    if job.status != JobStatus.RUNNING:
                        logger.info(
                            f"Job {job_id} is not in running state ({job.status}), deleting message"
                        )
                        sqs_client.delete_message(
                            QueueUrl=queue_url, ReceiptHandle=receipt_handle
                        )
                        continue

                    # Get handler
                    handler = registry.get_handler(job.type)
                    if not handler:
                        error = {
                            "error": f"Handler not found for job type: {job.type}",
                            "job_id": str(job.id),
                        }
                        logger.error(error["error"])
                        await job_service.mark_job_dead(job_id, error)
                        sqs_client.delete_message(
                            QueueUrl=queue_url, ReceiptHandle=receipt_handle
                        )
                        continue

                    # Execute handler
                    logger.info(f"Executing handler {job.type} for job {job_id}")
                    try:
                        # Create context object
                        ctx = {
                            "job_id": job.id,
                            "tenant_id": job.tenant_id,
                            "use_case": job.use_case,
                            "attempt": job.attempts + 1,
                        }

                        # Execute handler (assume it's async)
                        if asyncio.iscoroutinefunction(handler):
                            await handler(ctx, job.payload)
                        else:
                            handler(ctx, job.payload)

                        # Mark as succeeded
                        await job_service.mark_job_succeeded(job_id)
                        logger.info(f"Job {job_id} succeeded")

                    except Exception as handler_error:
                        error = {
                            "error": str(handler_error),
                            "error_type": type(handler_error).__name__,
                            "attempt": job.attempts + 1,
                        }
                        logger.error(
                            f"Handler error for job {job_id}: {handler_error}",
                            exc_info=True,
                        )

                        # Mark for retry or dead
                        await job_service.mark_job_retry(job_id, error=error)

                    # Delete message after processing
                    sqs_client.delete_message(
                        QueueUrl=queue_url, ReceiptHandle=receipt_handle
                    )

                except Exception as e:
                    logger.error(
                        f"Error processing message: {e}",
                        exc_info=True,
                    )
                    # Don't delete message on error - let it retry via SQS visibility timeout
                    continue

        except Exception as e:
            logger.error(f"Error in worker loop: {e}", exc_info=True)
            await asyncio.sleep(1)

    logger.info("Worker loop stopped")
