# Async Jobs Platform Library

A reusable Python library for building async job platforms with FastAPI, PostgreSQL, and AWS SQS.

## Features

- **PostgreSQL-backed job store** - Jobs are stored in PostgreSQL as the source of truth
- **SQS transport** - Uses AWS SQS for job message transport
- **Meta-style delay tolerance** - Supports deadline-based scheduling with delay tolerance
- **Multi-tenant aware** - Built-in support for tenant isolation and quotas
- **FastAPI integration** - Exposes HTTP endpoints via FastAPI router
- **Python client** - Simple Python client for enqueueing jobs
- **ECS-friendly** - Designed to run as Docker containers on AWS ECS
- **Scheduler and worker processes** - Standalone CLI tools for scheduling and processing jobs

## Installation

```bash
pip install -e .
```

Or install with development dependencies:

```bash
pip install -e ".[dev]"
```

## Quick Start

### 1. Database Setup

Apply the database schema:

```python
from async_jobs.ddl import JOBS_TABLE_DDL
import asyncpg

async def setup_db():
    conn = await asyncpg.connect("postgresql://user:pass@localhost/db")
    await conn.execute(JOBS_TABLE_DDL)
    await conn.close()
```

### 2. Configuration

Set environment variables:

```bash
export ASYNC_JOBS_DB_DSN="postgresql://user:pass@localhost/db"
export ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS="https://sqs.us-east-1.amazonaws.com/123/notifications"
export ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING="https://sqs.us-east-1.amazonaws.com/123/labeling"
export ASYNC_JOBS_NOTIFICATIONS_MAX_CONCURRENT=10
export ASYNC_JOBS_NOTIFICATIONS_DEFAULT_DELAY_TOLERANCE_SECONDS=3
export ASYNC_JOBS_MESSAGE_LABELING_MAX_CONCURRENT=10
export ASYNC_JOBS_MESSAGE_LABELING_DEFAULT_DELAY_TOLERANCE_SECONDS=3
```

Optional:

```bash
export ASYNC_JOBS_ENQUEUE_AUTH_TOKEN="secret-token"
export ASYNC_JOBS_PER_TENANT_QUOTAS='{"tenant1": {"notifications": 100}}'
```

### 3. FastAPI Integration

```python
from fastapi import FastAPI
from async_jobs.config import AsyncJobsConfig
from async_jobs.fastapi_router import create_jobs_router
from async_jobs.service import JobService
import asyncpg

app = FastAPI()

config = AsyncJobsConfig.from_env()
db_pool = await asyncpg.create_pool(config.db_dsn)

def job_service_factory():
    return JobService(config, db_pool)

jobs_router = create_jobs_router(job_service_factory, auth_token=config.enqueue_auth_token)
app.include_router(jobs_router, prefix="/async-jobs")
```

### 4. Register Job Handlers

```python
from async_jobs.registry import job_registry

@job_registry.handler("send_notification")
async def send_notification(ctx, payload):
    email = payload["email"]
    template = payload["template"]
    # Send notification...
    pass
```

### 5. Enqueue Jobs

**Via Python client (direct):**

```python
from async_jobs.config import AsyncJobsConfig
from async_jobs.service import JobService
import asyncpg

config = AsyncJobsConfig.from_env()
db_pool = await asyncpg.create_pool(config.db_dsn)
service = JobService(config, db_pool)

job_id = await service.enqueue(
    tenant_id="tenant1",
    use_case="notifications",
    type="send_notification",
    queue="async-notifications",
    payload={"email": "user@example.com", "template": "welcome"},
)
```

**Via HTTP client:**

```python
from async_jobs.http_client import AsyncJobsHttpClient

client = AsyncJobsHttpClient(
    base_url="https://async-jobs.internal",
    auth_token=os.getenv("ASYNC_JOBS_TOKEN"),
)

job_id = await client.enqueue(
    tenant_id="tenant1",
    use_case="notifications",
    type="send_notification",
    queue="async-notifications",
    payload={"email": "user@example.com", "template": "welcome"},
)
```

**Via HTTP API:**

```bash
curl -X POST https://async-jobs.internal/async-jobs/jobs/enqueue \
  -H "Content-Type: application/json" \
  -H "X-Async-Jobs-Token: secret-token" \
  -d '{
    "tenant_id": "tenant1",
    "use_case": "notifications",
    "type": "send_notification",
    "queue": "async-notifications",
    "payload": {"email": "user@example.com", "template": "welcome"}
  }'
```

### 6. Run Scheduler

```bash
async-jobs-scheduler
```

Or as Docker container:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install .
CMD ["async-jobs-scheduler"]
```

### 7. Run Worker

```bash
export ASYNC_JOBS_HANDLERS_MODULE="myapp.jobs.handlers"
async-jobs-worker --queue async-notifications
```

Or as Docker container:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . /app
RUN pip install .
ENV ASYNC_JOBS_HANDLERS_MODULE="myapp.jobs.handlers"
CMD ["async-jobs-worker", "--queue", "async-notifications"]
```

## API Reference

### Configuration

```python
from async_jobs.config import AsyncJobsConfig

config = AsyncJobsConfig.from_env()
```

### Service

```python
from async_jobs.service import JobService

service = JobService(config, db_pool)

# Enqueue job
job_id = await service.enqueue(...)

# Get job
job = await service.get_job(job_id)

# List jobs
jobs = await service.list_jobs(tenant_id="tenant1", status="pending")
```

### HTTP Router

```python
from async_jobs.fastapi_router import create_jobs_router

router = create_jobs_router(job_service_factory, auth_token="token")
```

Endpoints:
- `POST /jobs/enqueue` - Enqueue a new job
- `GET /jobs/{job_id}` - Get job details
- `GET /jobs` - List jobs with filters

### HTTP Client

```python
from async_jobs.http_client import AsyncJobsHttpClient

client = AsyncJobsHttpClient(base_url="https://api.example.com", auth_token="token")
job_id = await client.enqueue(...)
```

### Registry

```python
from async_jobs.registry import job_registry

@job_registry.handler("my_job_type")
async def my_handler(ctx, payload):
    # ctx contains: job_id, tenant_id, use_case, attempt
    # payload is the job payload
    pass
```

## Testing

Run unit tests:

```bash
pytest tests/unit
```

Run lightweight integration tests:

```bash
pytest tests/integration/test_lightweight.py
```

Run all tests:

```bash
pytest
```

## Architecture

- **Jobs Table**: PostgreSQL table storing all job state
- **Scheduler**: Process that selects pending jobs and sends them to SQS
- **Worker**: Process that consumes SQS messages and executes job handlers
- **FastAPI Router**: HTTP API for enqueueing and querying jobs
- **HTTP Client**: Python client for calling the HTTP API
- **Registry**: Handler registry for mapping job types to handler functions

## License

MIT
