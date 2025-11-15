"""Postgres storage backend for job persistence."""

import json
from datetime import datetime
from typing import List, Optional, Dict, Any

import asyncpg

from asyncjobserver.job import Job, JobStatus, JobPriority


class PostgresJobStorage:
    """
    PostgreSQL-based job storage and queue implementation.
    
    This class provides persistent storage for jobs using PostgreSQL,
    implementing a reliable job queue with support for scheduling,
    priorities, and status tracking.
    
    Example:
        ```python
        storage = PostgresJobStorage(
            host="localhost",
            port=5432,
            database="jobs",
            user="postgres",
            password="secret"
        )
        
        await storage.connect()
        await storage.initialize()
        
        # Store a job
        await storage.save_job(my_job)
        
        # Fetch pending jobs
        jobs = await storage.fetch_pending_jobs(limit=10)
        ```
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "jobs",
        user: str = "postgres",
        password: str = "",
        pool_min_size: int = 10,
        pool_max_size: int = 20,
    ):
        """
        Initialize PostgreSQL storage.
        
        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Database user
            password: Database password
            pool_min_size: Minimum connection pool size
            pool_max_size: Maximum connection pool size
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self.pool_min_size = pool_min_size
        self.pool_max_size = pool_max_size
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Establish connection pool to the database."""
        self.pool = await asyncpg.create_pool(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
            min_size=self.pool_min_size,
            max_size=self.pool_max_size,
        )

    async def disconnect(self) -> None:
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def initialize(self) -> None:
        """
        Create the jobs table if it doesn't exist.
        
        This sets up the database schema required for job storage.
        """
        if not self.pool:
            raise RuntimeError("Database connection not established. Call connect() first.")

        create_table_sql = """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id VARCHAR(255) PRIMARY KEY,
            job_type VARCHAR(255) NOT NULL,
            priority VARCHAR(50) NOT NULL,
            delay_seconds INTEGER NOT NULL DEFAULT 0,
            max_retries INTEGER NOT NULL DEFAULT 3,
            retry_count INTEGER NOT NULL DEFAULT 0,
            parameters JSONB NOT NULL DEFAULT '{}',
            status VARCHAR(50) NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            scheduled_at TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_message TEXT,
            result JSONB
        );
        
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_scheduled_at ON jobs(scheduled_at);
        CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority);
        CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
        """

        async with self.pool.acquire() as conn:
            await conn.execute(create_table_sql)

    async def save_job(self, job: Job) -> None:
        """
        Save a job to the database.
        
        Args:
            job: The job instance to save
        """
        if not self.pool:
            raise RuntimeError("Database connection not established. Call connect() first.")

        job_data = job.to_dict()
        
        # Calculate scheduled time if not set
        if not job_data.get("scheduled_at"):
            job_data["scheduled_at"] = job.config.calculate_scheduled_time()

        insert_sql = """
        INSERT INTO jobs (
            job_id, job_type, priority, delay_seconds, max_retries,
            retry_count, parameters, status, created_at, scheduled_at,
            started_at, completed_at, error_message, result
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        ON CONFLICT (job_id) DO UPDATE SET
            status = EXCLUDED.status,
            retry_count = EXCLUDED.retry_count,
            started_at = EXCLUDED.started_at,
            completed_at = EXCLUDED.completed_at,
            error_message = EXCLUDED.error_message,
            result = EXCLUDED.result
        """

        async with self.pool.acquire() as conn:
            await conn.execute(
                insert_sql,
                job_data["job_id"],
                job_data["job_type"],
                job_data["priority"],
                job_data["delay_seconds"],
                job_data["max_retries"],
                job_data["retry_count"],
                json.dumps(job_data["parameters"]),
                job_data["status"],
                job_data["created_at"],
                job_data.get("scheduled_at"),
                job_data.get("started_at"),
                job_data.get("completed_at"),
                job_data.get("error_message"),
                json.dumps(job_data.get("result")) if job_data.get("result") else None,
            )

    async def fetch_pending_jobs(
        self,
        limit: int = 100,
        priority: Optional[JobPriority] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch pending jobs that are ready to be scheduled.
        
        Args:
            limit: Maximum number of jobs to fetch
            priority: Optional priority filter
            
        Returns:
            List of job dictionaries
        """
        if not self.pool:
            raise RuntimeError("Database connection not established. Call connect() first.")

        now = datetime.utcnow()
        
        if priority:
            query = """
            SELECT * FROM jobs
            WHERE status = $1
            AND scheduled_at <= $2
            AND priority = $3
            ORDER BY priority DESC, scheduled_at ASC
            LIMIT $4
            """
            params = [JobStatus.PENDING.value, now, priority.value, limit]
        else:
            query = """
            SELECT * FROM jobs
            WHERE status = $1
            AND scheduled_at <= $2
            ORDER BY 
                CASE priority
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'medium' THEN 3
                    WHEN 'low' THEN 4
                END,
                scheduled_at ASC
            LIMIT $3
            """
            params = [JobStatus.PENDING.value, now, limit]

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
        return [dict(row) for row in rows]

    async def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        error_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update the status of a job.
        
        Args:
            job_id: ID of the job to update
            status: New status
            error_message: Optional error message if job failed
            result: Optional result data if job completed
        """
        if not self.pool:
            raise RuntimeError("Database connection not established. Call connect() first.")

        now = datetime.utcnow()
        
        update_sql = """
        UPDATE jobs
        SET status = $1,
            started_at = CASE WHEN $1 = 'running' THEN $2 ELSE started_at END,
            completed_at = CASE WHEN $1 IN ('completed', 'failed', 'cancelled') THEN $2 ELSE completed_at END,
            error_message = $3,
            result = $4
        WHERE job_id = $5
        """

        async with self.pool.acquire() as conn:
            await conn.execute(
                update_sql,
                status.value,
                now,
                error_message,
                json.dumps(result) if result else None,
                job_id,
            )

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific job by ID.
        
        Args:
            job_id: ID of the job to retrieve
            
        Returns:
            Job dictionary or None if not found
        """
        if not self.pool:
            raise RuntimeError("Database connection not established. Call connect() first.")

        query = "SELECT * FROM jobs WHERE job_id = $1"
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, job_id)
            
        return dict(row) if row else None

    async def delete_job(self, job_id: str) -> None:
        """
        Delete a job from the database.
        
        Args:
            job_id: ID of the job to delete
        """
        if not self.pool:
            raise RuntimeError("Database connection not established. Call connect() first.")

        delete_sql = "DELETE FROM jobs WHERE job_id = $1"
        
        async with self.pool.acquire() as conn:
            await conn.execute(delete_sql, job_id)
