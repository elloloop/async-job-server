"""Configuration for async jobs platform."""

import json
import os
from typing import Any, Dict, Optional


class AsyncJobsConfig:
    """Configuration object for async jobs."""

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
        self.per_use_case_config = per_use_case_config or {}
        self.per_tenant_quotas = per_tenant_quotas or {}

        # Map use_case to queue URL
        self.use_case_to_queue: Dict[str, str] = {
            "notifications": self.sqs_queue_notifications,
            "message_labeling": self.sqs_queue_message_labeling,
        }

    @classmethod
    def from_env(cls) -> "AsyncJobsConfig":
        """Create config from environment variables."""
        db_dsn = os.getenv("ASYNC_JOBS_DB_DSN")
        if not db_dsn:
            raise ValueError("ASYNC_JOBS_DB_DSN environment variable is required")

        sqs_queue_notifications = os.getenv("ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS")
        if not sqs_queue_notifications:
            raise ValueError(
                "ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS environment variable is required"
            )

        sqs_queue_message_labeling = os.getenv(
            "ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING"
        )
        if not sqs_queue_message_labeling:
            raise ValueError(
                "ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING environment variable is required"
            )

        notifications_max_concurrent = int(
            os.getenv("ASYNC_JOBS_NOTIFICATIONS_MAX_CONCURRENT", "10")
        )
        notifications_default_delay_tolerance_seconds = int(
            os.getenv(
                "ASYNC_JOBS_NOTIFICATIONS_DEFAULT_DELAY_TOLERANCE_SECONDS", "3"
            )
        )

        message_labeling_max_concurrent = int(
            os.getenv("ASYNC_JOBS_MESSAGE_LABELING_MAX_CONCURRENT", "10")
        )
        message_labeling_default_delay_tolerance_seconds = int(
            os.getenv(
                "ASYNC_JOBS_MESSAGE_LABELING_DEFAULT_DELAY_TOLERANCE_SECONDS", "3"
            )
        )

        enqueue_auth_token = os.getenv("ASYNC_JOBS_ENQUEUE_AUTH_TOKEN")

        per_tenant_quotas_str = os.getenv("ASYNC_JOBS_PER_TENANT_QUOTAS")
        per_tenant_quotas = None
        if per_tenant_quotas_str:
            try:
                per_tenant_quotas = json.loads(per_tenant_quotas_str)
            except json.JSONDecodeError as e:
                raise ValueError(
                    f"Invalid JSON in ASYNC_JOBS_PER_TENANT_QUOTAS: {e}"
                ) from e

        # Build per_use_case_config from env vars
        per_use_case_config = {
            "notifications": {
                "max_concurrent": notifications_max_concurrent,
                "default_delay_tolerance_seconds": (
                    notifications_default_delay_tolerance_seconds
                ),
            },
            "message_labeling": {
                "max_concurrent": message_labeling_max_concurrent,
                "default_delay_tolerance_seconds": (
                    message_labeling_default_delay_tolerance_seconds
                ),
            },
        }

        return cls(
            db_dsn=db_dsn,
            sqs_queue_notifications=sqs_queue_notifications,
            sqs_queue_message_labeling=sqs_queue_message_labeling,
            notifications_max_concurrent=notifications_max_concurrent,
            notifications_default_delay_tolerance_seconds=(
                notifications_default_delay_tolerance_seconds
            ),
            message_labeling_max_concurrent=message_labeling_max_concurrent,
            message_labeling_default_delay_tolerance_seconds=(
                message_labeling_default_delay_tolerance_seconds
            ),
            enqueue_auth_token=enqueue_auth_token,
            per_use_case_config=per_use_case_config,
            per_tenant_quotas=per_tenant_quotas,
        )

    def get_queue_url_for_use_case(self, use_case: str) -> Optional[str]:
        """Get SQS queue URL for a use case."""
        return self.use_case_to_queue.get(use_case)

    def get_max_concurrent_for_use_case(self, use_case: str) -> int:
        """Get max concurrent jobs for a use case."""
        config = self.per_use_case_config.get(use_case, {})
        return config.get("max_concurrent", 10)

    def get_default_delay_tolerance_seconds_for_use_case(
        self, use_case: str
    ) -> int:
        """Get default delay tolerance in seconds for a use case."""
        config = self.per_use_case_config.get(use_case, {})
        return config.get("default_delay_tolerance_seconds", 3)

    def get_quota_for_tenant_use_case(
        self, tenant_id: str, use_case: str
    ) -> Optional[int]:
        """Get quota limit for a tenant and use case combination."""
        tenant_quotas = self.per_tenant_quotas.get(tenant_id, {})
        return tenant_quotas.get(use_case)
