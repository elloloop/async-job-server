"""Unit tests for config module."""

import os
import pytest

from async_jobs.config import AsyncJobsConfig


def test_config_from_env_minimal():
    """Test creating config from minimal env vars."""
    os.environ["ASYNC_JOBS_DB_DSN"] = "postgresql://user:pass@localhost/db"
    os.environ["ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS"] = "https://sqs.us-east-1.amazonaws.com/123/notifications"
    os.environ["ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING"] = "https://sqs.us-east-1.amazonaws.com/123/labeling"

    config = AsyncJobsConfig.from_env()

    assert config.db_dsn == "postgresql://user:pass@localhost/db"
    assert config.sqs_queue_notifications == "https://sqs.us-east-1.amazonaws.com/123/notifications"
    assert config.sqs_queue_message_labeling == "https://sqs.us-east-1.amazonaws.com/123/labeling"
    assert config.notifications_max_concurrent == 10  # default
    assert config.message_labeling_max_concurrent == 10  # default


def test_config_from_env_with_all_vars():
    """Test creating config with all env vars set."""
    os.environ["ASYNC_JOBS_DB_DSN"] = "postgresql://user:pass@localhost/db"
    os.environ["ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS"] = "https://sqs.us-east-1.amazonaws.com/123/notifications"
    os.environ["ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING"] = "https://sqs.us-east-1.amazonaws.com/123/labeling"
    os.environ["ASYNC_JOBS_NOTIFICATIONS_MAX_CONCURRENT"] = "20"
    os.environ["ASYNC_JOBS_NOTIFICATIONS_DEFAULT_DELAY_TOLERANCE_SECONDS"] = "5"
    os.environ["ASYNC_JOBS_MESSAGE_LABELING_MAX_CONCURRENT"] = "15"
    os.environ["ASYNC_JOBS_MESSAGE_LABELING_DEFAULT_DELAY_TOLERANCE_SECONDS"] = "10"
    os.environ["ASYNC_JOBS_ENQUEUE_AUTH_TOKEN"] = "secret-token"
    os.environ["ASYNC_JOBS_PER_TENANT_QUOTAS"] = '{"tenant1": {"notifications": 100}}'

    config = AsyncJobsConfig.from_env()

    assert config.notifications_max_concurrent == 20
    assert config.notifications_default_delay_tolerance_seconds == 5
    assert config.message_labeling_max_concurrent == 15
    assert config.message_labeling_default_delay_tolerance_seconds == 10
    assert config.enqueue_auth_token == "secret-token"
    assert config.per_tenant_quotas == {"tenant1": {"notifications": 100}}


def test_config_missing_required_var():
    """Test that missing required env var raises error."""
    if "ASYNC_JOBS_DB_DSN" in os.environ:
        del os.environ["ASYNC_JOBS_DB_DSN"]

    with pytest.raises(ValueError, match="ASYNC_JOBS_DB_DSN"):
        AsyncJobsConfig.from_env()


def test_config_get_queue_url_for_use_case():
    """Test getting queue URL for use case."""
    os.environ["ASYNC_JOBS_DB_DSN"] = "postgresql://user:pass@localhost/db"
    os.environ["ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS"] = "https://sqs.us-east-1.amazonaws.com/123/notifications"
    os.environ["ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING"] = "https://sqs.us-east-1.amazonaws.com/123/labeling"

    config = AsyncJobsConfig.from_env()

    assert config.get_queue_url_for_use_case("notifications") == "https://sqs.us-east-1.amazonaws.com/123/notifications"
    assert config.get_queue_url_for_use_case("message_labeling") == "https://sqs.us-east-1.amazonaws.com/123/labeling"
    assert config.get_queue_url_for_use_case("unknown") is None


def test_config_get_quota_for_tenant_use_case():
    """Test getting quota for tenant and use case."""
    os.environ["ASYNC_JOBS_DB_DSN"] = "postgresql://user:pass@localhost/db"
    os.environ["ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS"] = "https://sqs.us-east-1.amazonaws.com/123/notifications"
    os.environ["ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING"] = "https://sqs.us-east-1.amazonaws.com/123/labeling"
    os.environ["ASYNC_JOBS_PER_TENANT_QUOTAS"] = '{"tenant1": {"notifications": 100, "message_labeling": 50}}'

    config = AsyncJobsConfig.from_env()

    assert config.get_quota_for_tenant_use_case("tenant1", "notifications") == 100
    assert config.get_quota_for_tenant_use_case("tenant1", "message_labeling") == 50
    assert config.get_quota_for_tenant_use_case("tenant1", "unknown") is None
    assert config.get_quota_for_tenant_use_case("tenant2", "notifications") is None
