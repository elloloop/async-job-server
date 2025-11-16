"""
Async Jobs Platform Library

A reusable library for building async job platforms with FastAPI, PostgreSQL, and SQS.
"""

__version__ = "0.1.0"

from async_jobs.config import AsyncJobsConfig
from async_jobs.errors import (
    AsyncJobsError,
    AuthTokenError,
    JobNotFoundError,
    QuotaExceededError,
    RemoteHttpError,
)
from async_jobs.models import Job, JobStatus
from async_jobs.registry import JobRegistry, job_registry
from async_jobs.service import JobService
from async_jobs.fastapi_router import create_jobs_router
from async_jobs.http_client import AsyncJobsHttpClient
from async_jobs.scheduler import run_scheduler_loop
from async_jobs.worker import run_worker_loop
from async_jobs.scheduler_main import run_scheduler
from async_jobs.worker_main import run_worker

__all__ = [
    "AsyncJobsConfig",
    "AsyncJobsError",
    "AuthTokenError",
    "Job",
    "JobNotFoundError",
    "JobRegistry",
    "JobService",
    "JobStatus",
    "QuotaExceededError",
    "RemoteHttpError",
    "AsyncJobsHttpClient",
    "create_jobs_router",
    "job_registry",
    "run_scheduler_loop",
    "run_worker_loop",
    "run_scheduler",
    "run_worker",
]
