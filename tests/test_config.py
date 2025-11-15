"""Test configuration."""

import os
from unittest.mock import patch

import pytest

from async_jobs.config import AsyncJobsConfig, TenantQuota, UseCaseConfig


def test_use_case_config():
    """Test UseCaseConfig creation."""
    config = UseCaseConfig(
        max_concurrent=10,
        default_delay_tolerance_seconds=60,
        sqs_queue="https://sqs.us-east-1.amazonaws.com/123456789/my-queue",
    )
    assert config.max_concurrent == 10
    assert config.default_delay_tolerance_seconds == 60
    assert "my-queue" in config.sqs_queue


def test_tenant_quota():
    """Test TenantQuota creation."""
    quota = TenantQuota(max_pending_jobs=100)
    assert quota.max_pending_jobs == 100


def test_from_env_minimal():
    """Test loading minimal configuration from environment."""
    env = {
        "ASYNC_JOBS_DB_DSN": "postgresql://localhost/test",
    }
    with patch.dict(os.environ, env, clear=True):
        config = AsyncJobsConfig.from_env()
        assert config.db_dsn == "postgresql://localhost/test"
        assert len(config.use_case_configs) == 0
        assert len(config.per_tenant_quotas) == 0
        assert config.enqueue_auth_token is None


def test_from_env_with_use_cases():
    """Test loading configuration with use cases."""
    env = {
        "ASYNC_JOBS_DB_DSN": "postgresql://localhost/test",
        "ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS": "https://sqs.us-east-1.amazonaws.com/123/notifications",
        "ASYNC_JOBS_NOTIFICATIONS_MAX_CONCURRENT": "20",
        "ASYNC_JOBS_NOTIFICATIONS_DEFAULT_DELAY_TOLERANCE_SECONDS": "120",
        "ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING": "https://sqs.us-east-1.amazonaws.com/123/message_labeling",
        "ASYNC_JOBS_MESSAGE_LABELING_MAX_CONCURRENT": "15",
        "ASYNC_JOBS_MESSAGE_LABELING_DEFAULT_DELAY_TOLERANCE_SECONDS": "90",
    }
    with patch.dict(os.environ, env, clear=True):
        config = AsyncJobsConfig.from_env()
        assert len(config.use_case_configs) == 2
        assert "notifications" in config.use_case_configs
        assert config.use_case_configs["notifications"].max_concurrent == 20
        assert config.use_case_configs["notifications"].default_delay_tolerance_seconds == 120
        assert "message_labeling" in config.use_case_configs
        assert config.use_case_configs["message_labeling"].max_concurrent == 15


def test_from_env_with_quotas():
    """Test loading configuration with per-tenant quotas."""
    env = {
        "ASYNC_JOBS_DB_DSN": "postgresql://localhost/test",
        "ASYNC_JOBS_PER_TENANT_QUOTAS": (
            '{"tenant1": {"max_pending_jobs": 50}, '
            '"tenant2": {"max_pending_jobs": 100}}'
        ),
    }
    with patch.dict(os.environ, env, clear=True):
        config = AsyncJobsConfig.from_env()
        assert len(config.per_tenant_quotas) == 2
        assert config.per_tenant_quotas["tenant1"].max_pending_jobs == 50
        assert config.per_tenant_quotas["tenant2"].max_pending_jobs == 100


def test_from_env_with_auth_token():
    """Test loading configuration with auth token."""
    env = {
        "ASYNC_JOBS_DB_DSN": "postgresql://localhost/test",
        "ASYNC_JOBS_ENQUEUE_AUTH_TOKEN": "secret-token-123",
    }
    with patch.dict(os.environ, env, clear=True):
        config = AsyncJobsConfig.from_env()
        assert config.enqueue_auth_token == "secret-token-123"


def test_from_env_with_timing_configs():
    """Test loading configuration with timing parameters."""
    env = {
        "ASYNC_JOBS_DB_DSN": "postgresql://localhost/test",
        "ASYNC_JOBS_SCHEDULER_INTERVAL_SECONDS": "10",
        "ASYNC_JOBS_WORKER_POLL_INTERVAL_SECONDS": "2",
        "ASYNC_JOBS_WORKER_VISIBILITY_TIMEOUT_SECONDS": "600",
        "ASYNC_JOBS_LEASE_DURATION_SECONDS": "600",
    }
    with patch.dict(os.environ, env, clear=True):
        config = AsyncJobsConfig.from_env()
        assert config.scheduler_interval_seconds == 10
        assert config.worker_poll_interval_seconds == 2
        assert config.worker_visibility_timeout_seconds == 600
        assert config.lease_duration_seconds == 600


def test_from_env_missing_dsn():
    """Test that missing DSN raises an error."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="ASYNC_JOBS_DB_DSN"):
            AsyncJobsConfig.from_env()
