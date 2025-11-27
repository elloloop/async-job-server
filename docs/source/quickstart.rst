Quick Start
===========

Installation
------------

Install the library using Poetry:

.. code-block:: bash

   poetry add async-jobs

Or using pip:

.. code-block:: bash

   pip install async-jobs

Basic Usage
-----------

1. Set Up Job Handlers
~~~~~~~~~~~~~~~~~~~~~~~

Define your job handlers using the decorator pattern:

.. code-block:: python

   from async_jobs import job_registry

   @job_registry.register("send_email")
   async def send_email_handler(job_data: dict) -> dict:
       """Send an email notification."""
       recipient = job_data["recipient"]
       subject = job_data["subject"]
       # ... send email logic
       return {"status": "sent", "recipient": recipient}

2. Integrate with FastAPI
~~~~~~~~~~~~~~~~~~~~~~~~~~

Add the jobs router to your FastAPI application:

.. code-block:: python

   from fastapi import FastAPI
   from async_jobs import create_jobs_router, AsyncJobsConfig

   app = FastAPI()

   # Create configuration
   config = AsyncJobsConfig()

   # Add jobs router
   jobs_router = create_jobs_router(config)
   app.include_router(jobs_router, prefix="/jobs", tags=["jobs"])

3. Run Scheduler and Worker
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Start the scheduler process:

.. code-block:: bash

   poetry run python -m async_jobs.scheduler_main

Start the worker process:

.. code-block:: bash

   poetry run python -m async_jobs.worker_main

Configuration
-------------

Configure the library using environment variables:

.. code-block:: bash

   # Database
   export DATABASE_URL="postgresql://user:pass@localhost/db"

   # AWS SQS
   export AWS_REGION="us-east-1"
   export JOBS_QUEUE_URL="https://sqs.us-east-1.amazonaws.com/..."

   # Tenant quotas (jobs per hour)
   export TENANT_JOB_QUOTA="100"

Next Steps
----------

- Read the :doc:`user_guide` for detailed usage instructions
- Check the :doc:`api_reference` for complete API documentation
- See :doc:`deployment` for production deployment guidance
