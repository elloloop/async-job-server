"""Async jobs library for FastAPI projects."""

from async_jobs.config import AsyncJobsConfig
from async_jobs.ddl import JOBS_TABLE_DDL
from async_jobs.errors import (
    AsyncJobsError,
    AuthTokenError,
    JobNotFoundError,
    QuotaExceededError,
    RemoteHttpError,
)
from async_jobs.fastapi_router import create_jobs_router
from async_jobs.http_client import AsyncJobsHttpClient
from async_jobs.models import Job, JobStatus
from async_jobs.registry import JobRegistry, job_registry
from async_jobs.scheduler import run_scheduler_loop
from async_jobs.service import JobService
from async_jobs.store import JobStore
from async_jobs.worker import run_worker_loop

__version__ = "0.1.0"

__all__ = [
    "AsyncJobsConfig",
    "JOBS_TABLE_DDL",
    "AsyncJobsError",
    "AuthTokenError",
    "JobNotFoundError",
    "QuotaExceededError",
    "RemoteHttpError",
    "create_jobs_router",
    "AsyncJobsHttpClient",
    "Job",
    "JobStatus",
    "JobRegistry",
    "job_registry",
    "run_scheduler_loop",
    "JobService",
    "JobStore",
    "run_worker_loop",
]
