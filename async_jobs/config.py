"""Configuration management for async jobs."""

import json
import os
from typing import Any, Dict, Optional


class AsyncJobsConfig:
    """Configuration for async jobs system."""

    def __init__(
        self,
        db_dsn: str,
        sqs_queue_notifications: str,
        sqs_queue_message_labeling: str,
        notifications_max_concurrent: int,
        notifications_default_delay_tolerance_seconds: int,
        message_labeling_max_concurrent: int,
        message_labeling_default_delay_tolerance_seconds: int,
        enqueue_auth_token: Optional[str] = None,
        per_use_case_config: Optional[Dict[str, Any]] = None,
        per_tenant_quotas: Optional[Dict[str, Dict[str, int]]] = None,
    ):
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
        """Create configuration from environment variables."""
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

    def get_use_case_config(self, use_case: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific use case."""
        return self.per_use_case_config.get(use_case)

    def get_tenant_quota(self, tenant_id: str, use_case: str) -> Optional[int]:
        """Get quota for a specific tenant and use case."""
        if tenant_id in self.per_tenant_quotas:
            return self.per_tenant_quotas[tenant_id].get(use_case)
        return None
