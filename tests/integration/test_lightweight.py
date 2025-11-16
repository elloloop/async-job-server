"""Lightweight integration tests using testcontainers."""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4

import asyncpg
from testcontainers.postgres import PostgresContainer

from async_jobs.config import AsyncJobsConfig
from async_jobs.ddl import JOBS_TABLE_DDL
from async_jobs.models import JobStatus
from async_jobs.registry import job_registry
from async_jobs.service import JobService


@pytest.fixture(scope="module")
def postgres_container():
    """Create a PostgreSQL test container."""
    with PostgresContainer("postgres:15") as postgres:
        yield postgres


@pytest.fixture
async def db_pool(postgres_container):
    """Create a database connection pool."""
    dsn = postgres_container.get_connection_url()
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)

    # Apply schema
    async with pool.acquire() as conn:
        await conn.execute(JOBS_TABLE_DDL)

    yield pool

    await pool.close()


@pytest.fixture
def config(postgres_container):
    """Create a test config."""
    dsn = postgres_container.get_connection_url()
    return AsyncJobsConfig(
        db_dsn=dsn,
        sqs_queue_notifications="https://sqs.us-east-1.amazonaws.com/123/notifications",
        sqs_queue_message_labeling="https://sqs.us-east-1.amazonaws.com/123/labeling",
        notifications_max_concurrent=10,
        notifications_default_delay_tolerance_seconds=3,
        message_labeling_max_concurrent=10,
        message_labeling_default_delay_tolerance_seconds=3,
    )


@pytest.fixture
def service(config, db_pool):
    """Create a JobService instance."""
    return JobService(config, db_pool)


@pytest.mark.asyncio
async def test_enqueue_and_get_job(service):
    """Test enqueueing and retrieving a job."""
    job_id = await service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="send_notification",
        queue="async-notifications",
        payload={"email": "test@example.com"},
    )

    job = await service.get_job(job_id)

    assert job.id == job_id
    assert job.tenant_id == "tenant1"
    assert job.use_case == "notifications"
    assert job.type == "send_notification"
    assert job.status == JobStatus.PENDING
    assert job.payload == {"email": "test@example.com"}


@pytest.mark.asyncio
async def test_enqueue_with_dedupe_key(service):
    """Test that dedupe_key prevents duplicate jobs."""
    dedupe_key = "unique-key-123"

    job_id1 = await service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="send_notification",
        queue="async-notifications",
        payload={},
        dedupe_key=dedupe_key,
    )

    # Enqueue again with same dedupe_key
    job_id2 = await service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="send_notification",
        queue="async-notifications",
        payload={},
        dedupe_key=dedupe_key,
    )

    # Should return the same job ID
    assert job_id1 == job_id2


@pytest.mark.asyncio
async def test_quota_enforcement(service):
    """Test that quota enforcement works."""
    # Set quota
    service.config.per_tenant_quotas = {
        "tenant1": {"notifications": 2}
    }

    # Enqueue 2 jobs (should succeed)
    job_id1 = await service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="send_notification",
        queue="async-notifications",
        payload={},
    )
    job_id2 = await service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="send_notification",
        queue="async-notifications",
        payload={},
    )

    # Third job should fail
    from async_jobs.errors import QuotaExceededError

    with pytest.raises(QuotaExceededError):
        await service.enqueue(
            tenant_id="tenant1",
            use_case="notifications",
            type="send_notification",
            queue="async-notifications",
            payload={},
        )


@pytest.mark.asyncio
async def test_list_jobs(service):
    """Test listing jobs with filters."""
    # Enqueue multiple jobs
    await service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="send_notification",
        queue="async-notifications",
        payload={},
    )
    await service.enqueue(
        tenant_id="tenant2",
        use_case="notifications",
        type="send_notification",
        queue="async-notifications",
        payload={},
    )

    # List all jobs
    all_jobs = await service.list_jobs()
    assert len(all_jobs) >= 2

    # Filter by tenant
    tenant1_jobs = await service.list_jobs(tenant_id="tenant1")
    assert all(job.tenant_id == "tenant1" for job in tenant1_jobs)


@pytest.mark.asyncio
async def test_mark_job_succeeded(service):
    """Test marking a job as succeeded."""
    job_id = await service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="send_notification",
        queue="async-notifications",
        payload={},
    )

    await service.mark_job_succeeded(job_id)

    job = await service.get_job(job_id)
    assert job.status == JobStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_mark_job_retry(service):
    """Test marking a job for retry."""
    job_id = await service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="send_notification",
        queue="async-notifications",
        payload={},
        max_attempts=3,
    )

    # First mark as running (simulate scheduler)
    from async_jobs.store import JobStore
    store = JobStore(service.db_pool)
    await store.mark_jobs_as_running_and_lease([job_id])

    # Mark for retry
    await service.mark_job_retry(job_id, error={"error": "test error"})

    job = await service.get_job(job_id)
    assert job.status == JobStatus.PENDING
    assert job.attempts == 1
    assert job.last_error == {"error": "test error"}


@pytest.mark.asyncio
async def test_mark_job_dead_after_max_attempts(service):
    """Test that job is marked as dead after max attempts."""
    job_id = await service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="send_notification",
        queue="async-notifications",
        payload={},
        max_attempts=2,
    )

    # Mark as running
    from async_jobs.store import JobStore
    store = JobStore(service.db_pool)
    await store.mark_jobs_as_running_and_lease([job_id])

    # Retry once (attempts = 1)
    await service.mark_job_retry(job_id, error={"error": "error1"})
    await store.mark_jobs_as_running_and_lease([job_id])

    # Retry again (attempts = 2, should mark as dead)
    await service.mark_job_retry(job_id, error={"error": "error2"})

    job = await service.get_job(job_id)
    assert job.status == JobStatus.DEAD
