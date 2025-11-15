"""Configuration management for async jobs."""

import json
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class UseCaseConfig:
    """Configuration for a specific use case."""

    max_concurrent: int
    default_delay_tolerance_seconds: int
    sqs_queue: str


@dataclass
class TenantQuota:
    """Per-tenant quota configuration."""

    max_pending_jobs: int


@dataclass
class AsyncJobsConfig:
    """Main configuration for async jobs."""

    db_dsn: str
    use_case_configs: dict[str, UseCaseConfig]
    per_tenant_quotas: dict[str, TenantQuota]
    enqueue_auth_token: Optional[str] = None
    scheduler_interval_seconds: int = 5
    worker_poll_interval_seconds: int = 1
    worker_visibility_timeout_seconds: int = 300
    lease_duration_seconds: int = 300

    @classmethod
    def from_env(cls) -> "AsyncJobsConfig":
        """Load configuration from environment variables."""
        db_dsn = os.getenv("ASYNC_JOBS_DB_DSN")
        if not db_dsn:
            raise ValueError("ASYNC_JOBS_DB_DSN environment variable is required")

        # Load use case configs
        use_case_configs = {}

        # Notifications use case
        notifications_queue = os.getenv("ASYNC_JOBS_SQS_QUEUE_NOTIFICATIONS")
        notifications_max_concurrent = int(
            os.getenv("ASYNC_JOBS_NOTIFICATIONS_MAX_CONCURRENT", "10")
        )
        notifications_default_delay = int(
            os.getenv("ASYNC_JOBS_NOTIFICATIONS_DEFAULT_DELAY_TOLERANCE_SECONDS", "60")
        )
        if notifications_queue:
            use_case_configs["notifications"] = UseCaseConfig(
                max_concurrent=notifications_max_concurrent,
                default_delay_tolerance_seconds=notifications_default_delay,
                sqs_queue=notifications_queue,
            )

        # Message labeling use case
        message_labeling_queue = os.getenv("ASYNC_JOBS_SQS_QUEUE_MESSAGE_LABELING")
        message_labeling_max_concurrent = int(
            os.getenv("ASYNC_JOBS_MESSAGE_LABELING_MAX_CONCURRENT", "10")
        )
        message_labeling_default_delay = int(
            os.getenv("ASYNC_JOBS_MESSAGE_LABELING_DEFAULT_DELAY_TOLERANCE_SECONDS", "60")
        )
        if message_labeling_queue:
            use_case_configs["message_labeling"] = UseCaseConfig(
                max_concurrent=message_labeling_max_concurrent,
                default_delay_tolerance_seconds=message_labeling_default_delay,
                sqs_queue=message_labeling_queue,
            )

        # Load per-tenant quotas
        per_tenant_quotas = {}
        quotas_json = os.getenv("ASYNC_JOBS_PER_TENANT_QUOTAS")
        if quotas_json:
            quotas_data = json.loads(quotas_json)
            for tenant_id, quota_data in quotas_data.items():
                per_tenant_quotas[tenant_id] = TenantQuota(
                    max_pending_jobs=quota_data["max_pending_jobs"]
                )

        # Optional auth token
        enqueue_auth_token = os.getenv("ASYNC_JOBS_ENQUEUE_AUTH_TOKEN")

        # Optional timing configs
        scheduler_interval = int(os.getenv("ASYNC_JOBS_SCHEDULER_INTERVAL_SECONDS", "5"))
        worker_poll_interval = int(os.getenv("ASYNC_JOBS_WORKER_POLL_INTERVAL_SECONDS", "1"))
        worker_visibility_timeout = int(
            os.getenv("ASYNC_JOBS_WORKER_VISIBILITY_TIMEOUT_SECONDS", "300")
        )
        lease_duration = int(os.getenv("ASYNC_JOBS_LEASE_DURATION_SECONDS", "300"))

        return cls(
            db_dsn=db_dsn,
            use_case_configs=use_case_configs,
            per_tenant_quotas=per_tenant_quotas,
            enqueue_auth_token=enqueue_auth_token,
            scheduler_interval_seconds=scheduler_interval,
            worker_poll_interval_seconds=worker_poll_interval,
            worker_visibility_timeout_seconds=worker_visibility_timeout,
            lease_duration_seconds=lease_duration,
        )
