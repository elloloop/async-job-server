"""Integration tests for the async jobs library.

These tests use real Postgres (via testcontainers) and mock SQS to test
the complete flow of enqueueing, scheduling, and processing jobs.
"""

import json
import logging
from datetime import datetime, timedelta
from uuid import UUID

import asyncpg
import pytest
from testcontainers.postgres import PostgresContainer

from async_jobs.config import AsyncJobsConfig
from async_jobs.ddl import JOBS_TABLE_DDL
from async_jobs.models import JobStatus
from async_jobs.registry import JobRegistry
from async_jobs.service import JobService


class MockSQSClient:
    """Mock SQS client for testing."""

    def __init__(self):
        self.messages: dict[str, list[dict]] = {}
        self.deleted_messages: list[str] = []

    async def send_message(self, QueueUrl: str, MessageBody: str):
        """Mock send_message."""
        if QueueUrl not in self.messages:
            self.messages[QueueUrl] = []

        message = {
            "MessageId": f"msg-{len(self.messages[QueueUrl])}",
            "ReceiptHandle": f"receipt-{len(self.messages[QueueUrl])}",
            "Body": MessageBody,
        }
        self.messages[QueueUrl].append(message)
        return {"MessageId": message["MessageId"]}

    async def receive_message(
        self,
        QueueUrl: str,
        MaxNumberOfMessages: int = 1,
        WaitTimeSeconds: int = 0,
        AttributeNames: list[str] = None,
    ):
        """Mock receive_message."""
        if QueueUrl not in self.messages:
            return {}

        messages = self.messages[QueueUrl][:MaxNumberOfMessages]
        return {"Messages": messages} if messages else {}

    async def delete_message(self, QueueUrl: str, ReceiptHandle: str):
        """Mock delete_message."""
        self.deleted_messages.append(ReceiptHandle)
        if QueueUrl in self.messages:
            self.messages[QueueUrl] = [
                m for m in self.messages[QueueUrl] if m["ReceiptHandle"] != ReceiptHandle
            ]
        return {}


@pytest.fixture
async def postgres_container():
    """Provide a PostgreSQL test container."""
    with PostgresContainer("postgres:15") as postgres:
        yield postgres


@pytest.fixture
async def db_pool(postgres_container):
    """Create a database pool and set up schema."""
    conn_string = postgres_container.get_connection_url()

    # Create pool
    pool = await asyncpg.create_pool(conn_string, min_size=2, max_size=10)

    # Create schema
    async with pool.acquire() as conn:
        await conn.execute(JOBS_TABLE_DDL)

    yield pool

    # Cleanup
    await pool.close()


@pytest.fixture
def config(postgres_container):
    """Create test configuration."""
    return AsyncJobsConfig(
        db_dsn=postgres_container.get_connection_url(),
        sqs_queue_notifications="https://sqs.us-east-1.amazonaws.com/123/notifications",
        sqs_queue_message_labeling="https://sqs.us-east-1.amazonaws.com/123/labeling",
        notifications_max_concurrent=10,
        notifications_default_delay_tolerance_seconds=300,
        message_labeling_max_concurrent=5,
        message_labeling_default_delay_tolerance_seconds=600,
    )


@pytest.fixture
def mock_sqs():
    """Provide mock SQS client."""
    return MockSQSClient()


@pytest.fixture
def job_registry():
    """Create a fresh job registry with test handlers."""
    registry = JobRegistry()

    @registry.handler("test_success")
    async def test_success(ctx, payload):
        """Handler that succeeds."""
        ctx["logger"].info(f"Processing job with payload: {payload}")

    @registry.handler("test_failure")
    async def test_failure(ctx, payload):
        """Handler that fails."""
        raise ValueError("Intentional test failure")

    return registry


