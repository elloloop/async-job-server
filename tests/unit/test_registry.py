"""Unit tests for registry module."""

import pytest

from async_jobs.registry import JobRegistry, job_registry


def test_registry_handler_decorator():
    """Test registering a handler with decorator."""
    registry = JobRegistry()

    @registry.handler("test_handler")
    async def test_handler(ctx, payload):
        return "result"

    handler = registry.get_handler("test_handler")
    assert handler is not None
    assert handler == test_handler


def test_registry_register_programmatically():
    """Test registering a handler programmatically."""
    registry = JobRegistry()

    async def test_handler(ctx, payload):
        return "result"

    registry.register("test_handler", test_handler)

    handler = registry.get_handler("test_handler")
    assert handler == test_handler


def test_registry_get_handler_not_found():
    """Test getting a non-existent handler returns None."""
    registry = JobRegistry()

    handler = registry.get_handler("nonexistent")
    assert handler is None


def test_registry_all_handlers():
    """Test getting all handlers."""
    registry = JobRegistry()

    @registry.handler("handler1")
    async def handler1(ctx, payload):
        pass

    @registry.handler("handler2")
    async def handler2(ctx, payload):
        pass

    all_handlers = registry.all_handlers()
    assert len(all_handlers) == 2
    assert "handler1" in all_handlers
    assert "handler2" in all_handlers


def test_global_registry():
    """Test that global registry instance exists."""
    assert job_registry is not None
    assert isinstance(job_registry, JobRegistry)
