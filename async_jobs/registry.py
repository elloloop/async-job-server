"""Job handler registry."""

from collections.abc import Callable


class JobRegistry:
    """Registry for job handlers."""

    def __init__(self):
        self._handlers: dict[str, Callable] = {}

    def handler(self, name: str):
        """Decorator to register a job handler.

        Args:
            name: Unique name for the job handler

        Returns:
            Decorator function that registers the handler

        Example:
            >>> registry = JobRegistry()
            >>> @registry.handler("send_notification")
            ... async def send_notification(ctx, payload):
            ...     return {"status": "sent"}
        """

        def decorator(func: Callable):
            self._handlers[name] = func
            return func

        return decorator

    def get_handler(self, name: str) -> Callable | None:
        """Get a handler by name."""
        return self._handlers.get(name)

    def all_handlers(self) -> dict[str, Callable]:
        """Get all registered handlers."""
        return self._handlers.copy()


# Global registry instance
job_registry = JobRegistry()
