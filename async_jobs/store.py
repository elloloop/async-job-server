"""Database store layer for async jobs."""

import json
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

import asyncpg

from async_jobs.errors import JobNotFoundError
from async_jobs.models import Job, JobStatus


class JobStore:
    """Database layer for job operations."""

    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool

    async def insert_job(
        self,
        id: UUID,
        tenant_id: str,
        use_case: str,
        type: str,
        queue: str,
        payload: dict[str, Any],
        run_at: datetime,
        delay_tolerance: timedelta,
        deadline_at: datetime,
        max_attempts: int,
        backoff_policy: dict[str, Any],
        priority: int = 0,
        dedupe_key: Optional[str] = None,
    ) -> Job:
        """Insert a new job into the database."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO jobs (
                    id, tenant_id, use_case, type, queue, status, payload,
                    run_at, delay_tolerance, deadline_at, priority,
                    attempts, max_attempts, backoff_policy, dedupe_key
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                """,
                id,
                tenant_id,
                use_case,
                type,
                queue,
                JobStatus.pending.value,
                json.dumps(payload),
                run_at,
                delay_tolerance,
                deadline_at,
                priority,
                0,
                max_attempts,
                json.dumps(backoff_policy),
                dedupe_key,
            )

        return await self.get_job(id)

    async def get_job(self, job_id: UUID) -> Job:
        """Get a job by ID."""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM jobs WHERE id = $1", job_id)

        if not row:
            raise JobNotFoundError(f"Job {job_id} not found")

        return self._row_to_job(row)

    async def list_jobs(
        self,
        tenant_id: Optional[str] = None,
        use_case: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[Job]:
        """List jobs with optional filters."""
        query = "SELECT * FROM jobs WHERE 1=1"
        params = []
        param_idx = 1

        if tenant_id:
            query += f" AND tenant_id = ${param_idx}"
            params.append(tenant_id)
            param_idx += 1

        if use_case:
            query += f" AND use_case = ${param_idx}"
            params.append(use_case)
            param_idx += 1

        if status:
            query += f" AND status = ${param_idx}"
            params.append(status)
            param_idx += 1

        query += f" ORDER BY created_at DESC LIMIT ${param_idx}"
        params.append(limit)

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [self._row_to_job(row) for row in rows]

    async def count_pending_jobs_for_tenant(self, tenant_id: str, use_case: str) -> int:
        """Count pending jobs for a tenant and use case."""
        async with self.db_pool.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM jobs
                WHERE tenant_id = $1 AND use_case = $2 AND status = $3
                """,
                tenant_id,
                use_case,
                JobStatus.pending.value,
            )
        return count

    async def count_running_jobs_for_use_case(self, use_case: str) -> int:
        """Count running jobs for a use case."""
        async with self.db_pool.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM jobs
                WHERE use_case = $1 AND status = $2
                """,
                use_case,
                JobStatus.running.value,
            )
        return count

    async def select_pending_jobs_for_scheduling(
        self, use_case: str, limit: int, now: datetime
    ) -> list[Job]:
        """Select pending jobs for scheduling, ordered by deadline."""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM jobs
                WHERE use_case = $1
                  AND status = $2
                  AND run_at <= $3
                ORDER BY deadline_at ASC
                LIMIT $4
                """,
                use_case,
                JobStatus.pending.value,
                now,
                limit,
            )

        return [self._row_to_job(row) for row in rows]

    async def mark_jobs_as_running_and_lease(
        self, job_ids: list[UUID], lease_expires_at: datetime
    ) -> None:
        """Mark jobs as running and set lease expiration."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs
                SET status = $1, lease_expires_at = $2, updated_at = now()
                WHERE id = ANY($3::uuid[])
                """,
                JobStatus.running.value,
                lease_expires_at,
                job_ids,
            )

    async def update_job_success(self, job_id: UUID) -> None:
        """Mark a job as succeeded."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs
                SET status = $1, updated_at = now()
                WHERE id = $2
                """,
                JobStatus.succeeded.value,
                job_id,
            )

    async def update_job_retry(
        self, job_id: UUID, error: dict[str, Any], next_run_at: datetime
    ) -> None:
        """Update job for retry with incremented attempts."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs
                SET status = $1,
                    attempts = attempts + 1,
                    last_error = $2,
                    run_at = $3,
                    lease_expires_at = NULL,
                    updated_at = now()
                WHERE id = $4
                """,
                JobStatus.pending.value,
                json.dumps(error),
                next_run_at,
                job_id,
            )

    async def update_job_dead(self, job_id: UUID, error: dict[str, Any]) -> None:
        """Mark a job as dead (permanent failure)."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs
                SET status = $1,
                    attempts = attempts + 1,
                    last_error = $2,
                    updated_at = now()
                WHERE id = $3
                """,
                JobStatus.dead.value,
                json.dumps(error),
                job_id,
            )

    def _row_to_job(self, row: asyncpg.Record) -> Job:
        """Convert a database row to a Job model."""
        return Job(
            id=row["id"],
            tenant_id=row["tenant_id"],
            use_case=row["use_case"],
            type=row["type"],
            queue=row["queue"],
            status=JobStatus(row["status"]),
            payload=json.loads(row["payload"])
            if isinstance(row["payload"], str)
            else row["payload"],
            run_at=row["run_at"],
            delay_tolerance=row["delay_tolerance"],
            deadline_at=row["deadline_at"],
            priority=row["priority"],
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            backoff_policy=json.loads(row["backoff_policy"])
            if isinstance(row["backoff_policy"], str)
            else row["backoff_policy"],
            lease_expires_at=row["lease_expires_at"],
            last_error=json.loads(row["last_error"])
            if row["last_error"] and isinstance(row["last_error"], str)
            else row["last_error"],
            dedupe_key=row["dedupe_key"],
            enqueue_failed=row["enqueue_failed"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
