"""Custom exceptions for async jobs library."""


class AsyncJobsError(Exception):
    """Base exception for async jobs library."""

    pass


class QuotaExceededError(AsyncJobsError):
    """Raised when a tenant exceeds their quota for a use case."""

    pass


class JobNotFoundError(AsyncJobsError):
    """Raised when a job is not found in the database."""

    pass


class AuthTokenError(AsyncJobsError):
    """Raised when authentication token is invalid or missing."""

    pass


class RemoteHttpError(AsyncJobsError):
    """Raised when HTTP client encounters an error."""

    pass
