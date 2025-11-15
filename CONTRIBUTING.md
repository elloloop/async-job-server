# Contributing to Async Jobs

## Development Setup

### Prerequisites

- Python 3.9 or higher
- PostgreSQL 12 or higher
- Docker and Docker Compose (for local testing)
- AWS CLI (for SQS setup)

### Initial Setup

1. Clone the repository:
```bash
git clone https://github.com/elloloop/async-job-server.git
cd async-job-server
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e ".[dev,test]"
```

4. Start local services:
```bash
docker-compose up -d
```

5. Set up environment:
```bash
cp .env.local .env
source .env  # On Windows: set -a; . .env; set +a
```

6. Initialize database:
```bash
async-jobs-scheduler --init-db
# Press Ctrl+C after initialization
```

## Development Workflow

### Running Tests

Run all tests:
```bash
pytest tests/ -v
```

Run with coverage:
```bash
pytest tests/ --cov=async_jobs --cov-report=html
```

Run specific test file:
```bash
pytest tests/test_config.py -v
```

### Code Formatting

Format code with Black:
```bash
black async_jobs/ tests/ examples/
```

### Linting

Run Ruff linter:
```bash
ruff check async_jobs/ tests/ examples/
```

Fix auto-fixable issues:
```bash
ruff check async_jobs/ tests/ examples/ --fix
```

### Type Checking

Run mypy:
```bash
mypy async_jobs/
```

## Project Structure

```
async-job-server/
├── async_jobs/           # Main library code
│   ├── __init__.py
│   ├── config.py         # Configuration management
│   ├── ddl.py            # Database schema
│   ├── errors.py         # Custom exceptions
│   ├── models.py         # Data models
│   ├── store.py          # Database access layer
│   ├── service.py        # Business logic
│   ├── registry.py       # Handler registration
│   ├── scheduler.py      # Scheduler loop
│   ├── worker.py         # Worker loop
│   ├── scheduler_main.py # Scheduler CLI
│   ├── worker_main.py    # Worker CLI
│   ├── fastapi_router.py # FastAPI endpoints
│   ├── http_client.py    # HTTP client
│   └── handlers/         # Example handlers
│       ├── notifications.py
│       └── messaging.py
├── tests/                # Unit tests
├── examples/             # Example applications
├── docs/                 # Documentation
└── pyproject.toml        # Project configuration
```

## Making Changes

### Adding a New Feature

1. Create a feature branch:
```bash
git checkout -b feature/your-feature-name
```

2. Write tests first (TDD approach):
```bash
# Add tests to tests/test_*.py
pytest tests/test_your_feature.py -v
```

3. Implement the feature

4. Ensure all tests pass:
```bash
pytest tests/ -v
```

5. Format and lint:
```bash
black async_jobs/ tests/
ruff check async_jobs/ tests/ --fix
```

6. Commit changes:
```bash
git add .
git commit -m "feat: add your feature description"
```

7. Push and create pull request:
```bash
git push origin feature/your-feature-name
```

### Fixing a Bug

1. Create a bug fix branch:
```bash
git checkout -b fix/bug-description
```

2. Write a failing test that reproduces the bug

3. Fix the bug

4. Ensure the test now passes

5. Follow steps 4-7 from "Adding a New Feature"

## Commit Message Convention

Use conventional commits format:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Adding or updating tests
- `refactor:` Code refactoring
- `style:` Code style changes (formatting)
- `chore:` Maintenance tasks

Examples:
```
feat: add support for priority-based scheduling
fix: resolve race condition in job leasing
docs: update README with deployment instructions
test: add integration tests for worker
```

## Testing Guidelines

### Unit Tests

- Test individual functions and methods
- Mock external dependencies (database, SQS)
- Use pytest fixtures for common setup
- Aim for >80% code coverage

### Integration Tests

- Test complete workflows
- Use docker-compose for services
- Test against real PostgreSQL and LocalStack
- Clean up test data after each test

### Example Test

```python
import pytest
from async_jobs import JobService, JobStore, AsyncJobsConfig

@pytest.mark.asyncio
async def test_enqueue_job(db_pool):
    """Test enqueueing a job."""
    config = AsyncJobsConfig.from_env()
    store = JobStore(db_pool)
    service = JobService(config, store)
    
    job_id = await service.enqueue(
        EnqueueJobRequest(
            tenant_id="test",
            use_case="notifications",
            type="send_email",
            queue="notifications",
            payload={"to": "test@example.com"},
            delay_tolerance_seconds=60,
            max_attempts=3,
            backoff_policy={"type": "exponential"},
        )
    )
    
    assert job_id is not None
    job = await service.get_job(job_id)
    assert job.status == JobStatus.PENDING
```

## Documentation

### Docstrings

Use Google-style docstrings:

```python
def function_name(param1: str, param2: int) -> bool:
    """Short description of function.

    Longer description if needed.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When param1 is invalid
    """
    pass
```

### README Updates

When adding features that affect usage:
1. Update README.md with examples
2. Update API documentation
3. Add configuration details if needed

## Release Process

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md
3. Create a release tag:
```bash
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

## Questions?

Contact the infrastructure team or open an issue for discussion.
