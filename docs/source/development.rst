Development Guide
=================

This guide covers contributing to and developing the async-jobs library.

Development Setup
-----------------

Prerequisites
~~~~~~~~~~~~~

- Python 3.11+
- Poetry
- Docker (for integration tests)
- PostgreSQL client tools

Installation
~~~~~~~~~~~~

.. code-block:: bash

   # Clone repository
   git clone https://github.com/your-org/async-job-server.git
   cd async-job-server

   # Install dependencies
   poetry install

   # Activate virtual environment
   poetry shell

Running Tests
-------------

Unit Tests
~~~~~~~~~~

.. code-block:: bash

   # Run unit tests
   poetry run pytest tests/unit/

   # Run with coverage
   poetry run pytest tests/unit/ --cov=async_jobs --cov-report=html

   # View coverage report
   open htmlcov/index.html

Integration Tests
~~~~~~~~~~~~~~~~~

Integration tests use testcontainers for PostgreSQL:

.. code-block:: bash

   # Run integration tests (requires Docker)
   poetry run pytest tests/integration/

   # Run all tests
   poetry run pytest

Code Quality
------------

Formatting
~~~~~~~~~~

The project uses Black for code formatting:

.. code-block:: bash

   # Format code
   poetry run black async_jobs tests

   # Check formatting
   poetry run black --check async_jobs tests

Linting
~~~~~~~

The project uses Ruff for linting:

.. code-block:: bash

   # Run linter
   poetry run ruff check async_jobs tests

   # Auto-fix issues
   poetry run ruff check --fix async_jobs tests

Type Checking
~~~~~~~~~~~~~

The project uses mypy for type checking:

.. code-block:: bash

   # Run type checker
   poetry run mypy async_jobs

Running Locally
---------------

Start Dependencies
~~~~~~~~~~~~~~~~~~

Use Docker Compose to start PostgreSQL and LocalStack:

.. code-block:: bash

   docker-compose up -d postgres localstack

Set Environment Variables
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   export DATABASE_URL="postgresql://jobs:jobs@localhost:5432/jobs"
   export AWS_REGION="us-east-1"
   export JOBS_QUEUE_URL="http://localhost:4566/000000000000/jobs-queue"
   export AWS_ACCESS_KEY_ID="test"
   export AWS_SECRET_ACCESS_KEY="test"
   export AWS_ENDPOINT_URL="http://localhost:4566"

Run Components
~~~~~~~~~~~~~~

.. code-block:: bash

   # Terminal 1: Run scheduler
   poetry run python -m async_jobs.scheduler_main

   # Terminal 2: Run worker
   poetry run python -m async_jobs.worker_main

   # Terminal 3: Run example API server
   poetry run uvicorn examples.main:app --reload

Building Documentation
----------------------

The project uses Sphinx for documentation:

.. code-block:: bash

   # Install documentation dependencies
   poetry install --with dev

   # Build HTML documentation
   cd docs
   make html

   # View documentation
   open build/html/index.html

   # Clean build artifacts
   make clean

Live documentation server:

.. code-block:: bash

   # Install sphinx-autobuild
   poetry add --group dev sphinx-autobuild

   # Run live server
   cd docs
   sphinx-autobuild source build/html

   # Open http://localhost:8000

Project Structure
-----------------

.. code-block:: text

   async-job-server/
   ├── async_jobs/           # Main library code
   │   ├── __init__.py       # Public API exports
   │   ├── config.py         # Configuration management
   │   ├── models.py         # Pydantic models
   │   ├── service.py        # Job service logic
   │   ├── store.py          # Database operations
   │   ├── registry.py       # Job handler registry
   │   ├── fastapi_router.py # FastAPI router
   │   ├── http_client.py    # HTTP client
   │   ├── scheduler.py      # Scheduler logic
   │   ├── worker.py         # Worker logic
   │   ├── scheduler_main.py # Scheduler entrypoint
   │   ├── worker_main.py    # Worker entrypoint
   │   ├── ddl.py            # Database schema
   │   ├── errors.py         # Exception classes
   │   └── handlers/         # Example job handlers
   │       ├── messaging.py
   │       └── notifications.py
   ├── tests/                # Test suite
   │   ├── unit/             # Unit tests
   │   └── integration/      # Integration tests
   ├── examples/             # Example applications
   ├── docs/                 # Documentation
   ├── pyproject.toml        # Project configuration
   └── docker-compose.yml    # Local dev environment

Contributing
------------

Pull Request Process
~~~~~~~~~~~~~~~~~~~~

1. Fork the repository
2. Create a feature branch (``git checkout -b feature/amazing-feature``)
3. Make your changes
4. Run tests and linting
5. Commit your changes (``git commit -m 'Add amazing feature'``)
6. Push to the branch (``git push origin feature/amazing-feature``)
7. Open a Pull Request

Code Style Guidelines
~~~~~~~~~~~~~~~~~~~~~

- Follow PEP 8 (enforced by Black and Ruff)
- Use type hints for all function signatures
- Write docstrings for all public APIs (Google style)
- Keep functions focused and testable
- Prefer composition over inheritance
- Use async/await consistently

Documentation Guidelines
~~~~~~~~~~~~~~~~~~~~~~~~

- Document all public APIs with docstrings
- Include usage examples in docstrings
- Update user guide for new features
- Add integration tests for new features
- Update changelog

Docstring Format
~~~~~~~~~~~~~~~~

Use Google-style docstrings:

.. code-block:: python

   async def enqueue_job(
       self,
       tenant_id: str,
       job_type: str,
       job_data: dict,
       run_after: datetime | None = None,
       run_before: datetime | None = None,
   ) -> Job:
       """Enqueue a new job for asynchronous execution.

       Args:
           tenant_id: Unique identifier for the tenant
           job_type: Type of job to execute (must be registered)
           job_data: Job-specific data payload
           run_after: Earliest time to execute (default: now)
           run_before: Latest acceptable execution time (deadline)

       Returns:
           The created Job instance

       Raises:
           QuotaExceededError: If tenant has exceeded hourly quota
           ValueError: If job_type is not registered

       Example:
           >>> service = JobService(config)
           >>> job = await service.enqueue_job(
           ...     tenant_id="tenant_123",
           ...     job_type="send_email",
           ...     job_data={"to": "user@example.com"},
           ... )
       """
       pass

Release Process
---------------

1. Update version in ``pyproject.toml`` and ``async_jobs/__init__.py``
2. Update changelog
3. Create and push tag:

   .. code-block:: bash

      git tag -a v0.2.0 -m "Release v0.2.0"
      git push origin v0.2.0

4. GitHub Actions will build and publish to PyPI

Debugging
---------

Enable Debug Logging
~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   export LOG_LEVEL=DEBUG
   poetry run python -m async_jobs.worker_main

Use Python Debugger
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   import pdb; pdb.set_trace()

Database Queries
~~~~~~~~~~~~~~~~

Log all SQL queries:

.. code-block:: python

   import logging
   logging.getLogger('asyncpg').setLevel(logging.DEBUG)

Common Issues
-------------

Import Errors
~~~~~~~~~~~~~

Make sure you're in the Poetry shell:

.. code-block:: bash

   poetry shell

Database Connection Errors
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Check PostgreSQL is running:

.. code-block:: bash

   docker-compose ps postgres

SQS Connection Errors
~~~~~~~~~~~~~~~~~~~~~

For local development, ensure LocalStack is running:

.. code-block:: bash

   docker-compose ps localstack
