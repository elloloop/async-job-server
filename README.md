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

## Documentation

📚 **[View Full Documentation](https://elloloop.github.io/async-job-server/)** (GitHub Pages)

Comprehensive documentation is available including:

- **Quick Start Guide**: Get up and running quickly
- **User Guide**: Detailed usage instructions and examples
- **API Reference**: Auto-generated from source code docstrings
- **Deployment Guide**: Production deployment on AWS ECS
- **Development Guide**: Contributing and local development

### Building Documentation Locally

```bash
# Install dependencies
poetry install --with dev

# Build HTML documentation
cd docs
make html

# View documentation
open build/html/index.html  # macOS
xdg-open build/html/index.html  # Linux
```

The documentation is automatically built and deployed to GitHub Pages on every push to the main branch.

## Quick Start

See the [Quick Start Guide](https://elloloop.github.io/async-job-server/quickstart.html) in the full documentation.

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
