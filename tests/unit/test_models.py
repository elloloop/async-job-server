"""Unit tests for models module."""

from datetime import datetime, timedelta
from uuid import uuid4

from async_jobs.models import Job, JobStatus


def test_job_status_enum():
    """Test JobStatus enum values."""
    assert JobStatus.pending.value == "pending"
    assert JobStatus.running.value == "running"
    assert JobStatus.succeeded.value == "succeeded"
    assert JobStatus.dead.value == "dead"
    assert JobStatus.cancelled.value == "cancelled"


def test_job_creation():
    """Test creating a Job instance."""
    job_id = uuid4()
    now = datetime.utcnow()
    run_at = now + timedelta(minutes=5)
    delay_tolerance = timedelta(seconds=300)
    deadline_at = run_at + delay_tolerance

    job = Job(
        id=job_id,
        tenant_id="tenant1",
        use_case="notifications",
        type="send_email",
        queue="queue-url",
        status=JobStatus.pending,
        payload={"email": "test@example.com"},
        run_at=run_at,
        delay_tolerance=delay_tolerance,
        deadline_at=deadline_at,
        priority=0,
        attempts=0,
        max_attempts=5,
        backoff_policy={"type": "exponential", "base_seconds": 10},
    )

    assert job.id == job_id
    assert job.tenant_id == "tenant1"
    assert job.use_case == "notifications"
    assert job.type == "send_email"
    assert job.status == JobStatus.pending
    assert job.payload == {"email": "test@example.com"}
    assert job.attempts == 0
    assert job.max_attempts == 5


def test_job_to_dict():
    """Test converting Job to dictionary."""
    job_id = uuid4()
    now = datetime.utcnow()
    run_at = now + timedelta(minutes=5)
    delay_tolerance = timedelta(seconds=300)
    deadline_at = run_at + delay_tolerance

    job = Job(
        id=job_id,
        tenant_id="tenant1",
        use_case="notifications",
        type="send_email",
        queue="queue-url",
        status=JobStatus.pending,
        payload={"email": "test@example.com"},
        run_at=run_at,
        delay_tolerance=delay_tolerance,
        deadline_at=deadline_at,
        priority=5,
        attempts=0,
        max_attempts=5,
        backoff_policy={"type": "exponential", "base_seconds": 10},
        dedupe_key="test-dedupe",
        created_at=now,
        updated_at=now,
    )

    job_dict = job.to_dict()

    assert job_dict["id"] == str(job_id)
    assert job_dict["tenant_id"] == "tenant1"
    assert job_dict["use_case"] == "notifications"
    assert job_dict["type"] == "send_email"
    assert job_dict["status"] == "pending"
    assert job_dict["payload"] == {"email": "test@example.com"}
    assert job_dict["priority"] == 5
    assert job_dict["attempts"] == 0
    assert job_dict["max_attempts"] == 5
    assert job_dict["delay_tolerance"] == 300.0
    assert job_dict["dedupe_key"] == "test-dedupe"
    assert "run_at" in job_dict
    assert "deadline_at" in job_dict
    assert "created_at" in job_dict
    assert "updated_at" in job_dict


def test_job_with_optional_fields():
    """Test Job with optional fields set."""
    job_id = uuid4()
    now = datetime.utcnow()
    run_at = now
    delay_tolerance = timedelta(seconds=300)
    deadline_at = run_at + delay_tolerance
    lease_expires_at = now + timedelta(minutes=10)

    job = Job(
        id=job_id,
        tenant_id="tenant1",
        use_case="notifications",
        type="send_email",
        queue="queue-url",
        status=JobStatus.running,
        payload={"email": "test@example.com"},
        run_at=run_at,
        delay_tolerance=delay_tolerance,
        deadline_at=deadline_at,
        priority=0,
        attempts=1,
        max_attempts=5,
        backoff_policy={"type": "exponential", "base_seconds": 10},
        lease_expires_at=lease_expires_at,
        last_error={"error": "Test error", "type": "TestException"},
        dedupe_key="dedupe123",
        enqueue_failed=False,
    )

    assert job.lease_expires_at == lease_expires_at
    assert job.last_error == {"error": "Test error", "type": "TestException"}
    assert job.dedupe_key == "dedupe123"
    assert job.enqueue_failed is False

    job_dict = job.to_dict()
    assert job_dict["lease_expires_at"] is not None
    assert job_dict["last_error"] == {"error": "Test error", "type": "TestException"}
