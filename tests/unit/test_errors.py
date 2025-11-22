"""Unit tests for errors module."""


from async_jobs.errors import (
    AsyncJobsError,
    AuthTokenError,
    JobNotFoundError,
    QuotaExceededError,
    RemoteHttpError,
)


def test_async_jobs_error_base_class():
    """Test base exception class."""
    error = AsyncJobsError("Test error")
    assert str(error) == "Test error"
    assert isinstance(error, Exception)


def test_quota_exceeded_error():
    """Test QuotaExceededError."""
    error = QuotaExceededError("Quota exceeded for tenant1")
    assert isinstance(error, AsyncJobsError)
    assert str(error) == "Quota exceeded for tenant1"


def test_job_not_found_error():
    """Test JobNotFoundError."""
    error = JobNotFoundError("Job abc123 not found")
    assert isinstance(error, AsyncJobsError)
    assert str(error) == "Job abc123 not found"


def test_auth_token_error():
    """Test AuthTokenError."""
    error = AuthTokenError("Invalid token")
    assert isinstance(error, AsyncJobsError)
    assert str(error) == "Invalid token"


def test_remote_http_error():
    """Test RemoteHttpError."""
    error = RemoteHttpError("HTTP 500: Internal Server Error")
    assert isinstance(error, AsyncJobsError)
    assert str(error) == "HTTP 500: Internal Server Error"


def test_error_inheritance():
    """Test that all custom errors inherit from AsyncJobsError."""
    assert issubclass(QuotaExceededError, AsyncJobsError)
    assert issubclass(JobNotFoundError, AsyncJobsError)
    assert issubclass(AuthTokenError, AsyncJobsError)
    assert issubclass(RemoteHttpError, AsyncJobsError)


def test_errors_can_be_caught_as_base():
    """Test that custom errors can be caught as AsyncJobsError."""
    try:
        raise QuotaExceededError("Test")
    except AsyncJobsError as e:
        assert isinstance(e, QuotaExceededError)

    try:
        raise JobNotFoundError("Test")
    except AsyncJobsError as e:
        assert isinstance(e, JobNotFoundError)

    try:
        raise AuthTokenError("Test")
    except AsyncJobsError as e:
        assert isinstance(e, AuthTokenError)

    try:
        raise RemoteHttpError("Test")
    except AsyncJobsError as e:
        assert isinstance(e, RemoteHttpError)
