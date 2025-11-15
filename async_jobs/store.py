"""Database store for async jobs."""
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from async_jobs.errors import JobNotFoundError
from async_jobs.models import Job, JobStatus


class JobStore:
    """Database store for job operations."""

    def __init__(self, pool: psycopg.AsyncConnectionPool):
        """Initialize the job store."""
        self.pool = pool

    async def insert_job(
        self,
        job_id: UUID,
        tenant_id: str,
        use_case: str,
        type: str,
        queue: str,
        payload: Dict[str, Any],
        run_at: datetime,
        delay_tolerance: timedelta,
        deadline_at: datetime,
        priority: int,
        max_attempts: int,
        backoff_policy: Dict[str, Any],
        dedupe_key: Optional[str] = None,
    ) -> Job:
        """Insert a new job into the database."""
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    INSERT INTO jobs (
                        id, tenant_id, use_case, type, queue, status, payload,
                        run_at, delay_tolerance, deadline_at, priority, attempts,
                        max_attempts, backoff_policy, dedupe_key
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING *
                    """,
                    (
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
                        0,
                        max_attempts,
                        json.dumps(backoff_policy),
                        dedupe_key,
                    ),
                )
                row = await cur.fetchone()
                return self._row_to_job(row)

    async def get_job(self, job_id: UUID) -> Job:
        """Get a job by ID."""
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    "SELECT * FROM jobs WHERE id = %s",
                    (job_id,),
                )
                row = await cur.fetchone()
                if not row:
                    raise JobNotFoundError(f"Job {job_id} not found")
                return self._row_to_job(row)

    async def list_jobs(
        self,
        tenant_id: Optional[str] = None,
        use_case: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: int = 100,
    ) -> List[Job]:
        """List jobs with optional filters."""
        query = "SELECT * FROM jobs WHERE 1=1"
        params: List[Any] = []

        if tenant_id:
            params.append(tenant_id)
            query += f" AND tenant_id = ${len(params)}"

        if use_case:
            params.append(use_case)
            query += f" AND use_case = ${len(params)}"

        if status:
            params.append(status.value)
            query += f" AND status = ${len(params)}"

        query += f" ORDER BY created_at DESC LIMIT {limit}"

        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()
                return [self._row_to_job(row) for row in rows]

    async def count_pending_jobs_for_tenant(self, tenant_id: str) -> int:
        """Count pending jobs for a tenant."""
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT COUNT(*) FROM jobs WHERE tenant_id = %s AND status = %s",
                    (tenant_id, JobStatus.PENDING.value),
                )
                result = await cur.fetchone()
                return result[0] if result else 0

    async def select_pending_jobs_for_scheduling(
        self, use_case: str, limit: int, now: datetime
    ) -> List[Job]:
        """Select pending jobs ready for scheduling."""
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    SELECT * FROM jobs
                    WHERE use_case = %s
                      AND status = %s
                      AND run_at <= %s
                      AND (lease_expires_at IS NULL OR lease_expires_at < %s)
                    ORDER BY deadline_at ASC
                    LIMIT %s
                    """,
                    (use_case, JobStatus.PENDING.value, now, now, limit),
                )
                rows = await cur.fetchall()
                return [self._row_to_job(row) for row in rows]

    async def mark_jobs_as_running_and_lease(
        self, job_ids: List[UUID], lease_expires_at: datetime
    ) -> List[Job]:
        """Mark jobs as running and set lease expiration."""
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    UPDATE jobs
                    SET status = %s,
                        lease_expires_at = %s,
                        updated_at = now()
                    WHERE id = ANY(%s)
                    RETURNING *
                    """,
                    (JobStatus.RUNNING.value, lease_expires_at, job_ids),
                )
                rows = await cur.fetchall()
                return [self._row_to_job(row) for row in rows]

    async def update_job_success(self, job_id: UUID) -> Job:
        """Mark a job as succeeded."""
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    UPDATE jobs
                    SET status = %s,
                        lease_expires_at = NULL,
                        updated_at = now()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (JobStatus.SUCCEEDED.value, job_id),
                )
                row = await cur.fetchone()
                if not row:
                    raise JobNotFoundError(f"Job {job_id} not found")
                return self._row_to_job(row)

    async def update_job_retry(
        self,
        job_id: UUID,
        attempts: int,
        last_error: Dict[str, Any],
        run_at: datetime,
    ) -> Job:
        """Update a job for retry."""
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    UPDATE jobs
                    SET status = %s,
                        attempts = %s,
                        last_error = %s,
                        run_at = %s,
                        lease_expires_at = NULL,
                        updated_at = now()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (
                        JobStatus.PENDING.value,
                        attempts,
                        json.dumps(last_error),
                        run_at,
                        job_id,
                    ),
                )
                row = await cur.fetchone()
                if not row:
                    raise JobNotFoundError(f"Job {job_id} not found")
                return self._row_to_job(row)

    async def update_job_dead(
        self, job_id: UUID, attempts: int, last_error: Dict[str, Any]
    ) -> Job:
        """Mark a job as dead."""
        async with self.pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(
                    """
                    UPDATE jobs
                    SET status = %s,
                        attempts = %s,
                        last_error = %s,
                        lease_expires_at = NULL,
                        updated_at = now()
                    WHERE id = %s
                    RETURNING *
                    """,
                    (JobStatus.DEAD.value, attempts, json.dumps(last_error), job_id),
                )
                row = await cur.fetchone()
                if not row:
                    raise JobNotFoundError(f"Job {job_id} not found")
                return self._row_to_job(row)

    def _row_to_job(self, row: Dict[str, Any]) -> Job:
        """Convert a database row to a Job object."""
        return Job(
            id=row["id"],
            tenant_id=row["tenant_id"],
            use_case=row["use_case"],
            type=row["type"],
            queue=row["queue"],
            status=JobStatus(row["status"]),
            payload=row["payload"] if isinstance(row["payload"], dict) else json.loads(row["payload"]),
            run_at=row["run_at"],
            delay_tolerance=row["delay_tolerance"],
            deadline_at=row["deadline_at"],
            priority=row["priority"],
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
            backoff_policy=row["backoff_policy"] if isinstance(row["backoff_policy"], dict) else json.loads(row["backoff_policy"]),
            lease_expires_at=row["lease_expires_at"],
            last_error=row["last_error"] if row["last_error"] is None or isinstance(row["last_error"], dict) else json.loads(row["last_error"]),
            dedupe_key=row["dedupe_key"],
            enqueue_failed=row["enqueue_failed"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
