Deployment Guide
================

This guide covers deploying the async-jobs library in production environments.

Prerequisites
-------------

- PostgreSQL 13+ database
- AWS SQS queue
- AWS credentials (for SQS access)
- Python 3.11+

Environment Variables
---------------------

Core Configuration
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Database connection
   DATABASE_URL=postgresql://user:password@host:5432/database

   # AWS configuration
   AWS_REGION=us-east-1
   JOBS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/123456789/jobs-queue

   # Optional: AWS credentials (if not using IAM roles)
   AWS_ACCESS_KEY_ID=AKIA...
   AWS_SECRET_ACCESS_KEY=secret...

Quota and Limits
~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Maximum jobs per tenant per hour
   TENANT_JOB_QUOTA=100

Scheduler Configuration
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # How often to check for schedulable jobs (seconds)
   SCHEDULER_INTERVAL=30

   # Maximum jobs to dispatch per cycle
   SCHEDULER_BATCH_SIZE=100

Worker Configuration
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Number of concurrent workers
   WORKER_CONCURRENCY=10

   # Maximum time for job execution (seconds)
   JOB_TIMEOUT=300

   # SQS visibility timeout (seconds)
   SQS_VISIBILITY_TIMEOUT=900

Docker Deployment
-----------------

API Server
~~~~~~~~~~

.. code-block:: dockerfile

   FROM python:3.11-slim

   WORKDIR /app
   COPY . .

   RUN pip install poetry && poetry install --no-dev

   CMD ["poetry", "run", "uvicorn", "your_app.main:app", "--host", "0.0.0.0", "--port", "8000"]

Scheduler
~~~~~~~~~

The library provides a Dockerfile for the scheduler:

.. code-block:: bash

   docker build -f Dockerfile.scheduler -t async-jobs-scheduler .
   docker run --env-file .env async-jobs-scheduler

Worker
~~~~~~

The library provides a Dockerfile for the worker:

.. code-block:: bash

   docker build -f Dockerfile.worker -t async-jobs-worker .
   docker run --env-file .env async-jobs-worker

Docker Compose
~~~~~~~~~~~~~~

For local development:

.. code-block:: yaml

   version: '3.8'
   services:
     postgres:
       image: postgres:15
       environment:
         POSTGRES_DB: jobs
         POSTGRES_USER: jobs
         POSTGRES_PASSWORD: secret

     scheduler:
       build:
         context: .
         dockerfile: Dockerfile.scheduler
       env_file: .env
       depends_on:
         - postgres

     worker:
       build:
         context: .
         dockerfile: Dockerfile.worker
       env_file: .env
       depends_on:
         - postgres

AWS ECS Deployment
------------------

Task Definitions
~~~~~~~~~~~~~~~~

Create separate ECS task definitions for scheduler and worker:

Scheduler Task
^^^^^^^^^^^^^^

.. code-block:: json

   {
     "family": "async-jobs-scheduler",
     "taskRoleArn": "arn:aws:iam::123456789:role/ecs-task-role",
     "executionRoleArn": "arn:aws:iam::123456789:role/ecs-execution-role",
     "containerDefinitions": [{
       "name": "scheduler",
       "image": "your-registry/async-jobs-scheduler:latest",
       "environment": [
         {"name": "DATABASE_URL", "value": "postgresql://..."},
         {"name": "JOBS_QUEUE_URL", "value": "https://sqs..."}
       ],
       "logConfiguration": {
         "logDriver": "awslogs",
         "options": {
           "awslogs-group": "/ecs/async-jobs-scheduler",
           "awslogs-region": "us-east-1"
         }
       }
     }]
   }

Worker Service
^^^^^^^^^^^^^^

.. code-block:: json

   {
     "family": "async-jobs-worker",
     "taskRoleArn": "arn:aws:iam::123456789:role/ecs-task-role",
     "executionRoleArn": "arn:aws:iam::123456789:role/ecs-execution-role",
     "containerDefinitions": [{
       "name": "worker",
       "image": "your-registry/async-jobs-worker:latest",
       "environment": [
         {"name": "DATABASE_URL", "value": "postgresql://..."},
         {"name": "JOBS_QUEUE_URL", "value": "https://sqs..."},
         {"name": "WORKER_CONCURRENCY", "value": "10"}
       ]
     }]
   }

