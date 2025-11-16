"""Unit tests for errors module."""

from async_jobs.errors import (
    AsyncJobsError,
    AuthTokenError,
    JobNotFoundError,
    QuotaExceededError,
    RemoteHttpError,
)


def test_async_jobs_error_base():
    """Test base error class."""
    error = AsyncJobsError("test message")
    assert str(error) == "test message"


def test_quota_exceeded_error():
    """Test QuotaExceededError."""
    error = QuotaExceededError("tenant1", "notifications")
    assert error.tenant_id == "tenant1"
    assert error.use_case == "notifications"
    assert "tenant1" in str(error)
    assert "notifications" in str(error)


def test_job_not_found_error():
    """Test JobNotFoundError."""
    error = JobNotFoundError("123e4567-e89b-12d3-a456-426614174000")
    assert error.job_id == "123e4567-e89b-12d3-a456-426614174000"
    assert "123e4567-e89b-12d3-a456-426614174000" in str(error)


def test_auth_token_error():
    """Test AuthTokenError."""
    error = AuthTokenError("Invalid token")
    assert str(error) == "Invalid token"


def test_remote_http_error():
    """Test RemoteHttpError."""
    error = RemoteHttpError(404, "Not found", '{"error": "details"}')
    assert error.status_code == 404
    assert error.response_body == '{"error": "details"}'
    assert "404" in str(error)
