"""Test models."""

from datetime import datetime, timedelta
from uuid import uuid4

from async_jobs.models import EnqueueJobRequest, Job, JobContext, JobStatus


def test_job_status_enum():
    """Test JobStatus enum values."""
    assert JobStatus.PENDING.value == "pending"
    assert JobStatus.RUNNING.value == "running"
    assert JobStatus.SUCCEEDED.value == "succeeded"
    assert JobStatus.DEAD.value == "dead"
    assert JobStatus.CANCELLED.value == "cancelled"


def test_job_creation():
    """Test Job dataclass creation."""
    job_id = uuid4()
    now = datetime.utcnow()
    job = Job(
        id=job_id,
        tenant_id="tenant1",
        use_case="notifications",
        type="send_email",
        queue="notifications-queue",
        status=JobStatus.PENDING,
        payload={"to": "test@example.com"},
        run_at=now,
        delay_tolerance=timedelta(seconds=60),
        deadline_at=now + timedelta(seconds=60),
        priority=0,
        attempts=0,
        max_attempts=3,
        backoff_policy={"type": "exponential", "base_delay_seconds": 60},
        lease_expires_at=None,
        last_error=None,
        dedupe_key=None,
        enqueue_failed=False,
        created_at=now,
        updated_at=now,
    )
    assert job.id == job_id
    assert job.tenant_id == "tenant1"
    assert job.use_case == "notifications"
    assert job.status == JobStatus.PENDING


def test_enqueue_job_request():
    """Test EnqueueJobRequest dataclass creation."""
    request = EnqueueJobRequest(
        tenant_id="tenant1",
        use_case="notifications",
        type="send_email",
        queue="notifications-queue",
        payload={"to": "test@example.com"},
        delay_tolerance_seconds=60,
        max_attempts=3,
        backoff_policy={"type": "exponential"},
        run_at=None,
        dedupe_key="email-123",
        priority=5,
    )
    assert request.tenant_id == "tenant1"
    assert request.use_case == "notifications"
    assert request.delay_tolerance_seconds == 60
    assert request.max_attempts == 3
    assert request.dedupe_key == "email-123"
    assert request.priority == 5


def test_job_context():
    """Test JobContext dataclass creation."""
    job_id = uuid4()
    context = JobContext(
        job_id=job_id,
        tenant_id="tenant1",
        use_case="notifications",
        type="send_email",
        attempt=1,
    )
    assert context.job_id == job_id
    assert context.tenant_id == "tenant1"
    assert context.use_case == "notifications"
    assert context.type == "send_email"
    assert context.attempt == 1
