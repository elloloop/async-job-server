"""Pytest configuration and fixtures."""

import os
from uuid import uuid4

import pytest

# Set test environment
os.environ["ASYNC_JOBS_DB_DSN"] = "postgresql://test:test@localhost:5432/test"


@pytest.fixture
def sample_job_payload():
    """Sample job payload for testing."""
    return {
        "message": "Test message",
        "recipient": "test@example.com",
        "data": {"key": "value"},
    }


@pytest.fixture
def sample_backoff_policy():
    """Sample backoff policy for testing."""
    return {"type": "exponential", "base_delay_seconds": 60, "max_delay_seconds": 3600}


@pytest.fixture
def sample_job_id():
    """Sample job ID for testing."""
    return uuid4()


@pytest.fixture
def sample_tenant_id():
    """Sample tenant ID for testing."""
    return "tenant-123"


@pytest.fixture
def sample_use_case():
    """Sample use case for testing."""
    return "notifications"
