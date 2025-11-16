"""Database store layer for jobs."""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from async_jobs.models import Job, JobStatus


class JobStore:
    """Internal DB layer for job operations."""

    def __init__(self, db_pool):
        """
        Initialize JobStore.

        Args:
            db_pool: Database connection pool (e.g., asyncpg Pool)
        """
        self.db_pool = db_pool

    async def insert_job(
        self,
        *,
        tenant_id: str,
        use_case: str,
        type: str,
        queue: str,
        payload: Dict[str, Any],
        run_at: datetime,
        delay_tolerance: timedelta,
        deadline_at: datetime,
        priority: int = 0,
        max_attempts: int = 5,
        backoff_policy: Dict[str, Any],
        dedupe_key: Optional[str] = None,
        job_id: Optional[UUID] = None,
    ) -> UUID:
        """
        Insert a new job.

        Returns:
            The job ID (UUID).
        """
        if job_id is None:
            job_id = uuid4()

        async with self.db_pool.acquire() as conn:
            # Check for dedupe_key if provided
            if dedupe_key:
                existing = await conn.fetchrow(
                    """
                    SELECT id FROM jobs
                    WHERE dedupe_key = $1 AND status IN ('pending', 'running')
                    """,
                    dedupe_key,
                )
                if existing:
                    return existing["id"]

            await conn.execute(
                """
                INSERT INTO jobs (
                    id, tenant_id, use_case, type, queue,
                    status, payload,
                    run_at, delay_tolerance, deadline_at,
                    priority, attempts, max_attempts, backoff_policy,
                    dedupe_key
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7,
                    $8, $9, $10,
                    $11, $12, $13, $14,
                    $15
                )
                """,
                job_id,
                tenant_id,
                use_case,
                type,
                queue,
                JobStatus.PENDING.value,
                json.dumps(payload),
                run_at,
                delay_tolerance,
                deadline_at,
                priority,
                0,  # attempts
                max_attempts,
                json.dumps(backoff_policy),
                dedupe_key,
            )

        return job_id

    async def get_job(self, job_id: UUID) -> Optional[Job]:
        """Get a job by ID."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    id, tenant_id, use_case, type, queue,
                    status, payload,
                    run_at, delay_tolerance, deadline_at,
                    priority, attempts, max_attempts, backoff_policy,
                    lease_expires_at, last_error, dedupe_key,
                    enqueue_failed, created_at, updated_at
                FROM jobs
                WHERE id = $1
                """,
                job_id,
            )

            if not row:
                return None

            return self._row_to_job(row)

    async def list_jobs(
        self,
        *,
        tenant_id: Optional[str] = None,
        use_case: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Job]:
        """List jobs with optional filters."""
        conditions = []
        params = []
        param_idx = 1

        if tenant_id:
            conditions.append(f"tenant_id = ${param_idx}")
            params.append(tenant_id)
            param_idx += 1

        if use_case:
            conditions.append(f"use_case = ${param_idx}")
            params.append(use_case)
            param_idx += 1

        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status)
            param_idx += 1

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        params.append(limit)
        limit_clause = f"LIMIT ${param_idx}"

        query = f"""
            SELECT
                id, tenant_id, use_case, type, queue,
                status, payload,
                run_at, delay_tolerance, deadline_at,
                priority, attempts, max_attempts, backoff_policy,
                lease_expires_at, last_error, dedupe_key,
                enqueue_failed, created_at, updated_at
            FROM jobs
            {where_clause}
            ORDER BY created_at DESC
            {limit_clause}
        """

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [self._row_to_job(row) for row in rows]

    async def count_pending_jobs_for_tenant(
        self, tenant_id: str, use_case: str
    ) -> int:
        """Count pending jobs for a tenant and use case."""
        async with self.db_pool.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM jobs
                WHERE tenant_id = $1 AND use_case = $2 AND status = 'pending'
                """,
                tenant_id,
                use_case,
            )
            return count or 0

    async def select_pending_jobs_for_scheduling(
        self,
        *,
        use_case: str,
        max_concurrent: int,
        current_running_count: int,
        limit: int,
    ) -> List[Job]:
        """
        Select pending jobs for scheduling, ordered by deadline_at.

        Only selects jobs where run_at <= now() and respects max_concurrent.
        """
        available_slots = max(0, max_concurrent - current_running_count)
        if available_slots <= 0:
            return []

        actual_limit = min(limit, available_slots)

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id, tenant_id, use_case, type, queue,
                    status, payload,
                    run_at, delay_tolerance, deadline_at,
                    priority, attempts, max_attempts, backoff_policy,
                    lease_expires_at, last_error, dedupe_key,
                    enqueue_failed, created_at, updated_at
                FROM jobs
                WHERE use_case = $1
                  AND status = 'pending'
                  AND run_at <= now()
                ORDER BY deadline_at ASC
                LIMIT $2
                """,
                use_case,
                actual_limit,
            )
            return [self._row_to_job(row) for row in rows]

    async def count_running_jobs_for_use_case(self, use_case: str) -> int:
        """Count running jobs for a use case."""
        async with self.db_pool.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM jobs
                WHERE use_case = $1 AND status = 'running'
                """,
                use_case,
            )
            return count or 0

    async def mark_jobs_as_running_and_lease(
        self, job_ids: List[UUID], lease_duration_seconds: int = 300
    ) -> int:
        """
        Mark jobs as running and set lease_expires_at.

        Returns:
            Number of jobs updated.
        """
        if not job_ids:
            return 0

        lease_expires_at = datetime.utcnow() + timedelta(
            seconds=lease_duration_seconds
        )

        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE jobs
                SET status = 'running',
                    lease_expires_at = $1,
                    updated_at = now()
                WHERE id = ANY($2::uuid[])
                  AND status = 'pending'
                """,
                lease_expires_at,
                job_ids,
            )
            # Extract number from result like "UPDATE 5"
            return int(result.split()[-1]) if result else 0

    async def update_job_success(self, job_id: UUID) -> None:
        """Mark a job as succeeded."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs
                SET status = 'succeeded',
                    updated_at = now()
                WHERE id = $1
                """,
                job_id,
            )

    async def update_job_retry(
        self,
        job_id: UUID,
        *,
        next_run_at: datetime,
        next_deadline_at: datetime,
        attempts: int,
        last_error: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update job for retry."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs
                SET status = 'pending',
                    run_at = $1,
                    deadline_at = $2,
                    attempts = $3,
                    last_error = $4,
                    lease_expires_at = NULL,
                    updated_at = now()
                WHERE id = $5
                """,
                next_run_at,
                next_deadline_at,
                attempts,
                json.dumps(last_error) if last_error else None,
                job_id,
            )

    async def update_job_dead(
        self, job_id: UUID, last_error: Optional[Dict[str, Any]] = None
    ) -> None:
        """Mark a job as dead."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs
                SET status = 'dead',
                    last_error = $1,
                    updated_at = now()
                WHERE id = $2
                """,
                json.dumps(last_error) if last_error else None,
                job_id,
            )

    def _row_to_job(self, row) -> Job:
        """Convert a database row to a Job model."""
        return Job(
            id=row["id"],
            tenant_id=row["tenant_id"],
            use_case=row["use_case"],
            type=row["type"],
            queue=row["queue"],
            status=row["status"],
            payload=json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"],
            run_at=row["run_at"],
            delay_tolerance=str(row["delay_tolerance"]),
            deadline_at=row["deadline_at"],
            priority=row["priority"],
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            backoff_policy=(
                json.loads(row["backoff_policy"])
                if isinstance(row["backoff_policy"], str)
                else row["backoff_policy"]
            ),
            lease_expires_at=row["lease_expires_at"],
            last_error=(
                json.loads(row["last_error"])
                if row["last_error"] and isinstance(row["last_error"], str)
                else row["last_error"]
            ),
            dedupe_key=row["dedupe_key"],
            enqueue_failed=row["enqueue_failed"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
