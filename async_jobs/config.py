"""Configuration management for async jobs."""

import json
import os
from typing import Any


class AsyncJobsConfig:
    """Configuration for async jobs system.

    This class manages all configuration settings for the async jobs library,
    including database connections, SQS queues, concurrency limits, and
    tenant-specific quotas.

    Attributes:
        db_dsn: PostgreSQL database connection string
        sqs_queue_notifications: SQS queue URL for notification jobs
        sqs_queue_message_labeling: SQS queue URL for message labeling jobs
        notifications_max_concurrent: Maximum concurrent notification jobs
        notifications_default_delay_tolerance_seconds: Default delay tolerance for notifications
        message_labeling_max_concurrent: Maximum concurrent message labeling jobs
        message_labeling_default_delay_tolerance_seconds: Default delay tolerance for labeling
        enqueue_auth_token: Optional authentication token for enqueue endpoint
        per_use_case_config: Custom configuration per use case
        per_tenant_quotas: Quota limits per tenant and use case
    """

    def __init__(
        self,
        db_dsn: str,
        sqs_queue_notifications: str,
        sqs_queue_message_labeling: str,
        notifications_max_concurrent: int,
        notifications_default_delay_tolerance_seconds: int,
        message_labeling_max_concurrent: int,
        message_labeling_default_delay_tolerance_seconds: int,
        enqueue_auth_token: str | None = None,
        per_use_case_config: dict[str, Any] | None = None,
        per_tenant_quotas: dict[str, dict[str, int]] | None = None,
    ):
        """Initialize async jobs configuration.

        Args:
            db_dsn: PostgreSQL database DSN (e.g., postgresql://user:pass@host/db)
            sqs_queue_notifications: SQS queue URL for notification jobs
            sqs_queue_message_labeling: SQS queue URL for message labeling jobs
            notifications_max_concurrent: Max concurrent notification workers
            notifications_default_delay_tolerance_seconds: Default delay tolerance for notifications (seconds)
            message_labeling_max_concurrent: Max concurrent message labeling workers
            message_labeling_default_delay_tolerance_seconds: Default delay tolerance for labeling (seconds)
            enqueue_auth_token: Optional bearer token for API authentication
            per_use_case_config: Override default config per use case
            per_tenant_quotas: Quota limits per tenant {"tenant_id": {"use_case": limit}}

        Example:
            >>> config = AsyncJobsConfig(
            ...     db_dsn="postgresql://user:pass@localhost/db",
            ...     sqs_queue_notifications="https://sqs.us-east-1.amazonaws.com/123/notifications",
            ...     sqs_queue_message_labeling="https://sqs.us-east-1.amazonaws.com/123/labeling",
            ...     notifications_max_concurrent=10,
            ...     notifications_default_delay_tolerance_seconds=300,
            ...     message_labeling_max_concurrent=5,
            ...     message_labeling_default_delay_tolerance_seconds=600,
            ... )
        """
        self.db_dsn = db_dsn
        self.sqs_queue_notifications = sqs_queue_notifications
        self.sqs_queue_message_labeling = sqs_queue_message_labeling
        self.notifications_max_concurrent = notifications_max_concurrent
        self.notifications_default_delay_tolerance_seconds = (
            notifications_default_delay_tolerance_seconds
        )
        self.message_labeling_max_concurrent = message_labeling_max_concurrent
        self.message_labeling_default_delay_tolerance_seconds = (
            message_labeling_default_delay_tolerance_seconds
        )
        self.enqueue_auth_token = enqueue_auth_token
        self.per_use_case_config = per_use_case_config or {
            "notifications": {
                "queue": sqs_queue_notifications,
                "max_concurrent": notifications_max_concurrent,
                "default_delay_tolerance_seconds": notifications_default_delay_tolerance_seconds,
            },
            "message_labeling": {
                "queue": sqs_queue_message_labeling,
                "max_concurrent": message_labeling_max_concurrent,
                "default_delay_tolerance_seconds": message_labeling_default_delay_tolerance_seconds,
            },
        }
        self.per_tenant_quotas = per_tenant_quotas or {}

    @classmethod
    def from_env(cls) -> "AsyncJobsConfig":
        """Create configuration from environment variables.

        Required environment variables:
            ASYNC_JOBS_DB_DSN: PostgreSQL connection string
            ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS: SQS queue URL for notifications
            ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING: SQS queue URL for message labeling

        Optional environment variables:
            ASYNC_JOBS_NOTIFICATIONS_MAX_CONCURRENT: Max concurrent notification workers (default: 10)
            ASYNC_JOBS_NOTIFICATIONS_DEFAULT_DELAY_TOLERANCE_SECONDS: Default delay (default: 300)
            ASYNC_JOBS_MESSAGE_LABELING_MAX_CONCURRENT: Max concurrent labeling workers (default: 5)
            ASYNC_JOBS_MESSAGE_LABELING_DEFAULT_DELAY_TOLERANCE_SECONDS: Default delay (default: 600)
            ASYNC_JOBS_ENQUEUE_AUTH_TOKEN: API authentication token
            ASYNC_JOBS_PER_TENANT_QUOTAS: JSON dict of tenant quotas

        Returns:
            AsyncJobsConfig instance configured from environment

        Raises:
            ValueError: If required environment variables are missing or invalid

        Example:
            >>> import os
            >>> os.environ['ASYNC_JOBS_DB_DSN'] = 'postgresql://localhost/db'
            >>> os.environ['ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS'] = 'https://sqs...'
            >>> os.environ['ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING'] = 'https://sqs...'
            >>> config = AsyncJobsConfig.from_env()
        """
        db_dsn = os.getenv("ASYNC_JOBS_DB_DSN")
        if not db_dsn:
            raise ValueError("ASYNC_JOBS_DB_DSN environment variable is required")

        sqs_queue_notifications = os.getenv("ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS")
        if not sqs_queue_notifications:
            raise ValueError("ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS environment variable is required")

        sqs_queue_message_labeling = os.getenv("ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING")
        if not sqs_queue_message_labeling:
            raise ValueError(
                "ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING environment variable is required"
            )

        notifications_max_concurrent = int(
            os.getenv("ASYNC_JOBS_NOTIFICATIONS_MAX_CONCURRENT", "10")
        )
        notifications_default_delay_tolerance_seconds = int(
            os.getenv("ASYNC_JOBS_NOTIFICATIONS_DEFAULT_DELAY_TOLERANCE_SECONDS", "300")
        )
        message_labeling_max_concurrent = int(
            os.getenv("ASYNC_JOBS_MESSAGE_LABELING_MAX_CONCURRENT", "5")
        )
        message_labeling_default_delay_tolerance_seconds = int(
            os.getenv("ASYNC_JOBS_MESSAGE_LABELING_DEFAULT_DELAY_TOLERANCE_SECONDS", "600")
        )

        enqueue_auth_token = os.getenv("ASYNC_JOBS_ENQUEUE_AUTH_TOKEN")

        # Parse per-tenant quotas from JSON if provided
        per_tenant_quotas = None
        quotas_json = os.getenv("ASYNC_JOBS_PER_TENANT_QUOTAS")
        if quotas_json:
            try:
                per_tenant_quotas = json.loads(quotas_json)
            except json.JSONDecodeError:
                raise ValueError("ASYNC_JOBS_PER_TENANT_QUOTAS must be valid JSON")

        return cls(
            db_dsn=db_dsn,
            sqs_queue_notifications=sqs_queue_notifications,
            sqs_queue_message_labeling=sqs_queue_message_labeling,
            notifications_max_concurrent=notifications_max_concurrent,
            notifications_default_delay_tolerance_seconds=notifications_default_delay_tolerance_seconds,
            message_labeling_max_concurrent=message_labeling_max_concurrent,
            message_labeling_default_delay_tolerance_seconds=message_labeling_default_delay_tolerance_seconds,
            enqueue_auth_token=enqueue_auth_token,
            per_tenant_quotas=per_tenant_quotas,
        )

    def get_use_case_config(self, use_case: str) -> dict[str, Any] | None:
        """Get configuration for a specific use case.

        Args:
            use_case: Name of the use case (e.g., "notifications", "message_labeling")

        Returns:
            Dictionary containing use case configuration with keys: queue, max_concurrent,
            default_delay_tolerance_seconds. Returns None if use case not found.

        Example:
            >>> config = AsyncJobsConfig.from_env()
            >>> notifications_config = config.get_use_case_config("notifications")
            >>> print(notifications_config["max_concurrent"])
            10
        """
        return self.per_use_case_config.get(use_case)

    def get_tenant_quota(self, tenant_id: str, use_case: str) -> int | None:
        """Get quota limit for a specific tenant and use case.

        Args:
            tenant_id: Unique identifier for the tenant
            use_case: Name of the use case (e.g., "notifications")

        Returns:
            Maximum number of pending jobs allowed for this tenant/use case combination.
            Returns None if no quota configured (unlimited).

        Example:
            >>> config.per_tenant_quotas = {"tenant_123": {"notifications": 100}}
            >>> quota = config.get_tenant_quota("tenant_123", "notifications")
            >>> print(quota)
            100
        """
        if tenant_id in self.per_tenant_quotas:
            return self.per_tenant_quotas[tenant_id].get(use_case)
        return None
