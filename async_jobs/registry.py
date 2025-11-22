"""Job handler registry."""

from collections.abc import Callable
from typing import Optional


class JobRegistry:
    """Registry for job handlers."""

    def __init__(self):
        self._handlers: dict[str, Callable] = {}

    def handler(self, name: str):
        """
        Decorator to register a job handler.

        Usage:
            @registry.handler("send_notification")
            async def send_notification(ctx, payload):
                ...
        """

        def decorator(func: Callable):
            self._handlers[name] = func
            return func

        return decorator

    def get_handler(self, name: str) -> Optional[Callable]:
        """Get a handler by name."""
        return self._handlers.get(name)

    def all_handlers(self) -> dict[str, Callable]:
        """Get all registered handlers."""
        return self._handlers.copy()


# Global registry instance
job_registry = JobRegistry()
