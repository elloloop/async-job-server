# AsyncJobServer

A Python library for distributed job scheduling, queuing, and execution with PostgreSQL and AWS SQS integration.

## Overview

`asyncjobserver` provides a robust framework for handling asynchronous job processing in distributed systems. It offers:

- **Job Management**: Define custom jobs with a simple interface
- **PostgreSQL Storage**: Reliable job persistence and queuing
- **AWS SQS Integration**: Distributed job distribution across workers
- **Priority Queues**: Multiple priority levels (critical, high, medium, low)
- **Scheduler Service**: Automatic job scheduling based on timing and priority
- **Worker Service**: Concurrent job execution with retry support
- **FastAPI Integration**: Ready-to-use example with REST API

## Installation

```bash
pip install asyncjobserver
```

For development:

```bash
pip install -r requirements-dev.txt
```

## Quick Start

### 1. Define a Job

```python
from asyncjobserver import Job, JobPriority
from typing import Dict, Any

class SayHelloJob(Job):
    async def handle(self) -> Dict[str, Any]:
        name = self.config.parameters.get("name", "World")
        print(f"Hello, {name}!")
        return {"message": f"Greeted {name}"}
```

### 2. Set Up Storage and Queue

```python
from asyncjobserver.storage.postgres import PostgresJobStorage
from asyncjobserver.queue.sqs import SQSQueue

# Initialize PostgreSQL storage
storage = PostgresJobStorage(
    host="localhost",
    port=5432,
    database="asyncjobs",
    user="postgres",
    password="postgres"
)
await storage.connect()
await storage.initialize()

# Initialize SQS queue
queue = SQSQueue(
    region_name="us-east-1",
    queue_name_prefix="asyncjobs"
)
await queue.initialize()
```

### 3. Start Scheduler and Worker

```python
from asyncjobserver import Scheduler, Worker

# Job registry
job_registry = {
    "SayHelloJob": SayHelloJob,
}

# Create scheduler
scheduler = Scheduler(
    storage=storage,
    queue=queue,
    job_registry=job_registry,
    poll_interval=5.0
)
await scheduler.start()

# Create worker
worker = Worker(
    storage=storage,
    queue=queue,
    job_registry=job_registry,
    concurrency=5
)
await worker.start()
```

### 4. Submit Jobs

```python
# Create a job instance
job = SayHelloJob(
    priority=JobPriority.MEDIUM,
    delay_seconds=10,
    parameters={"name": "FastAPI"}
)

# Save to storage (scheduler will pick it up)
await storage.save_job(job)
```

## Architecture

### Components

1. **Job**: Base class for defining work units
   - Implements `handle()` method for execution logic
   - Supports parameters, priorities, delays, and retries

2. **PostgreSQL Storage**: Job persistence layer
   - Stores job metadata and status
   - Acts as a durable queue
   - Supports status tracking and history

3. **SQS Queue**: Message distribution layer
   - Distributes jobs to workers
   - Separate queues per priority level
   - Ensures at-least-once delivery

4. **Scheduler**: Job scheduling service
   - Polls PostgreSQL for pending jobs
   - Distributes jobs to SQS based on schedule and priority
   - Updates job status

5. **Worker**: Job execution service
   - Polls SQS queues for jobs
   - Executes job handlers
   - Updates status and handles retries

### Flow

```
[Job Submission] → [PostgreSQL] → [Scheduler] → [SQS] → [Worker] → [Execution]
                         ↑                                    ↓
                         └────────────── [Status Updates] ────┘
```

## FastAPI Example

A complete FastAPI example is provided in `examples/fastapi_example.py`:

```bash
# Start the server
python examples/fastapi_example.py
```

### API Endpoints

- `POST /jobs` - Create a new job
- `GET /jobs/{job_id}` - Get job status
- `GET /health` - Health check

### Example Request

```bash
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "SayHelloJob",
    "priority": "medium",
    "delay_seconds": 5,
    "parameters": {"name": "World"}
  }'
```

## Job Lifecycle

1. **PENDING**: Job created and waiting for scheduled time
2. **SCHEDULED**: Scheduler has distributed job to SQS
3. **RUNNING**: Worker is executing the job
4. **COMPLETED**: Job finished successfully
5. **FAILED**: Job failed after max retries
6. **CANCELLED**: Job was cancelled

## Configuration

### Storage Configuration

```python
storage = PostgresJobStorage(
    host="localhost",
    port=5432,
    database="asyncjobs",
    user="postgres",
    password="postgres",
    pool_min_size=10,
    pool_max_size=20
)
```

### Queue Configuration

```python
queue = SQSQueue(
    region_name="us-east-1",
    queue_name_prefix="asyncjobs",
    aws_access_key_id="YOUR_KEY",
    aws_secret_access_key="YOUR_SECRET",
    endpoint_url="http://localhost:4566"  # For LocalStack
)
```

### Scheduler Configuration

```python
scheduler = Scheduler(
    storage=storage,
    queue=queue,
    poll_interval=5.0,      # Poll every 5 seconds
    batch_size=100,         # Max jobs per poll
    job_registry=job_registry
)
```

### Worker Configuration

```python
worker = Worker(
    storage=storage,
    queue=queue,
    job_registry=job_registry,
    priorities=[JobPriority.HIGH, JobPriority.MEDIUM],  # Which queues to poll
    concurrency=5,          # Max concurrent jobs
    poll_interval=1.0,      # Poll every second
    max_messages_per_poll=10
)
```

## Development Setup

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- AWS account (or LocalStack for local development)

### Local Development with LocalStack

```bash
# Install LocalStack
pip install localstack

# Start LocalStack
localstack start

# Configure SQS to use LocalStack
queue = SQSQueue(
    region_name="us-east-1",
    queue_name_prefix="asyncjobs",
    endpoint_url="http://localhost:4566"
)
```

### Running Tests

```bash
pytest tests/
```

## Advanced Usage

### Custom Job with Parameters

```python
class SendEmailJob(Job):
    async def handle(self) -> Dict[str, Any]:
        to = self.config.parameters["to"]
        subject = self.config.parameters["subject"]
        body = self.config.parameters["body"]
        
        # Send email logic here
        await send_email(to, subject, body)
        
        return {"sent_to": to, "subject": subject}

# Create and submit
job = SendEmailJob(
    priority=JobPriority.HIGH,
    parameters={
        "to": "user@example.com",
        "subject": "Hello",
        "body": "This is a test"
    }
)
await storage.save_job(job)
```

### Job Retries

Jobs automatically retry on failure:

```python
job = MyJob(
    max_retries=5,  # Retry up to 5 times
    parameters={"data": "value"}
)
```

### Priority Levels

```python
from asyncjobserver import JobPriority

# Available priorities (highest to lowest)
JobPriority.CRITICAL
JobPriority.HIGH
JobPriority.MEDIUM
JobPriority.LOW
```

### Delayed Execution

```python
# Execute after 60 seconds
job = MyJob(
    delay_seconds=60,
    parameters={"data": "value"}
)
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions, please use the GitHub issue tracker.
