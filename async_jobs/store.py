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

    async def lease_pending_jobs_atomically(
        self, use_case: str, limit: int, now: datetime, lease_expires_at: datetime
    ) -> list[Job]:
        """
        Atomically lease pending jobs for scheduling.
        
        Uses FOR UPDATE SKIP LOCKED to ensure only one scheduler can lease each job.
        Returns jobs that were successfully leased.
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                UPDATE jobs
                SET status = $1, lease_expires_at = $2, updated_at = now()
                WHERE id IN (
                    SELECT id FROM jobs
                    WHERE use_case = $3
                      AND status = $4
                      AND run_at <= $5
                    ORDER BY deadline_at ASC
                    LIMIT $6
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING *
                """,
                JobStatus.running.value,
                lease_expires_at,
                use_case,
                JobStatus.pending.value,
                now,
                limit,
            )

        return [self._row_to_job(row) for row in rows]

    async def select_pending_jobs_for_scheduling(
        self, use_case: str, limit: int, now: datetime
    ) -> list[Job]:
        """
        DEPRECATED: Use lease_pending_jobs_atomically instead.
        
        Select pending jobs for scheduling, ordered by deadline.
        """
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
        """
        DEPRECATED: Use lease_pending_jobs_atomically instead.
        
        Mark jobs as running and set lease expiration.
        """
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

    async def revert_expired_leases(self, now: datetime, max_attempts: int = 5) -> int:
        """
        Revert jobs with expired leases back to pending or mark as dead.
        
        Returns the number of jobs reverted.
        """
        async with self.db_pool.acquire() as conn:
            # Revert to pending if attempts < max_attempts
            result = await conn.execute(
                """
                UPDATE jobs
                SET status = $1,
                    lease_expires_at = NULL,
                    last_error = jsonb_build_object(
                        'error', 'Lease expired - worker may have crashed',
                        'timestamp', $3
                    ),
                    updated_at = now()
                WHERE status = $2
                  AND lease_expires_at < $4
                  AND attempts < max_attempts
                """,
                JobStatus.pending.value,
                JobStatus.running.value,
                now.isoformat(),
                now,
            )
            
            # Extract count from result string like "UPDATE 5"
            reverted_count = int(result.split()[-1]) if result else 0
            
            # Mark as dead if attempts >= max_attempts
            dead_result = await conn.execute(
                """
                UPDATE jobs
                SET status = $1,
                    lease_expires_at = NULL,
                    last_error = jsonb_build_object(
                        'error', 'Lease expired after max attempts',
                        'timestamp', $3
                    ),
                    updated_at = now()
                WHERE status = $2
                  AND lease_expires_at < $4
                  AND attempts >= max_attempts
                """,
                JobStatus.dead.value,
                JobStatus.running.value,
                now.isoformat(),
                now,
            )
            
            dead_count = int(dead_result.split()[-1]) if dead_result else 0
            
            return reverted_count + dead_count

    async def mark_job_enqueue_failed(self, job_id: UUID, error: dict[str, Any]) -> None:
        """Mark a job as having failed to enqueue to SQS."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE jobs
                SET enqueue_failed = true,
                    status = $1,
                    lease_expires_at = NULL,
                    last_error = $2,
                    updated_at = now()
                WHERE id = $3
                """,
                JobStatus.pending.value,
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