@pytest.mark.asyncio
async def test_enqueue_and_schedule_job(db_pool, config, mock_sqs):
    """Test enqueueing a job and scheduling it."""
    logger = logging.getLogger("test")
    job_service = JobService(config, db_pool, logger)

    # Enqueue a job
    job_id = await job_service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="test_success",
        queue=config.sqs_queue_notifications,
        payload={"message": "Hello World"},
        run_at=datetime.utcnow(),
    )

    assert job_id is not None
    assert isinstance(job_id, UUID)

    # Verify job is in database
    job = await job_service.get_job(job_id)
    assert job.status == JobStatus.pending
    assert job.tenant_id == "tenant1"
    assert job.use_case == "notifications"
    assert job.type == "test_success"

    # Run scheduler once (simulate single iteration)
    jobs = await job_service.lease_jobs_for_use_case(
        use_case="notifications", max_count=10, lease_duration=timedelta(minutes=10)
    )

    assert len(jobs) == 1
    assert jobs[0].id == job_id

    # Send to SQS manually (simulate scheduler)
    await mock_sqs.send_message(
        QueueUrl=config.sqs_queue_notifications,
        MessageBody=json.dumps({"job_id": str(job_id)}),
    )

    # Verify job is now in running state
    job = await job_service.get_job(job_id)
    assert job.status == JobStatus.running

    # Verify message in SQS
    assert config.sqs_queue_notifications in mock_sqs.messages
    assert len(mock_sqs.messages[config.sqs_queue_notifications]) == 1


@pytest.mark.asyncio
async def test_worker_processes_successful_job(db_pool, config, mock_sqs, job_registry):
    """Test that worker successfully processes a job."""
    logger = logging.getLogger("test")
    job_service = JobService(config, db_pool, logger)

    # Enqueue and lease a job
    job_id = await job_service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="test_success",
        queue=config.sqs_queue_notifications,
        payload={"message": "Test"},
        run_at=datetime.utcnow(),
    )

    _ = await job_service.lease_jobs_for_use_case(
        use_case="notifications", max_count=10, lease_duration=timedelta(minutes=10)
    )

    # Add to SQS
    await mock_sqs.send_message(
        QueueUrl=config.sqs_queue_notifications,
        MessageBody=json.dumps({"job_id": str(job_id)}),
    )

    # Process the job (simulate worker receiving and processing one message)
    response = await mock_sqs.receive_message(
        QueueUrl=config.sqs_queue_notifications, MaxNumberOfMessages=1
    )

    messages = response.get("Messages", [])
    assert len(messages) == 1

    message = messages[0]
    body = json.loads(message["Body"])
    job_id_from_msg = UUID(body["job_id"])

    # Load and process job
    job = await job_service.get_job(job_id_from_msg)
    assert job.status == JobStatus.running

    # Execute handler
    handler = job_registry.get_handler(job.type)
    ctx = {"job": job, "logger": logger}
    await handler(ctx, job.payload)

    # Mark as succeeded
    await job_service.mark_job_succeeded(job.id)

    # Delete message
    await mock_sqs.delete_message(
        QueueUrl=config.sqs_queue_notifications, ReceiptHandle=message["ReceiptHandle"]
    )

    # Verify job is succeeded
    job = await job_service.get_job(job_id)
    assert job.status == JobStatus.succeeded

    # Verify message deleted
    assert message["ReceiptHandle"] in mock_sqs.deleted_messages


@pytest.mark.asyncio
async def test_worker_handles_job_failure_with_retry(db_pool, config, mock_sqs, job_registry):
    """Test that worker handles job failure and schedules retry."""
    logger = logging.getLogger("test")
    job_service = JobService(config, db_pool, logger)

    # Enqueue and lease a failing job
    job_id = await job_service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="test_failure",
        queue=config.sqs_queue_notifications,
        payload={"message": "Test"},
        run_at=datetime.utcnow(),
        max_attempts=3,
    )

    _ = await job_service.lease_jobs_for_use_case(
        use_case="notifications", max_count=10, lease_duration=timedelta(minutes=10)
    )

    await mock_sqs.send_message(
        QueueUrl=config.sqs_queue_notifications,
        MessageBody=json.dumps({"job_id": str(job_id)}),
    )

    # Process the job
    response = await mock_sqs.receive_message(
        QueueUrl=config.sqs_queue_notifications, MaxNumberOfMessages=1
    )
    message = response["Messages"][0]
    body = json.loads(message["Body"])
    job_id_from_msg = UUID(body["job_id"])

    job = await job_service.get_job(job_id_from_msg)

    # Execute handler (will fail)
    handler = job_registry.get_handler(job.type)
    ctx = {"job": job, "logger": logger}

    try:
        await handler(ctx, job.payload)
        assert False, "Handler should have raised an exception"
    except ValueError:
        # Expected failure
        pass

    # Mark for retry
    error = {"error": "Intentional test failure", "type": "ValueError"}
    await job_service.mark_job_retry(job.id, error, backoff_seconds=10)

    # Delete message
    await mock_sqs.delete_message(
        QueueUrl=config.sqs_queue_notifications, ReceiptHandle=message["ReceiptHandle"]
    )

    # Verify job is pending again with incremented attempts
    job = await job_service.get_job(job_id)
    assert job.status == JobStatus.pending
    assert job.attempts == 1
    assert job.last_error is not None


