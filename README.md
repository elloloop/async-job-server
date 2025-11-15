# Async Jobs

A reusable Python library for async job scheduling and execution using PostgreSQL and AWS SQS.

## Features

- **Job Scheduling**: Schedule jobs with deadline-based execution and delay tolerance
- **Multi-tenant Support**: Per-tenant quotas and isolation
- **Retry Logic**: Configurable backoff policies (exponential, linear, constant)
- **FastAPI Integration**: Ready-to-use API router for job management
- **HTTP Client**: Simple client for remote job enqueueing
- **Worker & Scheduler**: CLI tools for running worker and scheduler processes
- **Handler Registry**: Easy registration of job handlers

## Installation

```bash
pip install -e .
```

For development:
```bash
pip install -e ".[dev,test]"
```

## Quick Start

### 1. Database Setup

Apply the database schema to your PostgreSQL database:

```python
from async_jobs.ddl import get_ddl
import psycopg

# Execute DDL
with psycopg.connect("postgresql://...") as conn:
    with conn.cursor() as cur:
        cur.execute(get_ddl())
    conn.commit()
```

Or use the CLI with `--init-db` flag when starting the scheduler or worker.

### 2. Configuration

Set up environment variables:

```bash
# Required
export ASYNC_JOBS_DB_DSN="postgresql://user:pass@localhost:5432/dbname"

# Use case configurations
export ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS="https://sqs.us-east-1.amazonaws.com/123456789/notifications"
export ASYNC_JOBS_NOTIFICATIONS_MAX_CONCURRENT=10
export ASYNC_JOBS_NOTIFICATIONS_DEFAULT_DELAY_TOLERANCE_SECONDS=60

export ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING="https://sqs.us-east-1.amazonaws.com/123456789/message-labeling"
export ASYNC_JOBS_MESSAGE_LABELING_MAX_CONCURRENT=10
export ASYNC_JOBS_MESSAGE_LABELING_DEFAULT_DELAY_TOLERANCE_SECONDS=60

# Optional: Per-tenant quotas
export ASYNC_JOBS_PER_TENANT_QUOTAS='{"tenant1": {"max_pending_jobs": 100}}'

# Optional: Authentication
export ASYNC_JOBS_ENQUEUE_AUTH_TOKEN="secret-token"

# Optional: Timing configurations
export ASYNC_JOBS_SCHEDULER_INTERVAL_SECONDS=5
export ASYNC_JOBS_WORKER_POLL_INTERVAL_SECONDS=1
export ASYNC_JOBS_WORKER_VISIBILITY_TIMEOUT_SECONDS=300
export ASYNC_JOBS_LEASE_DURATION_SECONDS=300
```

### 3. Define Job Handlers

Create a module with your job handlers:

```python
# myapp/job_handlers.py
from async_jobs.registry import job_registry
from async_jobs.models import JobContext
from typing import Dict, Any

@job_registry.handler("send_notification")
async def send_notification(ctx: JobContext, payload: Dict[str, Any]):
    """Handle notification sending."""
    recipient = payload["recipient"]
    message = payload["message"]
    # Send notification...
    return {"status": "sent", "recipient": recipient}

@job_registry.handler("process_data")
async def process_data(ctx: JobContext, payload: Dict[str, Any]):
    """Handle data processing."""
    data_id = payload["data_id"]
    # Process data...
    return {"status": "processed", "data_id": data_id}
```

### 4. Integrate with FastAPI

```python
from fastapi import FastAPI
from async_jobs import create_jobs_router, JobService, JobStore, AsyncJobsConfig
from psycopg_pool import AsyncConnectionPool

app = FastAPI()

# Initialize connection pool
config = AsyncJobsConfig.from_env()
db_pool = AsyncConnectionPool(conninfo=config.db_dsn, min_size=2, max_size=10)

# Factory function for job service
def get_job_service():
    store = JobStore(db_pool)
    return JobService(config, store)

# Add jobs router
jobs_router = create_jobs_router(
    job_service_factory=get_job_service,
    require_auth_token=True,
    expected_auth_token=config.enqueue_auth_token,
)
app.include_router(jobs_router)

@app.on_event("startup")
async def startup():
    await db_pool.wait()

@app.on_event("shutdown")
async def shutdown():
    await db_pool.close()
```

