"""Test errors."""


from async_jobs.errors import (
    AsyncJobsError,
    AuthTokenError,
    JobNotFoundError,
    QuotaExceededError,
    RemoteHttpError,
)


def test_async_jobs_error():
    """Test base AsyncJobsError."""
    error = AsyncJobsError("Test error")
    assert str(error) == "Test error"
    assert isinstance(error, Exception)


def test_quota_exceeded_error():
    """Test QuotaExceededError."""
    error = QuotaExceededError("Quota exceeded")
    assert str(error) == "Quota exceeded"
    assert isinstance(error, AsyncJobsError)


def test_job_not_found_error():
    """Test JobNotFoundError."""
    error = JobNotFoundError("Job not found")
    assert str(error) == "Job not found"
    assert isinstance(error, AsyncJobsError)


def test_auth_token_error():
    """Test AuthTokenError."""
    error = AuthTokenError("Invalid token")
    assert str(error) == "Invalid token"
    assert isinstance(error, AsyncJobsError)


def test_remote_http_error():
    """Test RemoteHttpError."""
    error = RemoteHttpError("HTTP request failed")
    assert str(error) == "HTTP request failed"
    assert isinstance(error, AsyncJobsError)
