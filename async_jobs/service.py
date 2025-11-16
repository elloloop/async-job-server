"""High-level service layer for job operations."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from async_jobs.config import AsyncJobsConfig
from async_jobs.errors import JobNotFoundError, QuotaExceededError
from async_jobs.models import Job
from async_jobs.store import JobStore


class JobService:
    """High-level API for job operations."""

    def __init__(
        self, config: AsyncJobsConfig, db_pool, logger: Optional[logging.Logger] = None
    ):
        """
        Initialize JobService.

        Args:
            config: AsyncJobsConfig instance
            db_pool: Database connection pool
            logger: Optional logger instance
        """
        self.config = config
        self.db_pool = db_pool
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
    ) -> UUID:
        """
        Enqueue a new job.

        Args:
            tenant_id: Tenant identifier
            use_case: Use case identifier (e.g., "notifications")
            type: Job type (handler name)
            queue: Queue name
            payload: Job payload (JSON-serializable dict)
            run_at: When to run the job (defaults to now)
            delay_tolerance: Maximum delay tolerance (defaults to use_case default)
            max_attempts: Maximum retry attempts
            backoff_policy: Backoff policy dict
            dedupe_key: Optional deduplication key

        Returns:
            Job ID (UUID)

        Raises:
            QuotaExceededError: If tenant quota is exceeded
        """
        # Validate required fields
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not use_case:
            raise ValueError("use_case is required")
        if not type:
            raise ValueError("type is required")
        if not queue:
            raise ValueError("queue is required")

        # Check quota
        quota = self.config.get_quota_for_tenant_use_case(tenant_id, use_case)
        if quota is not None:
            current_pending = await self.store.count_pending_jobs_for_tenant(
                tenant_id, use_case
            )
            if current_pending >= quota:
                raise QuotaExceededError(
                    tenant_id,
                    use_case,
                    f"Quota exceeded: {current_pending}/{quota} pending jobs",
                )

        # Apply defaults
        if run_at is None:
            run_at = datetime.utcnow()

        if delay_tolerance is None:
            delay_tolerance_seconds = (
                self.config.get_default_delay_tolerance_seconds_for_use_case(use_case)
            )
            delay_tolerance = timedelta(seconds=delay_tolerance_seconds)

        if backoff_policy is None:
            backoff_policy = {
                "type": "exponential",
                "base_seconds": 10,
            }

        # Calculate deadline_at
        deadline_at = run_at + delay_tolerance

        # Insert job
        job_id = await self.store.insert_job(
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
            dedupe_key=dedupe_key,
        )

        self.logger.info(
            f"Enqueued job {job_id} for tenant {tenant_id}, use_case {use_case}, type {type}"
        )

        return job_id

    async def get_job(self, job_id: UUID) -> Job:
        """
        Get a job by ID.

        Raises:
            JobNotFoundError: If job is not found
        """
        job = await self.store.get_job(job_id)
        if job is None:
            raise JobNotFoundError(str(job_id))
        return job

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
            tenant_id=tenant_id,
            use_case=use_case,
            status=status,
            limit=limit,
        )

    async def lease_jobs_for_use_case(
        self,
        use_case: str,
        max_concurrent: int,
        limit: int = 100,
        lease_duration_seconds: int = 300,
    ) -> List[Job]:
        """
        Lease jobs for a use case (used by scheduler).

        Returns:
            List of leased job IDs
        """
        # Count current running jobs
        current_running = await self.store.count_running_jobs_for_use_case(use_case)

        # Select pending jobs
        pending_jobs = await self.store.select_pending_jobs_for_scheduling(
            use_case=use_case,
            max_concurrent=max_concurrent,
            current_running_count=current_running,
            limit=limit,
        )

        if not pending_jobs:
            return []

        # Mark as running and lease
        job_ids = [job.id for job in pending_jobs]
        updated_count = await self.store.mark_jobs_as_running_and_lease(
            job_ids, lease_duration_seconds=lease_duration_seconds
        )

        # Return only the jobs that were successfully leased
        if updated_count < len(job_ids):
            # Some jobs may have been leased by another scheduler instance
            # Re-fetch to get only the ones we successfully leased
            leased_jobs = []
            for job_id in job_ids[:updated_count]:
                job = await self.store.get_job(job_id)
                if job and job.status.value == "running":
                    leased_jobs.append(job)
            return leased_jobs

        return pending_jobs

    async def mark_job_succeeded(self, job_id: UUID) -> None:
        """Mark a job as succeeded."""
        await self.store.update_job_success(job_id)
        self.logger.info(f"Job {job_id} marked as succeeded")

    async def mark_job_retry(
        self,
        job_id: UUID,
        *,
        error: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Mark a job for retry with backoff.

        Calculates next run_at and deadline_at based on backoff policy.
        """
        job = await self.store.get_job(job_id)
        if not job:
            raise JobNotFoundError(str(job_id))

        if job.attempts >= job.max_attempts:
            await self.mark_job_dead(job_id, error)
            return

        # Calculate backoff
        backoff_seconds = self._calculate_backoff(
            job.attempts + 1, job.backoff_policy
        )
        next_run_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)

        # Recalculate delay_tolerance (use same as original)
        delay_tolerance_seconds = self._parse_interval_seconds(job.delay_tolerance)
        next_deadline_at = next_run_at + timedelta(seconds=delay_tolerance_seconds)

        await self.store.update_job_retry(
            job_id=job_id,
            next_run_at=next_run_at,
            next_deadline_at=next_deadline_at,
            attempts=job.attempts + 1,
            last_error=error,
        )

        self.logger.info(
            f"Job {job_id} scheduled for retry (attempt {job.attempts + 1}/{job.max_attempts})"
        )

    async def mark_job_dead(
        self, job_id: UUID, error: Optional[Dict[str, Any]] = None
    ) -> None:
        """Mark a job as dead (permanently failed)."""
        await self.store.update_job_dead(job_id, error)
        self.logger.warning(f"Job {job_id} marked as dead")

    def _calculate_backoff(
        self, attempt: int, backoff_policy: Dict[str, Any]
    ) -> int:
        """Calculate backoff delay in seconds."""
        policy_type = backoff_policy.get("type", "exponential")
        base_seconds = backoff_policy.get("base_seconds", 10)

        if policy_type == "exponential":
            return base_seconds * (2 ** (attempt - 1))
        elif policy_type == "linear":
            return base_seconds * attempt
        elif policy_type == "fixed":
            return base_seconds
        else:
            # Default to exponential
            return base_seconds * (2 ** (attempt - 1))

    def _parse_interval_seconds(self, interval_str: str) -> int:
        """
        Parse PostgreSQL INTERVAL string to seconds.

        Simple implementation - assumes format like "3 seconds" or "00:00:03".
        """
        # Try to parse common formats
        if "second" in interval_str.lower():
            # Extract number
            import re

            match = re.search(r"(\d+)", interval_str)
            if match:
                return int(match.group(1))
        # Fallback: try parsing as HH:MM:SS
        try:
            parts = interval_str.split(":")
            if len(parts) == 3:
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
        except (ValueError, AttributeError):
            pass

        # Default fallback
        return 3
