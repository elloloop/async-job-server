# Example Environment Configuration

This directory contains example applications demonstrating how to use the async_jobs library.

## Files

- `example_app.py`: Complete FastAPI application with async_jobs integration
- `http_client_example.py`: Example of using the HTTP client to enqueue jobs remotely
- `.env.example`: Example environment variables

## Setup

1. Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

2. Set up database:

```bash
# Connect to your PostgreSQL database and run:
psql -U your_user -d your_db -f - << 'EOF'
# Paste the DDL from async_jobs.ddl.JOBS_TABLE_DDL here
EOF
```

3. Run the example application:

```bash
# From the repository root
poetry run python examples/example_app.py
```

4. In separate terminals, run scheduler and worker:

```bash
# Terminal 2: Run scheduler
poetry run async-jobs-scheduler

# Terminal 3: Run worker
poetry run async-jobs-worker \
  --queue https://sqs.us-east-1.amazonaws.com/123/notifications \
  --handlers-module examples.example_app
```

## Testing

1. Create a user signup (which enqueues jobs):

```bash
curl -X POST "http://localhost:8000/users/signup?email=test@example.com&name=Test%20User"
```

2. Check job status:

```bash
curl http://localhost:8000/async-jobs/jobs/{job_id}
```

3. List all jobs:

```bash
curl http://localhost:8000/async-jobs/jobs
```

## Using the HTTP Client

```bash
poetry run python examples/http_client_example.py
```

## Docker

To run with Docker Compose:

```bash
# From repository root
docker-compose up
```

This will start:
- PostgreSQL
- Localstack (SQS emulator)
- Scheduler
- Workers for both notification and message labeling queues
