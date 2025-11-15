"""Async jobs library for job scheduling and execution."""

__version__ = "0.1.0"

from async_jobs.config import AsyncJobsConfig, TenantQuota, UseCaseConfig
from async_jobs.errors import (
    AsyncJobsError,
    AuthTokenError,
    JobNotFoundError,
    QuotaExceededError,
    RemoteHttpError,
)
from async_jobs.fastapi_router import create_jobs_router
from async_jobs.http_client import AsyncJobsHttpClient
from async_jobs.models import EnqueueJobRequest, Job, JobContext, JobStatus
from async_jobs.registry import JobRegistry, job_registry
from async_jobs.service import JobService
from async_jobs.store import JobStore

__all__ = [
    # Version
    "__version__",
    # Config
    "AsyncJobsConfig",
    "UseCaseConfig",
    "TenantQuota",
    # Errors
    "AsyncJobsError",
    "QuotaExceededError",
    "JobNotFoundError",
    "AuthTokenError",
    "RemoteHttpError",
    # Models
    "Job",
    "JobStatus",
    "JobContext",
    "EnqueueJobRequest",
    # Core components
    "JobStore",
    "JobService",
    "JobRegistry",
    "job_registry",
    # FastAPI
    "create_jobs_router",
    # HTTP Client
    "AsyncJobsHttpClient",
]
