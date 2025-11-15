"""Data models for async jobs."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import UUID


class JobStatus(str, Enum):
    """Job status enum."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    DEAD = "dead"
    CANCELLED = "cancelled"


@dataclass
class Job:
    """Full job record."""

    id: UUID
    tenant_id: str
    use_case: str
    type: str
    queue: str
    status: JobStatus
    payload: dict[str, Any]
    run_at: datetime
    delay_tolerance: timedelta
    deadline_at: datetime
    priority: int
    attempts: int
    max_attempts: int
    backoff_policy: dict[str, Any]
    lease_expires_at: Optional[datetime]
    last_error: Optional[dict[str, Any]]
    dedupe_key: Optional[str]
    enqueue_failed: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class EnqueueJobRequest:
    """Request to enqueue a new job."""

    tenant_id: str
    use_case: str
    type: str
    queue: str
    payload: dict[str, Any]
    delay_tolerance_seconds: int
    max_attempts: int
    backoff_policy: dict[str, Any]
    run_at: Optional[datetime] = None
    dedupe_key: Optional[str] = None
    priority: int = 0


@dataclass
class JobContext:
    """Context passed to job handlers."""

    job_id: UUID
    tenant_id: str
    use_case: str
    type: str
    attempt: int
