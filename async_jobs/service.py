"""Job service business logic."""

import uuid
from datetime import datetime, timedelta
from typing import Optional

from async_jobs.config import AsyncJobsConfig
from async_jobs.errors import QuotaExceededError
from async_jobs.models import EnqueueJobRequest, Job, JobStatus
from async_jobs.store import JobStore


class JobService:
    """High-level job service operations."""

    def __init__(self, config: AsyncJobsConfig, store: JobStore):
        """Initialize the job service."""
        self.config = config
        self.store = store

    async def enqueue(self, request: EnqueueJobRequest) -> uuid.UUID:
        """Enqueue a new job."""
        # Check tenant quota
        if request.tenant_id in self.config.per_tenant_quotas:
            quota = self.config.per_tenant_quotas[request.tenant_id]
            pending_count = await self.store.count_pending_jobs_for_tenant(request.tenant_id)
            if pending_count >= quota.max_pending_jobs:
                raise QuotaExceededError(
                    f"Tenant {request.tenant_id} has exceeded quota "
                    f"of {quota.max_pending_jobs} pending jobs"
                )

        # Get use case config for defaults
        use_case_config = self.config.use_case_configs.get(request.use_case)

        # Apply default delay tolerance if needed
        delay_tolerance_seconds = request.delay_tolerance_seconds
        if delay_tolerance_seconds == 0 and use_case_config:
            delay_tolerance_seconds = use_case_config.default_delay_tolerance_seconds

        delay_tolerance = timedelta(seconds=delay_tolerance_seconds)

        # Calculate run_at and deadline_at
        run_at = request.run_at or datetime.utcnow()
        deadline_at = run_at + delay_tolerance

        # Generate job ID
        job_id = uuid.uuid4()

        # Insert job
        await self.store.insert_job(
            job_id=job_id,
            tenant_id=request.tenant_id,
            use_case=request.use_case,
            type=request.type,
            queue=request.queue,
            payload=request.payload,
            run_at=run_at,
            delay_tolerance=delay_tolerance,
            deadline_at=deadline_at,
            priority=request.priority,
            max_attempts=request.max_attempts,
            backoff_policy=request.backoff_policy,
            dedupe_key=request.dedupe_key,
        )

        return job_id

    async def get_job(self, job_id: uuid.UUID) -> Job:
        """Get a job by ID."""
        return await self.store.get_job(job_id)

    async def list_jobs(
        self,
        tenant_id: Optional[str] = None,
        use_case: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: int = 100,
    ) -> list[Job]:
        """List jobs with optional filters."""
        return await self.store.list_jobs(
            tenant_id=tenant_id, use_case=use_case, status=status, limit=limit
        )

    async def lease_jobs_for_use_case(
        self, use_case: str, max_jobs: int, lease_duration: timedelta
    ) -> list[Job]:
        """Lease jobs for a use case for scheduling."""
        now = datetime.utcnow()

        # Select pending jobs
        jobs = await self.store.select_pending_jobs_for_scheduling(
            use_case=use_case, limit=max_jobs, now=now
        )

        if not jobs:
            return []

        # Mark as running and set lease
        lease_expires_at = now + lease_duration
        job_ids = [job.id for job in jobs]
        leased_jobs = await self.store.mark_jobs_as_running_and_lease(
            job_ids=job_ids, lease_expires_at=lease_expires_at
        )

        return leased_jobs

    async def mark_job_succeeded(self, job_id: uuid.UUID) -> Job:
        """Mark a job as succeeded."""
        return await self.store.update_job_success(job_id)

    async def mark_job_retry(
        self,
        job_id: uuid.UUID,
        error: dict,
        backoff_seconds: int,
    ) -> Job:
        """Mark a job for retry with backoff."""
        job = await self.store.get_job(job_id)
        attempts = job.attempts + 1
        run_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)

        return await self.store.update_job_retry(
            job_id=job_id,
            attempts=attempts,
            last_error=error,
            run_at=run_at,
        )

    async def mark_job_dead(self, job_id: uuid.UUID, error: dict) -> Job:
        """Mark a job as dead (max retries exceeded)."""
        job = await self.store.get_job(job_id)
        attempts = job.attempts + 1

        return await self.store.update_job_dead(
            job_id=job_id,
            attempts=attempts,
            last_error=error,
        )
