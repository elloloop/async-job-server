"""
End-to-end integration test for the async jobs system.

This test validates the complete flow: enqueue -> schedule -> process
It can run in two modes:
1. With testcontainers (default) - spins up its own Postgres
2. With external services (CI mode) - uses environment-provided services
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from uuid import UUID

import aioboto3
import asyncpg
import pytest

from async_jobs.config import AsyncJobsConfig
from async_jobs.ddl import JOBS_TABLE_DDL
from async_jobs.models import JobStatus
from async_jobs.registry import JobRegistry
from async_jobs.service import JobService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def use_external_services():
    """Check if we should use external services (CI mode) or testcontainers."""
    return os.getenv("USE_EXTERNAL_SERVICES", "false").lower() == "true"


@pytest.fixture(scope="session")
def postgres_container():
    """Provide PostgreSQL container for local testing."""
    if use_external_services():
        # In CI mode, no container needed
        yield None
    else:
        # Use testcontainers (local development)
        pytest.importorskip("testcontainers")
        from testcontainers.postgres import PostgresContainer

        with PostgresContainer("postgres:15") as postgres:
            yield postgres


@pytest.fixture
def config(postgres_container):
    """Create test configuration."""
    if use_external_services():
        # Use environment variables (CI mode)
        return AsyncJobsConfig.from_env()
    else:
        # Use testcontainers (local development)
        return AsyncJobsConfig(
            db_dsn=postgres_container.get_connection_url(),
            sqs_queue_notifications="http://localhost:4566/000000000000/notifications",
            sqs_queue_message_labeling="http://localhost:4566/000000000000/message-labeling",
            notifications_max_concurrent=10,
            notifications_default_delay_tolerance_seconds=300,
            message_labeling_max_concurrent=5,
            message_labeling_default_delay_tolerance_seconds=600,
        )


@pytest.fixture
async def db_pool(config):
    """Create a database pool and set up schema."""
    pool = await asyncpg.create_pool(config.db_dsn, min_size=2, max_size=10)

    yield pool

    # Cleanup
    await pool.close()


@pytest.fixture
async def clean_db(db_pool):
    """Clean database before each test."""
    async with db_pool.acquire() as conn:
        # Drop table if exists for clean slate
        await conn.execute("DROP TABLE IF EXISTS jobs")
        await conn.execute(JOBS_TABLE_DDL)
    yield


@pytest.fixture
async def clean_queues(sqs_client, config):
    """Purge SQS queues before each test."""
    try:
        await sqs_client.purge_queue(QueueUrl=config.sqs_queue_notifications)
    except Exception as e:
        logger.warning(f"Could not purge notifications queue: {e}")
    
    try:
        await sqs_client.purge_queue(QueueUrl=config.sqs_queue_message_labeling)
    except Exception as e:
        logger.warning(f"Could not purge message_labeling queue: {e}")
    
    yield


@pytest.fixture
async def sqs_client(config):
    """Create SQS client."""
    session = aioboto3.Session()

    # Get endpoint URL from environment if set (for LocalStack)
    endpoint_url = os.getenv("AWS_ENDPOINT_URL")
    sqs_kwargs = {}
    if endpoint_url:
        sqs_kwargs["endpoint_url"] = endpoint_url

    async with session.client("sqs", **sqs_kwargs) as client:
        # Create queues if they don't exist (for LocalStack)
        if endpoint_url:
            try:
                await client.create_queue(QueueName="notifications")
                await client.create_queue(QueueName="message-labeling")
            except Exception as e:
                logger.warning(f"Queue creation warning: {e}")

        yield client


@pytest.fixture
def job_registry():
    """Create a fresh job registry with test handlers."""
    registry = JobRegistry()

    @registry.handler("test_success")
    async def test_success(ctx, payload):
        """Handler that succeeds."""
        logger.info(f"Processing successful job: {payload}")
        ctx["logger"].info(f"Job {ctx['job'].id} completed successfully")

    @registry.handler("test_failure")
    async def test_failure(ctx, payload):
        """Handler that fails."""
        raise ValueError("Intentional test failure")

    @registry.handler("send_notification")
    async def send_notification(ctx, payload):
        """Handler for notifications."""
        logger.info(f"Sending notification: {payload}")
        ctx["logger"].info(f"Notification sent for job {ctx['job'].id}")

    return registry


@pytest.mark.asyncio
async def test_end_to_end_job_flow(clean_db, clean_queues, db_pool, config, sqs_client, job_registry):
    """
    Test the complete end-to-end flow:
    1. Enqueue a job
    2. Scheduler leases and sends to SQS
    3. Worker receives from SQS and processes
    4. Job is marked as succeeded
    """
    job_service = JobService(config, db_pool, logger)

    # Step 1: Enqueue a job
    logger.info("Step 1: Enqueueing job...")
    job_id = await job_service.enqueue(
        tenant_id="test-tenant",
        use_case="notifications",
        type="test_success",
        queue=config.sqs_queue_notifications,
        payload={"message": "End-to-end test", "priority": "high"},
        run_at=datetime.utcnow(),
    )

    assert job_id is not None
    assert isinstance(job_id, UUID)
    logger.info(f"Job enqueued with ID: {job_id}")

    # Verify job is in pending state
    job = await job_service.get_job(job_id)
    assert job.status == JobStatus.pending
    assert job.type == "test_success"

    # Step 2: Simulate scheduler - lease jobs and send to SQS
    logger.info("Step 2: Scheduler leasing jobs...")
    jobs = await job_service.lease_jobs_for_use_case(
        use_case="notifications", max_count=10, lease_duration=timedelta(minutes=10)
    )

    assert len(jobs) >= 1
    leased_job = next((j for j in jobs if j.id == job_id), None)
    assert leased_job is not None
    logger.info(f"Leased {len(jobs)} job(s)")

    # Send to SQS
    await sqs_client.send_message(
        QueueUrl=config.sqs_queue_notifications,
        MessageBody=json.dumps({"job_id": str(job_id)}),
    )
    logger.info("Job sent to SQS")

    # Verify job is now in running state
    job = await job_service.get_job(job_id)
    assert job.status == JobStatus.running

    # Step 3: Simulate worker - receive from SQS and process
    logger.info("Step 3: Worker processing job...")
    response = await sqs_client.receive_message(
        QueueUrl=config.sqs_queue_notifications,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=5,
    )

    assert "Messages" in response
    messages = response["Messages"]
    assert len(messages) >= 1

    message = messages[0]
    body = json.loads(message["Body"])
    job_id_from_msg = UUID(body["job_id"])
    assert job_id_from_msg == job_id

    # Process the job
    job = await job_service.get_job(job_id_from_msg)
    handler = job_registry.get_handler(job.type)
    assert handler is not None

    ctx = {"job": job, "logger": logger}
    await handler(ctx, job.payload)

    # Mark as succeeded
    await job_service.mark_job_succeeded(job.id)
    logger.info("Job processed and marked as succeeded")

    # Delete message from SQS
    await sqs_client.delete_message(
        QueueUrl=config.sqs_queue_notifications, ReceiptHandle=message["ReceiptHandle"]
    )
    logger.info("Message deleted from SQS")

    # Step 4: Verify final state
    logger.info("Step 4: Verifying final state...")
    job = await job_service.get_job(job_id)
    assert job.status == JobStatus.succeeded
    assert job.attempts == 0  # Should still be 0 as it succeeded on first try

    logger.info("✅ End-to-end test passed!")


@pytest.mark.asyncio
async def test_multiple_jobs_different_use_cases(clean_db, clean_queues, db_pool, config, sqs_client, job_registry):
    """
    Test handling multiple jobs across different use cases.
    """
    job_service = JobService(config, db_pool, logger)

    # Enqueue multiple jobs
    logger.info("Enqueueing multiple jobs...")
    job_ids = []

    # Notification jobs
    for i in range(3):
        job_id = await job_service.enqueue(
            tenant_id=f"tenant-{i}",
            use_case="notifications",
            type="send_notification",
            queue=config.sqs_queue_notifications,
            payload={"email": f"user{i}@example.com", "message": f"Test {i}"},
            run_at=datetime.utcnow(),
        )
        job_ids.append((job_id, "notifications"))

    logger.info(f"Enqueued {len(job_ids)} jobs")

    # Lease all notification jobs
    jobs = await job_service.lease_jobs_for_use_case(
        use_case="notifications", max_count=10, lease_duration=timedelta(minutes=10)
    )

    assert len(jobs) >= 3
    logger.info(f"Leased {len(jobs)} jobs")

    # Send all to SQS
    for job in jobs:
        await sqs_client.send_message(
            QueueUrl=config.sqs_queue_notifications,
            MessageBody=json.dumps({"job_id": str(job.id)}),
        )

    # Process jobs
    processed = 0
    for _ in range(len(jobs)):
        response = await sqs_client.receive_message(
            QueueUrl=config.sqs_queue_notifications,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=5,
        )

        if "Messages" not in response or not response["Messages"]:
            break

        message = response["Messages"][0]
        body = json.loads(message["Body"])
        job_id = UUID(body["job_id"])

        job = await job_service.get_job(job_id)
        handler = job_registry.get_handler(job.type)

        if handler:
            ctx = {"job": job, "logger": logger}
            await handler(ctx, job.payload)
            await job_service.mark_job_succeeded(job.id)
            await sqs_client.delete_message(
                QueueUrl=config.sqs_queue_notifications,
                ReceiptHandle=message["ReceiptHandle"],
            )
            processed += 1

    logger.info(f"Processed {processed} jobs")
    assert processed >= 3

    # Verify all jobs succeeded
    for job_id, _ in job_ids:
        job = await job_service.get_job(job_id)
        assert job.status == JobStatus.succeeded

    logger.info("✅ Multiple jobs test passed!")


@pytest.mark.asyncio
async def test_job_failure_and_retry(clean_db, clean_queues, db_pool, config, sqs_client, job_registry):
    """
    Test job failure handling mechanism.
    """
    job_service = JobService(config, db_pool, logger)

    # Enqueue a job that will fail
    logger.info("Enqueueing failing job...")
    job_id = await job_service.enqueue(
        tenant_id="test-tenant",
        use_case="notifications",
        type="test_failure",
        queue=config.sqs_queue_notifications,
        payload={"test": "failure"},
        run_at=datetime.utcnow(),
        max_attempts=3,
    )

    # Lease and send to SQS
    jobs = await job_service.lease_jobs_for_use_case(
        use_case="notifications", max_count=1, lease_duration=timedelta(minutes=10)
    )
    assert len(jobs) == 1

    await sqs_client.send_message(
        QueueUrl=config.sqs_queue_notifications,
        MessageBody=json.dumps({"job_id": str(job_id)}),
    )

    # Process the job (it will fail)
    response = await sqs_client.receive_message(
        QueueUrl=config.sqs_queue_notifications, MaxNumberOfMessages=1, WaitTimeSeconds=5
    )

    message = response["Messages"][0]
    body = json.loads(message["Body"])
    job_id_from_msg = UUID(body["job_id"])

    job = await job_service.get_job(job_id_from_msg)
    handler = job_registry.get_handler(job.type)

    # Execute handler (it should fail)
    error_msg = None
    error_type = None
    try:
        ctx = {"job": job, "logger": logger}
        await handler(ctx, job.payload)
        assert False, "Handler should have raised an exception"
    except ValueError as e:
        logger.info(f"Expected failure: {e}")
        error_msg = str(e)
        error_type = type(e).__name__

    # Verify the error was caught
    assert error_msg == "Intentional test failure"
    assert error_type == "ValueError"

    # Delete message from SQS
    await sqs_client.delete_message(
        QueueUrl=config.sqs_queue_notifications, ReceiptHandle=message["ReceiptHandle"]
    )

    # Verify job is still in running state (handler failed)
    job = await job_service.get_job(job_id)
    assert job.status == JobStatus.running

    logger.info("✅ Failure handling test passed!")
