"""Errors for the async jobs library."""


class AsyncJobsError(Exception):
    """Base exception for all async jobs errors."""

    pass


class QuotaExceededError(AsyncJobsError):
    """Raised when a tenant exceeds their job quota."""

    pass


class JobNotFoundError(AsyncJobsError):
    """Raised when a job is not found."""

    pass


class AuthTokenError(AsyncJobsError):
    """Raised when authentication fails."""

    pass


class RemoteHttpError(AsyncJobsError):
    """Raised when a remote HTTP call fails."""

    pass
