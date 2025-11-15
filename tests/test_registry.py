"""Test registry."""

import pytest

from async_jobs.models import JobContext
from async_jobs.registry import JobRegistry, job_registry


def test_job_registry_creation():
    """Test creating a new JobRegistry."""
    registry = JobRegistry()
    assert registry is not None
    assert len(registry._handlers) == 0


def test_job_registry_handler_decorator():
    """Test registering a handler with decorator."""
    registry = JobRegistry()

    @registry.handler("test_job")
    async def test_handler(ctx, payload):
        return "test"

    assert registry.has_handler("test_job")
    handler = registry.get_handler("test_job")
    assert handler == test_handler


def test_job_registry_get_nonexistent_handler():
    """Test getting a handler that doesn't exist."""
    registry = JobRegistry()
    with pytest.raises(ValueError, match="No handler registered"):
        registry.get_handler("nonexistent")


def test_job_registry_has_handler():
    """Test checking if a handler exists."""
    registry = JobRegistry()

    @registry.handler("existing_job")
    async def existing_handler(ctx, payload):
        pass

    assert registry.has_handler("existing_job")
    assert not registry.has_handler("nonexistent_job")


@pytest.mark.asyncio
async def test_job_handler_execution():
    """Test executing a registered handler."""
    registry = JobRegistry()

    @registry.handler("echo_job")
    async def echo_handler(ctx, payload):
        return {"echoed": payload}

    handler = registry.get_handler("echo_job")
    from uuid import uuid4

    context = JobContext(
        job_id=uuid4(),
        tenant_id="tenant1",
        use_case="test",
        type="echo_job",
        attempt=1,
    )
    result = await handler(context, {"message": "hello"})
    assert result == {"echoed": {"message": "hello"}}


def test_global_registry():
    """Test that global registry is available."""
    assert job_registry is not None
    assert isinstance(job_registry, JobRegistry)
