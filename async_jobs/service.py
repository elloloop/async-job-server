"""High-level service layer for job operations."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import asyncpg

from async_jobs.config import AsyncJobsConfig
from async_jobs.errors import QuotaExceededError
from async_jobs.models import Job
from async_jobs.store import JobStore


class JobService:
    """High-level API for job operations."""

    def __init__(
        self, config: AsyncJobsConfig, db_pool: asyncpg.Pool, logger: Optional[logging.Logger] = None
    ):
        self.config = config
        self.store = JobStore(db_pool)
        self.logger = logger or logging.getLogger(__name__)

    async def enqueue(
        self,
        *,
        tenant_id: str,
        use_case: str,
        type: str,
        queue: str,
        payload: Dict[str, Any],
        run_at: Optional[datetime] = None,
        delay_tolerance: Optional[timedelta] = None,
        max_attempts: int = 5,
        backoff_policy: Optional[Dict[str, Any]] = None,
        dedupe_key: Optional[str] = None,
        priority: int = 0,
    ) -> UUID:
        """
        Enqueue a new job.

        Args:
            tenant_id: Tenant identifier
            use_case: Use case name (e.g., "notifications", "message_labeling")
            type: Job type (e.g., "send_notification")
            queue: SQS queue name
            payload: Job payload as dictionary
            run_at: When to run the job (defaults to now)
            delay_tolerance: How long the job can be delayed (uses default if not provided)
            max_attempts: Maximum retry attempts
            backoff_policy: Retry backoff policy
            dedupe_key: Optional deduplication key
            priority: Job priority (higher = more important)

        Returns:
            UUID: The created job ID

        Raises:
            QuotaExceededError: If tenant quota is exceeded
        """
        # Apply defaults
        if run_at is None:
            run_at = datetime.utcnow()

        # Get use case config for defaults
        use_case_config = self.config.get_use_case_config(use_case)
        if use_case_config and delay_tolerance is None:
            default_delay_seconds = use_case_config.get("default_delay_tolerance_seconds", 300)
            delay_tolerance = timedelta(seconds=default_delay_seconds)
        elif delay_tolerance is None:
            delay_tolerance = timedelta(seconds=300)

        # Calculate deadline
        deadline_at = run_at + delay_tolerance

        # Default backoff policy
        if backoff_policy is None:
            backoff_policy = {"type": "exponential", "base_seconds": 10}

        # Check quota
        await self._check_quota(tenant_id, use_case)

        # Create job
        job_id = uuid4()
        await self.store.insert_job(
            id=job_id,
            tenant_id=tenant_id,
            use_case=use_case,
            type=type,
            queue=queue,
            payload=payload,
            run_at=run_at,
            delay_tolerance=delay_tolerance,
            deadline_at=deadline_at,
            max_attempts=max_attempts,
            backoff_policy=backoff_policy,
            priority=priority,
            dedupe_key=dedupe_key,
        )

        self.logger.info(f"Enqueued job {job_id} for tenant {tenant_id}, use_case {use_case}")
        return job_id

    async def get_job(self, job_id: UUID) -> Job:
        """Get a job by ID."""
        return await self.store.get_job(job_id)

    async def list_jobs(
        self,
        *,
        tenant_id: Optional[str] = None,
        use_case: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Job]:
        """List jobs with optional filters."""
        return await self.store.list_jobs(
            tenant_id=tenant_id, use_case=use_case, status=status, limit=limit
        )

    async def lease_jobs_for_use_case(
        self, use_case: str, max_count: int, lease_duration: timedelta
    ) -> List[Job]:
        """
        Lease jobs for a use case.

        Returns jobs that are ready to run, marks them as running,
        and sets lease expiration.
        """
        now = datetime.utcnow()

        # Get current running count
        running_count = await self.store.count_running_jobs_for_use_case(use_case)

        # Calculate how many more we can lease
        available_slots = max_count - running_count
        if available_slots <= 0:
            return []

        # Select pending jobs
        jobs = await self.store.select_pending_jobs_for_scheduling(use_case, available_slots, now)

        if not jobs:
            return []

        # Mark as running and lease
        job_ids = [job.id for job in jobs]
        lease_expires_at = now + lease_duration
        await self.store.mark_jobs_as_running_and_lease(job_ids, lease_expires_at)

        # Reload jobs to get updated state
        leased_jobs = []
        for job_id in job_ids:
            job = await self.store.get_job(job_id)
            leased_jobs.append(job)

        return leased_jobs

    async def mark_job_succeeded(self, job_id: UUID) -> None:
        """Mark a job as succeeded."""
        await self.store.update_job_success(job_id)
        self.logger.info(f"Job {job_id} succeeded")

    async def mark_job_retry(
        self, job_id: UUID, error: Dict[str, Any], backoff_seconds: int
    ) -> None:
        """Mark a job for retry with backoff."""
        next_run_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)
        await self.store.update_job_retry(job_id, error, next_run_at)
        self.logger.info(f"Job {job_id} scheduled for retry at {next_run_at}")

    async def mark_job_dead(self, job_id: UUID, error: Dict[str, Any]) -> None:
        """Mark a job as permanently failed."""
        await self.store.update_job_dead(job_id, error)
        self.logger.error(f"Job {job_id} marked as dead")

    async def _check_quota(self, tenant_id: str, use_case: str) -> None:
        """Check if tenant has exceeded quota for use case."""
        quota = self.config.get_tenant_quota(tenant_id, use_case)
        if quota is None:
            # No quota configured, allow unlimited
            return

        pending_count = await self.store.count_pending_jobs_for_tenant(tenant_id, use_case)
        if pending_count >= quota:
            raise QuotaExceededError(
                f"Tenant {tenant_id} has exceeded quota for {use_case}: "
                f"{pending_count} >= {quota}"
            )
