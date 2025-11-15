"""Job handler registry."""
from typing import Any, Callable, Dict

from async_jobs.models import JobContext


JobHandler = Callable[[JobContext, Dict[str, Any]], Any]


class JobRegistry:
    """Registry for job handlers."""

    def __init__(self):
        """Initialize the registry."""
        self._handlers: Dict[str, JobHandler] = {}

    def handler(self, job_type: str):
        """Decorator to register a job handler."""

        def decorator(func: JobHandler):
            self._handlers[job_type] = func
            return func

        return decorator

    def get_handler(self, job_type: str) -> JobHandler:
        """Get a handler for a job type."""
        handler = self._handlers.get(job_type)
        if not handler:
            raise ValueError(f"No handler registered for job type: {job_type}")
        return handler

    def has_handler(self, job_type: str) -> bool:
        """Check if a handler is registered for a job type."""
        return job_type in self._handlers


# Global registry instance
job_registry = JobRegistry()
