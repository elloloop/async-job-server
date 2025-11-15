# Examples

This directory contains example applications and scripts demonstrating how to use the async jobs library.

## Files

- **app.py**: Example FastAPI application with jobs API
- **handlers.py**: Example job handlers
- **client.py**: Example client script for enqueueing jobs
- **.env.example**: Example environment configuration

## Running the Example

### 1. Set up environment

Copy the example environment file:
```bash
cp examples/.env.example examples/.env
```

Edit `.env` with your PostgreSQL and AWS SQS credentials.

### 2. Initialize the database

```bash
# Using scheduler with --init-db flag
export $(cat examples/.env | xargs)
async-jobs-scheduler --init-db --log-level INFO
# Press Ctrl+C after initialization
```

### 3. Run the FastAPI application

```bash
cd examples
export $(cat .env | xargs)
python app.py
```

The API will be available at `http://localhost:8000`. Visit `http://localhost:8000/docs` for interactive API documentation.

### 4. Run the scheduler

In a separate terminal:
```bash
export $(cat examples/.env | xargs)
async-jobs-scheduler --log-level INFO
```

### 5. Run workers

In separate terminals for each queue:

**Notifications queue:**
```bash
export $(cat examples/.env | xargs)
export ASYNC_JOBS_HANDLERS_MODULE=examples.handlers
async-jobs-worker --queue $ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS --log-level INFO
```

**Message labeling queue:**
```bash
export $(cat examples/.env | xargs)
export ASYNC_JOBS_HANDLERS_MODULE=examples.handlers
async-jobs-worker --queue $ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING --log-level INFO
```

### 6. Enqueue jobs using the client

In another terminal:
```bash
cd examples
export $(cat .env | xargs)
python client.py
```

## Testing Locally with LocalStack

For local testing with SQS, you can use LocalStack:

```bash
# Start LocalStack with SQS
docker run -d -p 4566:4566 -e SERVICES=sqs localstack/localstack

# Create queues
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name notifications
aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name message-labeling

# Update .env to use LocalStack endpoints
export ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS=http://localhost:4566/000000000000/notifications
export ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING=http://localhost:4566/000000000000/message-labeling
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1
```

## API Usage Examples

### Enqueue a job

```bash
curl -X POST http://localhost:8000/jobs/enqueue \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "tenant-123",
    "use_case": "notifications",
    "type": "example_notification",
    "queue": "notifications",
    "payload": {
      "recipient": "user@example.com",
      "message": "Hello!"
    },
    "delay_tolerance_seconds": 60,
    "max_attempts": 3,
    "backoff_policy": {
      "type": "exponential",
      "base_delay_seconds": 60,
      "max_delay_seconds": 3600
    }
  }'
```

### Get job details

```bash
curl http://localhost:8000/jobs/{job_id}
```

### List jobs

```bash
curl "http://localhost:8000/jobs/?tenant_id=tenant-123&limit=10"
```

## Troubleshooting

- **Database connection errors**: Ensure PostgreSQL is running and credentials are correct
- **SQS errors**: Check AWS credentials and queue URLs
- **Handler not found**: Ensure `ASYNC_JOBS_HANDLERS_MODULE` is set correctly and handlers are imported
- **Jobs not processing**: Check that scheduler and workers are running and connected to the correct queues
