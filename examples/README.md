# Examples

This directory contains examples demonstrating how to use the asyncjobserver library.

## Examples

### 1. Simple Example (`simple_example.py`)

A standalone script that demonstrates the basic usage of the library without a web framework.

**Run:**
```bash
# Start dependencies
docker-compose up -d

# Run the example
python examples/simple_example.py
```

### 2. FastAPI Example (`fastapi_example.py`)

A complete FastAPI application with REST API endpoints for job management.

**Run:**
```bash
# Start dependencies
docker-compose up -d

# Run the server
python examples/fastapi_example.py

# Or with uvicorn
uvicorn examples.fastapi_example:app --reload
```

**API Usage:**
```bash
# Create a job
curl -X POST http://localhost:8000/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "SayHelloJob",
    "priority": "medium",
    "delay_seconds": 5,
    "parameters": {"name": "World"}
  }'

# Get job status
curl http://localhost:8000/jobs/{job_id}

# Health check
curl http://localhost:8000/health
```

## Prerequisites

Both examples require:

1. **PostgreSQL** - For job storage
2. **LocalStack** - For local SQS queues

The easiest way to set these up is using Docker Compose:

```bash
cd /path/to/async-job-server
docker-compose up -d
```

This will start:
- PostgreSQL on port 5432
- LocalStack (SQS) on port 4566

## Job Types

Both examples include these job types:

- **SayHelloJob**: Prints a hello message with a customizable name
- **CalculationJob**: Performs arithmetic operations

You can add your own job types by:

1. Creating a class that inherits from `Job`
2. Implementing the `handle()` method
3. Adding it to the job registry
