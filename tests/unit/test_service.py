"""Unit tests for service module."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from async_jobs.config import AsyncJobsConfig
from async_jobs.errors import JobNotFoundError, QuotaExceededError
from async_jobs.models import Job, JobStatus
from async_jobs.service import JobService


@pytest.fixture
def mock_config():
    """Create a mock config."""
    config = MagicMock(spec=AsyncJobsConfig)
    config.get_default_delay_tolerance_seconds_for_use_case.return_value = 3
    config.get_quota_for_tenant_use_case.return_value = None
    config.per_use_case_config = {
        "notifications": {
            "max_concurrent": 10,
            "default_delay_tolerance_seconds": 3,
        }
    }
    return config


@pytest.fixture
def mock_db_pool():
    """Create a mock database pool."""
    pool = AsyncMock()
    return pool


@pytest.fixture
def service(mock_config, mock_db_pool):
    """Create a JobService instance."""
    return JobService(mock_config, mock_db_pool)


@pytest.mark.asyncio
async def test_enqueue_job_success(service, mock_config):
    """Test successful job enqueue."""
    job_id = uuid4()
    run_at = datetime.utcnow()
    delay_tolerance = timedelta(seconds=3)
    deadline_at = run_at + delay_tolerance

    with patch.object(service.store, "count_pending_jobs_for_tenant", return_value=0):
        with patch.object(service.store, "insert_job", return_value=job_id):
            result = await service.enqueue(
                tenant_id="tenant1",
                use_case="notifications",
                type="send_notification",
                queue="async-notifications",
                payload={"email": "test@example.com"},
                run_at=run_at,
                delay_tolerance=delay_tolerance,
            )

    assert result == job_id


@pytest.mark.asyncio
async def test_enqueue_job_calculates_deadline_at(service, mock_config):
    """Test that deadline_at is calculated correctly."""
    job_id = uuid4()
    run_at = datetime.utcnow()
    delay_tolerance = timedelta(seconds=5)
    expected_deadline = run_at + delay_tolerance

    with patch.object(service.store, "count_pending_jobs_for_tenant", return_value=0):
        with patch.object(service.store, "insert_job") as mock_insert:
            await service.enqueue(
                tenant_id="tenant1",
                use_case="notifications",
                type="send_notification",
                queue="async-notifications",
                payload={},
                run_at=run_at,
                delay_tolerance=delay_tolerance,
            )

            call_kwargs = mock_insert.call_args[1]
            assert call_kwargs["deadline_at"] == expected_deadline


@pytest.mark.asyncio
async def test_enqueue_job_applies_default_delay_tolerance(service, mock_config):
    """Test that default delay tolerance is applied when not provided."""
    job_id = uuid4()
    run_at = datetime.utcnow()
    mock_config.get_default_delay_tolerance_seconds_for_use_case.return_value = 5

    with patch.object(service.store, "count_pending_jobs_for_tenant", return_value=0):
        with patch.object(service.store, "insert_job") as mock_insert:
            await service.enqueue(
                tenant_id="tenant1",
                use_case="notifications",
                type="send_notification",
                queue="async-notifications",
                payload={},
                run_at=run_at,
            )

            call_kwargs = mock_insert.call_args[1]
            assert call_kwargs["delay_tolerance"] == timedelta(seconds=5)


@pytest.mark.asyncio
async def test_enqueue_job_quota_exceeded(service, mock_config):
    """Test that quota exceeded raises QuotaExceededError."""
    mock_config.get_quota_for_tenant_use_case.return_value = 10

    with patch.object(service.store, "count_pending_jobs_for_tenant", return_value=10):
        with pytest.raises(QuotaExceededError):
            await service.enqueue(
                tenant_id="tenant1",
                use_case="notifications",
                type="send_notification",
                queue="async-notifications",
                payload={},
            )


@pytest.mark.asyncio
async def test_enqueue_job_quota_not_exceeded(service, mock_config):
    """Test that job can be enqueued when quota is not exceeded."""
    job_id = uuid4()
    mock_config.get_quota_for_tenant_use_case.return_value = 10

    with patch.object(service.store, "count_pending_jobs_for_tenant", return_value=9):
        with patch.object(service.store, "insert_job", return_value=job_id):
            result = await service.enqueue(
                tenant_id="tenant1",
                use_case="notifications",
                type="send_notification",
                queue="async-notifications",
                payload={},
            )

    assert result == job_id


@pytest.mark.asyncio
async def test_get_job_success(service):
    """Test getting a job successfully."""
    job_id = uuid4()
    job = Job(
        id=job_id,
        tenant_id="tenant1",
        use_case="notifications",
        type="send_notification",
        queue="async-notifications",
        status=JobStatus.PENDING,
        payload={},
        run_at=datetime.utcnow(),
        delay_tolerance="3 seconds",
        deadline_at=datetime.utcnow(),
        priority=0,
        attempts=0,
        max_attempts=5,
        backoff_policy={},
    )

    with patch.object(service.store, "get_job", return_value=job):
        result = await service.get_job(job_id)

    assert result.id == job_id


@pytest.mark.asyncio
async def test_get_job_not_found(service):
    """Test getting a non-existent job raises JobNotFoundError."""
    job_id = uuid4()

    with patch.object(service.store, "get_job", return_value=None):
        with pytest.raises(JobNotFoundError):
            await service.get_job(job_id)


@pytest.mark.asyncio
async def test_mark_job_retry_calculates_backoff(service):
    """Test that retry calculates backoff correctly."""
    job_id = uuid4()
    job = Job(
        id=job_id,
        tenant_id="tenant1",
        use_case="notifications",
        type="send_notification",
        queue="async-notifications",
        status=JobStatus.RUNNING,
        payload={},
        run_at=datetime.utcnow(),
        delay_tolerance="3 seconds",
        deadline_at=datetime.utcnow(),
        priority=0,
        attempts=1,
        max_attempts=5,
        backoff_policy={"type": "exponential", "base_seconds": 10},
    )

    with patch.object(service.store, "get_job", return_value=job):
        with patch.object(service.store, "update_job_retry") as mock_update:
            await service.mark_job_retry(job_id, error={"error": "test"})

            call_kwargs = mock_update.call_args[1]
            assert call_kwargs["attempts"] == 2
            assert call_kwargs["next_run_at"] > datetime.utcnow()


@pytest.mark.asyncio
async def test_mark_job_retry_exceeds_max_attempts(service):
    """Test that retry marks job as dead when max attempts exceeded."""
    job_id = uuid4()
    job = Job(
        id=job_id,
        tenant_id="tenant1",
        use_case="notifications",
        type="send_notification",
        queue="async-notifications",
        status=JobStatus.RUNNING,
        payload={},
        run_at=datetime.utcnow(),
        delay_tolerance="3 seconds",
        deadline_at=datetime.utcnow(),
        priority=0,
        attempts=5,
        max_attempts=5,
        backoff_policy={"type": "exponential", "base_seconds": 10},
    )

    with patch.object(service.store, "get_job", return_value=job):
        with patch.object(service.store, "update_job_dead") as mock_dead:
            await service.mark_job_retry(job_id, error={"error": "test"})

            mock_dead.assert_called_once()
