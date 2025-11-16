"""Unit tests for registry module."""

import pytest

from async_jobs.registry import JobRegistry


@pytest.mark.asyncio
async def test_registry_handler_decorator():
    """Test registering handlers with decorator."""
    registry = JobRegistry()

    @registry.handler("test_handler")
    async def test_handler(ctx, payload):
        return {"result": "success"}

    handler = registry.get_handler("test_handler")
    assert handler is not None

    result = await handler({}, {})
    assert result == {"result": "success"}


@pytest.mark.asyncio
async def test_registry_multiple_handlers():
    """Test registering multiple handlers."""
    registry = JobRegistry()

    @registry.handler("handler1")
    async def handler1(ctx, payload):
        return "handler1"

    @registry.handler("handler2")
    async def handler2(ctx, payload):
        return "handler2"

    assert registry.get_handler("handler1") is not None
    assert registry.get_handler("handler2") is not None

    result1 = await registry.get_handler("handler1")({}, {})
    result2 = await registry.get_handler("handler2")({}, {})

    assert result1 == "handler1"
    assert result2 == "handler2"


def test_registry_get_nonexistent_handler():
    """Test getting a handler that doesn't exist."""
    registry = JobRegistry()

    handler = registry.get_handler("nonexistent")
    assert handler is None


def test_registry_all_handlers():
    """Test getting all registered handlers."""
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


def test_registry_handler_overwrites():
    """Test that registering same name overwrites."""
    registry = JobRegistry()

    @registry.handler("test")
    async def handler1(ctx, payload):
        return "first"

    @registry.handler("test")
    async def handler2(ctx, payload):
        return "second"

    handler = registry.get_handler("test")
    # The second handler should overwrite the first
    assert handler == handler2