### 5. Enqueue Jobs Programmatically

```python
from async_jobs import AsyncJobsHttpClient
from datetime import datetime

client = AsyncJobsHttpClient(
    base_url="http://localhost:8000",
    auth_token="secret-token"
)

# Enqueue a job
job_id = await client.enqueue(
    tenant_id="tenant1",
    use_case="notifications",
    type="send_notification",
    queue="notifications",
    payload={
        "recipient": "user@example.com",
        "message": "Hello!"
    },
    delay_tolerance_seconds=60,
    max_attempts=3,
    backoff_policy={
        "type": "exponential",
        "base_delay_seconds": 60,
        "max_delay_seconds": 3600
    }
)
print(f"Enqueued job: {job_id}")
```

### 6. Run the Scheduler

The scheduler selects pending jobs, enforces capacity limits, and pushes job IDs to SQS:

```bash
async-jobs-scheduler --log-level INFO
```

With database initialization:
```bash
async-jobs-scheduler --init-db --log-level INFO
```

### 7. Run Workers

Workers consume jobs from SQS, execute handlers, and update job status:

```bash
# Set handler module
export ASYNC_JOBS_HANDLERS_MODULE="myapp.job_handlers"

# Start worker for notifications queue
async-jobs-worker \
  --queue https://sqs.us-east-1.amazonaws.com/123456789/notifications \
  --log-level INFO
```

## Architecture

### Job Lifecycle

1. **Enqueue**: Job is created in PostgreSQL with status `pending`
2. **Schedule**: Scheduler selects jobs based on `deadline_at`, leases them, and pushes IDs to SQS
3. **Execute**: Worker consumes from SQS, executes handler, and updates status to `succeeded`
4. **Retry**: On failure, job is retried with backoff (status returns to `pending`)
5. **Dead**: After max attempts, job is marked `dead`

### Components

- **JobStore**: Database access layer for jobs
- **JobService**: Business logic for job operations
- **JobRegistry**: Handler registration system
- **Scheduler**: Periodic process that leases jobs and pushes to SQS
- **Worker**: Consumes SQS messages and executes handlers
- **FastAPI Router**: HTTP API for job management
- **HTTP Client**: Client library for remote job enqueueing

