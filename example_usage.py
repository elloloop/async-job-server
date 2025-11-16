"""Example usage of the async_jobs library.

This file demonstrates how to use the library in different scenarios.
"""

import asyncio
import os
from datetime import datetime, timedelta

import asyncpg
from fastapi import FastAPI

from async_jobs.config import AsyncJobsConfig
from async_jobs.ddl import JOBS_TABLE_DDL
from async_jobs.fastapi_router import create_jobs_router
from async_jobs.http_client import AsyncJobsHttpClient
from async_jobs.registry import job_registry
from async_jobs.service import JobService


# Example 1: Register job handlers
@job_registry.handler("send_email")
async def send_email_handler(ctx, payload):
    """Example email handler."""
    email = payload["email"]
    subject = payload["subject"]
    body = payload["body"]
    print(f"Sending email to {email}: {subject}")
    # In real implementation: await email_service.send(email, subject, body)


@job_registry.handler("process_payment")
async def process_payment_handler(ctx, payload):
    """Example payment handler."""
    amount = payload["amount"]
    currency = payload["currency"]
    print(f"Processing payment: {amount} {currency}")
    # In real implementation: await payment_service.process(amount, currency)


# Example 2: Setup FastAPI app with router
async def setup_fastapi_app():
    """Example FastAPI app setup."""
    app = FastAPI()

    # Load config
    config = AsyncJobsConfig.from_env()

    # Create DB pool
    db_pool = await asyncpg.create_pool(config.db_dsn)

    # Apply schema (in production, use migrations)
    async with db_pool.acquire() as conn:
        await conn.execute(JOBS_TABLE_DDL)

    # Create router
    def job_service_factory():
        return JobService(config, db_pool)

    router = create_jobs_router(
        job_service_factory, auth_token=config.enqueue_auth_token
    )
    app.include_router(router, prefix="/async-jobs")

    return app


# Example 3: Enqueue jobs directly via service
async def enqueue_jobs_directly():
    """Example of enqueueing jobs using JobService directly."""
    config = AsyncJobsConfig.from_env()
    db_pool = await asyncpg.create_pool(config.db_dsn)
    service = JobService(config, db_pool)

    # Enqueue a simple job
    job_id = await service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="send_email",
        queue="async-notifications",
        payload={
            "email": "user@example.com",
            "subject": "Welcome!",
            "body": "Welcome to our service!",
        },
    )
    print(f"Enqueued job: {job_id}")

    # Enqueue a job with custom scheduling
    job_id2 = await service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="send_email",
        queue="async-notifications",
        payload={"email": "user@example.com", "subject": "Reminder", "body": "..."},
        run_at=datetime.utcnow() + timedelta(hours=1),  # Run in 1 hour
        delay_tolerance=timedelta(seconds=300),  # 5 minute delay tolerance
        max_attempts=3,
        backoff_policy={"type": "exponential", "base_seconds": 30},
    )
    print(f"Enqueued scheduled job: {job_id2}")

    # Enqueue with deduplication
    job_id3 = await service.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="send_email",
        queue="async-notifications",
        payload={"email": "user@example.com", "subject": "Important", "body": "..."},
        dedupe_key="email-user@example.com-important",  # Prevents duplicates
    )
    print(f"Enqueued job with dedupe: {job_id3}")

    await db_pool.close()


# Example 4: Enqueue jobs via HTTP client
async def enqueue_jobs_via_http():
    """Example of enqueueing jobs using HTTP client."""
    client = AsyncJobsHttpClient(
        base_url="https://async-jobs.internal",
        auth_token=os.getenv("ASYNC_JOBS_TOKEN"),
    )

    job_id = await client.enqueue(
        tenant_id="tenant1",
        use_case="notifications",
        type="send_email",
        queue="async-notifications",
        payload={
            "email": "user@example.com",
            "subject": "Welcome!",
            "body": "Welcome to our service!",
        },
    )
    print(f"Enqueued job via HTTP: {job_id}")


# Example 5: Query jobs
async def query_jobs():
    """Example of querying jobs."""
    config = AsyncJobsConfig.from_env()
    db_pool = await asyncpg.create_pool(config.db_dsn)
    service = JobService(config, db_pool)

    # Get a specific job
    job = await service.get_job(job_id)
    print(f"Job status: {job.status}")
    print(f"Job attempts: {job.attempts}/{job.max_attempts}")

    # List jobs for a tenant
    jobs = await service.list_jobs(tenant_id="tenant1", status="pending")
    print(f"Found {len(jobs)} pending jobs for tenant1")

    # List jobs for a use case
    jobs = await service.list_jobs(use_case="notifications", limit=100)
    print(f"Found {len(jobs)} jobs for notifications use case")

    await db_pool.close()


if __name__ == "__main__":
    # Run examples (uncomment as needed)
    # asyncio.run(enqueue_jobs_directly())
    # asyncio.run(enqueue_jobs_via_http())
    # asyncio.run(query_jobs())
    pass
