"""Exception types for the async jobs library."""


class AsyncJobsError(Exception):
    """Base exception for all async jobs errors."""

    pass


class QuotaExceededError(AsyncJobsError):
    """Raised when a tenant's quota for a use case is exceeded."""

    def __init__(self, tenant_id: str, use_case: str, message: str = None):
        self.tenant_id = tenant_id
        self.use_case = use_case
        if message is None:
            message = f"Quota exceeded for tenant {tenant_id} and use_case {use_case}"
        super().__init__(message)


class JobNotFoundError(AsyncJobsError):
    """Raised when a job is not found."""

    def __init__(self, job_id: str, message: str = None):
        self.job_id = job_id
        if message is None:
            message = f"Job {job_id} not found"
        super().__init__(message)


class AuthTokenError(AsyncJobsError):
    """Raised when authentication token is missing or invalid."""

    pass


class RemoteHttpError(AsyncJobsError):
    """Raised when an HTTP request to a remote async jobs service fails."""

    def __init__(self, status_code: int, message: str, response_body: str = None):
        self.status_code = status_code
        self.response_body = response_body
        super().__init__(f"HTTP {status_code}: {message}")