## Configuration Reference

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ASYNC_JOBS_DB_DSN` | Yes | PostgreSQL connection string |
| `ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS` | No | SQS queue URL for notifications |
| `ASYNC_JOBS_NOTIFICATIONS_MAX_CONCURRENT` | No | Max concurrent notifications jobs (default: 10) |
| `ASYNC_JOBS_NOTIFICATIONS_DEFAULT_DELAY_TOLERANCE_SECONDS` | No | Default delay tolerance for notifications (default: 60) |
| `ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING` | No | SQS queue URL for message labeling |
| `ASYNC_JOBS_MESSAGE_LABELING_MAX_CONCURRENT` | No | Max concurrent message labeling jobs (default: 10) |
| `ASYNC_JOBS_MESSAGE_LABELING_DEFAULT_DELAY_TOLERANCE_SECONDS` | No | Default delay tolerance for message labeling (default: 60) |
| `ASYNC_JOBS_PER_TENANT_QUOTAS` | No | JSON object with per-tenant quotas |
| `ASYNC_JOBS_ENQUEUE_AUTH_TOKEN` | No | Authentication token for API |
| `ASYNC_JOBS_SCHEDULER_INTERVAL_SECONDS` | No | Scheduler loop interval (default: 5) |
| `ASYNC_JOBS_WORKER_POLL_INTERVAL_SECONDS` | No | Worker SQS poll interval (default: 1) |
| `ASYNC_JOBS_WORKER_VISIBILITY_TIMEOUT_SECONDS` | No | SQS visibility timeout (default: 300) |
| `ASYNC_JOBS_LEASE_DURATION_SECONDS` | No | Job lease duration (default: 300) |
| `ASYNC_JOBS_HANDLERS_MODULE` | No | Python module containing job handlers (for worker) |

## Database Schema

The library creates a single `jobs` table with the following structure:

- `id`: UUID primary key
- `tenant_id`: Tenant identifier
- `use_case`: Use case (e.g., "notifications", "message_labeling")
- `type`: Job type (handler name)
- `queue`: SQS queue name
- `status`: Job status (pending, running, succeeded, dead, cancelled)
- `payload`: JSON payload for the job
- `run_at`: When the job should run
- `delay_tolerance`: How long the job can be delayed
- `deadline_at`: Absolute deadline (run_at + delay_tolerance)
- `priority`: Job priority (higher = more important)
- `attempts`: Number of execution attempts
- `max_attempts`: Maximum retry attempts
- `backoff_policy`: Retry backoff configuration
- `lease_expires_at`: When the current lease expires
- `last_error`: Last error details (if failed)
- `dedupe_key`: Optional deduplication key
- `enqueue_failed`: Whether enqueueing failed
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

Indexes:
- `idx_jobs_pending_deadline`: For efficient scheduling
- `idx_jobs_tenant_status`: For tenant queries
- `idx_jobs_use_case_status`: For use case queries
- `idx_jobs_dedupe_key`: For deduplication

## API Endpoints

### POST /jobs/enqueue

Enqueue a new job.

**Request:**
```json
{
  "tenant_id": "tenant1",
  "use_case": "notifications",
  "type": "send_email",
  "queue": "notifications",
  "payload": {"to": "user@example.com"},
  "run_at": "2024-01-01T12:00:00Z",
  "delay_tolerance_seconds": 60,
  "max_attempts": 3,
  "backoff_policy": {
    "type": "exponential",
    "base_delay_seconds": 60,
    "max_delay_seconds": 3600
  },
  "dedupe_key": "optional-dedup-key",
  "priority": 0
}
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### GET /jobs/{job_id}

Get job details by ID.

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "tenant_id": "tenant1",
  "use_case": "notifications",
  "type": "send_email",
  "status": "succeeded",
  "payload": {"to": "user@example.com"}
}
```

### GET /jobs/

List jobs with optional filters.

**Query Parameters:**
- `tenant_id`: Filter by tenant
- `use_case`: Filter by use case
- `status`: Filter by status
- `limit`: Max results (default: 100, max: 1000)

**Response:**
```json
{
  "jobs": [...]
}
```

## Testing

Run unit tests:
```bash
pytest tests/
```

Run tests with coverage:
```bash
pytest tests/ --cov=async_jobs --cov-report=html
```

## Development

Format code:
```bash
black async_jobs/ tests/
```

Lint code:
```bash
ruff check async_jobs/ tests/
```

Type checking:
```bash
mypy async_jobs/
```

## AWS ECS Deployment

### Scheduler Container

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY . .
RUN pip install .

CMD ["async-jobs-scheduler", "--log-level", "INFO"]
```

### Worker Container

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY . .
COPY myapp/ /app/myapp/
RUN pip install .

ENV ASYNC_JOBS_HANDLERS_MODULE=myapp.job_handlers

CMD ["async-jobs-worker", "--queue", "${QUEUE_URL}", "--log-level", "INFO"]
```

### Task Definition

Configure environment variables and ensure:
- IAM role has SQS and Secrets Manager permissions
- Database credentials are in Secrets Manager or environment
- SQS queues are created
- Security groups allow database access

## License

Proprietary - Internal use only

## Support

For issues or questions, contact the infrastructure team.
