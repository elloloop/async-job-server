# Async Jobs Library

A reusable async job platform library for FastAPI projects with PostgreSQL job store, SQS transport, and ECS-friendly scheduler/worker processes.

## Features

- **FastAPI Integration**: Drop-in router for job enqueueing endpoints
- **PostgreSQL Job Store**: Reliable job persistence with deadline-based scheduling
- **SQS Transport**: AWS SQS for job message queuing
- **Multi-tenant**: Built-in tenant isolation and quota enforcement
- **Deadline-based Scheduling**: Meta-style delay tolerance for flexible job execution
- **ECS Ready**: Environment-based configuration and graceful shutdown
- **Retry Logic**: Configurable backoff strategies (exponential, linear, constant)
- **Job Registry**: Decorator-based handler registration

## Quick Start

See full documentation in this README for setup instructions, API reference, and examples.

## Testing

Run tests:

```bash
# Unit tests
poetry run pytest tests/unit/

# Integration tests (requires Docker for testcontainers)
poetry run pytest tests/integration/

# All tests with coverage
poetry run pytest --cov=async_jobs --cov-report=html
```

## License

Internal use only.
