"""Data models for async jobs."""

from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID


class JobStatus(Enum):
    """Job status enumeration.

    Represents the lifecycle states of an async job:

    - pending: Job created and waiting to be scheduled
    - running: Job currently being executed by a worker
    - succeeded: Job completed successfully
    - dead: Job failed permanently after exhausting all retries
    - cancelled: Job manually cancelled before completion
    """

    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    dead = "dead"
    cancelled = "cancelled"


class Job:
    """Represents an async job record.

    A Job encapsulates all information needed to execute an asynchronous task,
    including scheduling constraints, retry policies, and execution state.

    Attributes:
        id: Unique job identifier (UUID)
        tenant_id: Tenant that owns this job
        use_case: Use case category (e.g., "notifications", "message_labeling")
        type: Specific job type within the use case
        queue: SQS queue URL for this job
        status: Current job status (pending, running, succeeded, dead, cancelled)
        payload: Job-specific data passed to the handler
        run_at: Earliest time the job should run
        delay_tolerance: How long the job can be delayed beyond run_at
        deadline_at: Latest acceptable execution time (run_at + delay_tolerance)
        priority: Job priority (higher values = higher priority)
        attempts: Number of execution attempts so far
        max_attempts: Maximum retry attempts before marking job as dead
        backoff_policy: Retry backoff configuration dict
        lease_expires_at: When the current execution lease expires (for failure recovery)
        last_error: Error details from the most recent failed attempt
        dedupe_key: Optional deduplication key to prevent duplicate jobs
        enqueue_failed: Whether the job failed to enqueue to SQS
        created_at: When the job was created
        updated_at: When the job was last modified
    """

    def __init__(
        self,
        id: UUID,
        tenant_id: str,
        use_case: str,
        type: str,
        queue: str,
        status: JobStatus,
        payload: dict[str, Any],
        run_at: datetime,
        delay_tolerance: timedelta,
        deadline_at: datetime,
        priority: int,
        attempts: int,
        max_attempts: int,
        backoff_policy: dict[str, Any],
        lease_expires_at: datetime | None = None,
        last_error: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
        enqueue_failed: bool = False,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        """Initialize a Job instance.

        Args:
            id: Unique job identifier
            tenant_id: Tenant identifier
            use_case: Use case name (e.g., "notifications")
            type: Specific job type (e.g., "send_email")
            queue: SQS queue URL
            status: Current job status
            payload: Job data dictionary
            run_at: Earliest execution time
            delay_tolerance: Maximum acceptable delay
            deadline_at: Latest execution time (run_at + delay_tolerance)
            priority: Job priority (higher = more important)
            attempts: Current attempt count
            max_attempts: Maximum retry attempts
            backoff_policy: Retry backoff configuration
            lease_expires_at: Execution lease expiration time
            last_error: Most recent error details
            dedupe_key: Deduplication key
            enqueue_failed: Whether SQS enqueue failed
            created_at: Creation timestamp (defaults to now)
            updated_at: Last update timestamp (defaults to now)
        """
        self.id = id
        self.tenant_id = tenant_id
        self.use_case = use_case
        self.type = type
        self.queue = queue
        self.status = status
        self.payload = payload
        self.run_at = run_at
        self.delay_tolerance = delay_tolerance
        self.deadline_at = deadline_at
        self.priority = priority
        self.attempts = attempts
        self.max_attempts = max_attempts
        self.backoff_policy = backoff_policy
        self.lease_expires_at = lease_expires_at
        self.last_error = last_error
        self.dedupe_key = dedupe_key
        self.enqueue_failed = enqueue_failed
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Convert job to dictionary representation.

        Serializes the job to a JSON-compatible dictionary with ISO format
        timestamps and total_seconds for timedeltas.

        Returns:
            Dictionary containing all job attributes with serialized values

        Example:
            >>> job = Job(...)
            >>> job_dict = job.to_dict()
            >>> print(job_dict["status"])
            "pending"
        """
        return {
            "id": str(self.id),
            "tenant_id": self.tenant_id,
            "use_case": self.use_case,
            "type": self.type,
            "queue": self.queue,
            "status": self.status.value,
            "payload": self.payload,
            "run_at": self.run_at.isoformat(),
            "delay_tolerance": self.delay_tolerance.total_seconds(),
            "deadline_at": self.deadline_at.isoformat(),
            "priority": self.priority,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "backoff_policy": self.backoff_policy,
            "lease_expires_at": (
                self.lease_expires_at.isoformat() if self.lease_expires_at else None
            ),
            "last_error": self.last_error,
            "dedupe_key": self.dedupe_key,
            "enqueue_failed": self.enqueue_failed,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
