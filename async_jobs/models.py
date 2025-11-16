"""Data models for jobs."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID


class JobStatus(str, Enum):
    """Job status values."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    DEAD = "dead"
    CANCELLED = "cancelled"


class Job:
    """Represents a job record."""

    def __init__(
        self,
        id: UUID,
        tenant_id: str,
        use_case: str,
        type: str,
        queue: str,
        status: JobStatus,
        payload: Dict[str, Any],
        run_at: datetime,
        delay_tolerance: str,  # INTERVAL as string from DB
        deadline_at: datetime,
        priority: int,
        attempts: int,
        max_attempts: int,
        backoff_policy: Dict[str, Any],
        lease_expires_at: Optional[datetime] = None,
        last_error: Optional[Dict[str, Any]] = None,
        dedupe_key: Optional[str] = None,
        enqueue_failed: bool = False,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id
        self.tenant_id = tenant_id
        self.use_case = use_case
        self.type = type
        self.queue = queue
        self.status = JobStatus(status) if isinstance(status, str) else status
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
        self.created_at = created_at
        self.updated_at = updated_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "tenant_id": self.tenant_id,
            "use_case": self.use_case,
            "type": self.type,
            "queue": self.queue,
            "status": self.status.value,
            "payload": self.payload,
            "run_at": self.run_at.isoformat() if self.run_at else None,
            "delay_tolerance": self.delay_tolerance,
            "deadline_at": self.deadline_at.isoformat() if self.deadline_at else None,
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
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