IAM Permissions
~~~~~~~~~~~~~~~

The ECS task role needs the following permissions:

.. code-block:: json

   {
     "Version": "2012-10-17",
     "Statement": [{
       "Effect": "Allow",
       "Action": [
         "sqs:ReceiveMessage",
         "sqs:DeleteMessage",
         "sqs:SendMessage",
         "sqs:GetQueueAttributes"
       ],
       "Resource": "arn:aws:sqs:us-east-1:123456789:jobs-queue"
     }]
   }

Database Setup
--------------

1. Create Database
~~~~~~~~~~~~~~~~~~

.. code-block:: sql

   CREATE DATABASE jobs_production;
   CREATE USER jobs_user WITH PASSWORD 'secure_password';
   GRANT ALL PRIVILEGES ON DATABASE jobs_production TO jobs_user;

2. Apply Schema
~~~~~~~~~~~~~~~

.. code-block:: python

   from async_jobs import JOBS_TABLE_DDL
   import asyncpg

   async def setup_database():
       conn = await asyncpg.connect(
           "postgresql://jobs_user:secure_password@host:5432/jobs_production"
       )
       await conn.execute(JOBS_TABLE_DDL)
       await conn.close()

3. Create Indexes
~~~~~~~~~~~~~~~~~

For optimal performance:

.. code-block:: sql

   -- Index for scheduler queries
   CREATE INDEX idx_jobs_schedulable ON jobs (tenant_id, status, run_after)
   WHERE status = 'pending' AND run_after <= NOW();

   -- Index for tenant quota queries
   CREATE INDEX idx_jobs_tenant_recent ON jobs (tenant_id, created_at)
   WHERE created_at >= NOW() - INTERVAL '1 hour';

Monitoring
----------

Health Checks
~~~~~~~~~~~~~

The API server exposes a health endpoint:

.. code-block:: bash

   curl http://api-server:8000/health

Metrics
~~~~~~~

Key metrics to monitor:

- Job queue depth (pending jobs)
- Job execution time (p50, p95, p99)
- Job success/failure rate
- Tenant quota utilization
- SQS queue depth and age

Logs
~~~~

All components log to stdout in JSON format for easy aggregation:

.. code-block:: python

   import logging
   logging.basicConfig(
       level=logging.INFO,
       format='{"timestamp":"%(asctime)s","level":"%(levelname)s","message":"%(message)s"}'
   )

Scaling
-------

Scheduler
~~~~~~~~~

Run a single scheduler instance (leader election not implemented).
The scheduler is lightweight and handles high throughput.

Workers
~~~~~~~

Scale workers horizontally based on:

- SQS queue depth
- Job execution time
- Desired processing latency

.. code-block:: bash

   # Auto-scale based on SQS queue depth
   # Target: <100 messages in queue
   aws application-autoscaling put-scaling-policy \
     --policy-name worker-scaling \
     --service-namespace ecs \
     --scalable-dimension ecs:service:DesiredCount \
     --target-tracking-scaling-policy-configuration \
     'TargetValue=100,PredefinedMetricSpecification={PredefinedMetricType=SQSQueueMessagesVisible}'

Troubleshooting
---------------

Jobs Not Being Scheduled
~~~~~~~~~~~~~~~~~~~~~~~~~

Check:

1. Scheduler is running
2. Jobs have ``run_after`` in the past
3. Database connectivity
4. SQS queue accessibility

Jobs Not Being Executed
~~~~~~~~~~~~~~~~~~~~~~~~

Check:

1. Workers are running
2. Job handlers are registered
3. SQS visibility timeout is sufficient
4. Job execution doesn't exceed timeout

High Job Failure Rate
~~~~~~~~~~~~~~~~~~~~~

Check:

1. Error logs for specific failures
2. Retry configuration
3. External dependencies availability
4. Resource limits (memory, CPU)