@pytest.mark.asyncio
async def test_quota_enforcement(db_pool, config):
    """Test that quota enforcement works."""
    logger = logging.getLogger("test")

    # Set quota for tenant
    config.per_tenant_quotas = {"tenant1": {"notifications": 2}}

    job_service = JobService(config, db_pool, logger)

    # Enqueue two jobs (should succeed)
    job_id1 = await job_service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="test",
        queue=config.sqs_queue_notifications,
        payload={},
    )
    assert job_id1 is not None

    job_id2 = await job_service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="test",
        queue=config.sqs_queue_notifications,
        payload={},
    )
    assert job_id2 is not None

    # Third job should fail quota check
    from async_jobs.errors import QuotaExceededError

    with pytest.raises(QuotaExceededError):
        await job_service.enqueue(
            tenant_id="tenant1",
            use_case="notifications",
            type="test",
            queue=config.sqs_queue_notifications,
            payload={},
        )


@pytest.mark.asyncio
async def test_deadline_calculation(db_pool, config):
    """Test that deadline is calculated correctly."""
    logger = logging.getLogger("test")
    job_service = JobService(config, db_pool, logger)

    run_at = datetime.utcnow()
    delay_tolerance = timedelta(seconds=300)

    job_id = await job_service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="test",
        queue=config.sqs_queue_notifications,
        payload={},
        run_at=run_at,
        delay_tolerance=delay_tolerance,
    )

    job = await job_service.get_job(job_id)

    # Deadline should be run_at + delay_tolerance
    expected_deadline = run_at + delay_tolerance

    # Allow 1 second tolerance for test execution time
    assert abs((job.deadline_at - expected_deadline).total_seconds()) < 1


@pytest.mark.asyncio
async def test_list_jobs_filtering(db_pool, config):
    """Test listing jobs with filters."""
    logger = logging.getLogger("test")
    job_service = JobService(config, db_pool, logger)

    # Create jobs for different tenants and use cases
    await job_service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="test1",
        queue=config.sqs_queue_notifications,
        payload={},
    )

    await job_service.enqueue(
        tenant_id="tenant1",
        use_case="message_labeling",
        type="test2",
        queue=config.sqs_queue_message_labeling,
        payload={},
    )

    await job_service.enqueue(
        tenant_id="tenant2",
        use_case="notifications",
        type="test3",
        queue=config.sqs_queue_notifications,
        payload={},
    )

    # List all jobs
    all_jobs = await job_service.list_jobs()
    assert len(all_jobs) >= 3

    # Filter by tenant
    tenant1_jobs = await job_service.list_jobs(tenant_id="tenant1")
    assert len(tenant1_jobs) == 2
    assert all(job.tenant_id == "tenant1" for job in tenant1_jobs)

    # Filter by use case
    notification_jobs = await job_service.list_jobs(use_case="notifications")
    assert len(notification_jobs) == 2
    assert all(job.use_case == "notifications" for job in notification_jobs)

    # Filter by tenant and use case
    tenant1_notifications = await job_service.list_jobs(
        tenant_id="tenant1", use_case="notifications"
    )
    assert len(tenant1_notifications) == 1
    assert tenant1_notifications[0].tenant_id == "tenant1"
    assert tenant1_notifications[0].use_case == "notifications"
