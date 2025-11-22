"""Unit tests for configuration module."""

import json

import pytest

from async_jobs.config import AsyncJobsConfig


def test_config_from_env_minimal(monkeypatch):
    """Test creating config from minimal environment variables."""
    monkeypatch.setenv("ASYNC_JOBS_DB_DSN", "postgresql://localhost/test")
    monkeypatch.setenv(
        "ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS",
        "https://sqs.us-east-1.amazonaws.com/123/notifications",
    )
    monkeypatch.setenv(
        "ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING", "https://sqs.us-east-1.amazonaws.com/123/labeling"
    )

    config = AsyncJobsConfig.from_env()

    assert config.db_dsn == "postgresql://localhost/test"
    assert config.sqs_queue_notifications == "https://sqs.us-east-1.amazonaws.com/123/notifications"
    assert config.sqs_queue_message_labeling == "https://sqs.us-east-1.amazonaws.com/123/labeling"
    assert config.notifications_max_concurrent == 10  # default
    assert config.notifications_default_delay_tolerance_seconds == 300  # default


def test_config_from_env_with_overrides(monkeypatch):
    """Test creating config with all environment variables."""
    monkeypatch.setenv("ASYNC_JOBS_DB_DSN", "postgresql://localhost/test")
    monkeypatch.setenv(
        "ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS",
        "https://sqs.us-east-1.amazonaws.com/123/notifications",
    )
    monkeypatch.setenv(
        "ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING", "https://sqs.us-east-1.amazonaws.com/123/labeling"
    )
    monkeypatch.setenv("ASYNC_JOBS_NOTIFICATIONS_MAX_CONCURRENT", "20")
    monkeypatch.setenv("ASYNC_JOBS_NOTIFICATIONS_DEFAULT_DELAY_TOLERANCE_SECONDS", "600")
    monkeypatch.setenv("ASYNC_JOBS_MESSAGE_LABELING_MAX_CONCURRENT", "15")
    monkeypatch.setenv("ASYNC_JOBS_MESSAGE_LABELING_DEFAULT_DELAY_TOLERANCE_SECONDS", "900")
    monkeypatch.setenv("ASYNC_JOBS_ENQUEUE_AUTH_TOKEN", "secret123")

    config = AsyncJobsConfig.from_env()

    assert config.notifications_max_concurrent == 20
    assert config.notifications_default_delay_tolerance_seconds == 600
    assert config.message_labeling_max_concurrent == 15
    assert config.message_labeling_default_delay_tolerance_seconds == 900
    assert config.enqueue_auth_token == "secret123"


def test_config_from_env_with_tenant_quotas(monkeypatch):
    """Test creating config with per-tenant quotas."""
    monkeypatch.setenv("ASYNC_JOBS_DB_DSN", "postgresql://localhost/test")
    monkeypatch.setenv(
        "ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS",
        "https://sqs.us-east-1.amazonaws.com/123/notifications",
    )
    monkeypatch.setenv(
        "ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING", "https://sqs.us-east-1.amazonaws.com/123/labeling"
    )

    quotas = {
        "tenant1": {"notifications": 100, "message_labeling": 50},
        "tenant2": {"notifications": 200},
    }
    monkeypatch.setenv("ASYNC_JOBS_PER_TENANT_QUOTAS", json.dumps(quotas))

    config = AsyncJobsConfig.from_env()

    assert config.get_tenant_quota("tenant1", "notifications") == 100
    assert config.get_tenant_quota("tenant1", "message_labeling") == 50
    assert config.get_tenant_quota("tenant2", "notifications") == 200
    assert config.get_tenant_quota("tenant2", "message_labeling") is None
    assert config.get_tenant_quota("tenant3", "notifications") is None


def test_config_from_env_missing_required(monkeypatch):
    """Test that missing required env vars raise ValueError."""
    with pytest.raises(ValueError, match="ASYNC_JOBS_DB_DSN"):
        AsyncJobsConfig.from_env()

    monkeypatch.setenv("ASYNC_JOBS_DB_DSN", "postgresql://localhost/test")
    with pytest.raises(ValueError, match="ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS"):
        AsyncJobsConfig.from_env()


def test_config_get_use_case_config():
    """Test getting use case configuration."""
    config = AsyncJobsConfig(
        db_dsn="postgresql://localhost/test",
        sqs_queue_notifications="https://sqs.us-east-1.amazonaws.com/123/notifications",
        sqs_queue_message_labeling="https://sqs.us-east-1.amazonaws.com/123/labeling",
        notifications_max_concurrent=10,
        notifications_default_delay_tolerance_seconds=300,
        message_labeling_max_concurrent=5,
        message_labeling_default_delay_tolerance_seconds=600,
    )

    notifications_config = config.get_use_case_config("notifications")
    assert notifications_config is not None
    assert notifications_config["max_concurrent"] == 10
    assert notifications_config["default_delay_tolerance_seconds"] == 300

    missing_config = config.get_use_case_config("nonexistent")
    assert missing_config is None
