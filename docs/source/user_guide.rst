User Guide
==========

This guide covers the main features and concepts of the async-jobs library.

Architecture Overview
---------------------

The async-jobs library consists of three main components:

1. **API Server**: FastAPI application that enqueues jobs via REST endpoints
2. **Scheduler**: Background process that dispatches scheduled jobs to SQS
3. **Worker**: Background process that executes jobs from SQS queue

Job Lifecycle
-------------

1. **Enqueue**: Job is created via API and stored in PostgreSQL
2. **Schedule**: Scheduler finds jobs past their deadline and pushes to SQS
3. **Execute**: Worker receives message, executes handler, updates status
4. **Retry**: Failed jobs are retried based on backoff strategy
5. **Complete**: Job marked as completed or permanently failed

Job Registry
------------

Register job handlers using the decorator pattern:

.. code-block:: python

   from async_jobs import job_registry

   @job_registry.register("process_payment")
   async def process_payment(job_data: dict) -> dict:
       """Process a payment transaction."""
       amount = job_data["amount"]
       # ... processing logic
       return {"transaction_id": "txn_123"}

Job handlers receive the job data as a dictionary and should return
a dictionary with the result.

Multi-Tenancy
-------------

The library supports multi-tenant isolation:

.. code-block:: python

   from async_jobs import JobService, AsyncJobsConfig

   config = AsyncJobsConfig()
   service = JobService(config)

   # Enqueue job for specific tenant
   job = await service.enqueue_job(
       tenant_id="tenant_123",
       job_type="send_email",
       job_data={"recipient": "user@example.com"},
       run_after=None,  # Run immediately
       run_before=datetime.now() + timedelta(hours=1),  # 1hr deadline
   )

Tenant quotas are enforced to prevent abuse:

.. code-block:: bash

   # Allow 100 jobs per tenant per hour
   export TENANT_JOB_QUOTA="100"

Deadline-Based Scheduling
--------------------------

Unlike traditional delay-based scheduling, this library uses Meta-style
deadline-based scheduling:

- **run_after**: Earliest time to execute (default: now)
- **run_before**: Latest acceptable time (deadline)

This provides flexibility for the scheduler to optimize execution while
ensuring jobs complete before their deadline.

.. code-block:: python

   from datetime import datetime, timedelta

   # Job must run between 10 min and 1 hour from now
   await service.enqueue_job(
       tenant_id="tenant_123",
       job_type="generate_report",
       job_data={"report_id": "rpt_456"},
       run_after=datetime.now() + timedelta(minutes=10),
       run_before=datetime.now() + timedelta(hours=1),
   )

Retry Strategies
----------------

Configure retry behavior using backoff strategies:

Exponential Backoff
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from async_jobs.models import JobRetryConfig

   retry_config = JobRetryConfig(
       max_retries=5,
       backoff_strategy="exponential",
       base_delay_seconds=60,  # Start with 1 minute
       max_delay_seconds=3600,  # Cap at 1 hour
   )

Linear Backoff
~~~~~~~~~~~~~~

.. code-block:: python

   retry_config = JobRetryConfig(
       max_retries=3,
       backoff_strategy="linear",
       base_delay_seconds=300,  # 5 minutes between retries
   )

Constant Backoff
~~~~~~~~~~~~~~~~

.. code-block:: python

   retry_config = JobRetryConfig(
       max_retries=10,
       backoff_strategy="constant",
       base_delay_seconds=120,  # Always wait 2 minutes
   )

Job Status
----------

Jobs progress through the following states:

- ``pending``: Job created, waiting to be scheduled
- ``scheduled``: Job pushed to SQS queue
- ``running``: Job currently being executed
- ``completed``: Job finished successfully
- ``failed``: Job failed after all retries exhausted
- ``cancelled``: Job manually cancelled

Query Job Status
~~~~~~~~~~~~~~~~

.. code-block:: python

   from async_jobs import JobStore

   store = JobStore(config)
   job = await store.get_job(job_id="job_123")

   print(f"Status: {job.status}")
   print(f"Attempts: {job.attempts}")
   print(f"Result: {job.result}")

Error Handling
--------------

The library provides specific exception types:

.. code-block:: python

   from async_jobs.errors import (
       JobNotFoundError,
       QuotaExceededError,
       AuthTokenError,
   )

   try:
       await service.enqueue_job(...)
   except QuotaExceededError:
       # Handle quota exceeded
       pass
   except JobNotFoundError:
       # Handle missing job
       pass

HTTP Client
-----------

For service-to-service communication, use the HTTP client:

.. code-block:: python

   from async_jobs import AsyncJobsHttpClient

   client = AsyncJobsHttpClient(
       base_url="http://jobs-api:8000",
       auth_token="secret_token",
   )

   # Enqueue job via HTTP
   job = await client.enqueue_job(
       tenant_id="tenant_123",
       job_type="send_notification",
       job_data={"user_id": "usr_456"},
   )

   # Get job status
   job = await client.get_job(job_id=job.id)

Database Schema
---------------

The library requires a PostgreSQL table for job storage.
Apply the DDL during initialization:

.. code-block:: python

   from async_jobs import JOBS_TABLE_DDL
   import asyncpg

   conn = await asyncpg.connect(database_url)
   await conn.execute(JOBS_TABLE_DDL)

Testing
-------

The library is designed to be testable:

.. code-block:: python

   import pytest
   from async_jobs import JobRegistry

   @pytest.mark.asyncio
   async def test_job_handler():
       registry = JobRegistry()

       @registry.register("test_job")
       async def test_handler(job_data: dict) -> dict:
           return {"status": "ok"}

       handler = registry.get_handler("test_job")
       result = await handler({"input": "data"})

       assert result["status"] == "ok"
