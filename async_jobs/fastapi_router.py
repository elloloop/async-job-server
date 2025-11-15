"""FastAPI router for job API."""

from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from async_jobs.errors import AsyncJobsError, JobNotFoundError, QuotaExceededError
from async_jobs.models import EnqueueJobRequest, JobStatus
from async_jobs.service import JobService


class EnqueueRequest(BaseModel):
    """Request to enqueue a job."""

    tenant_id: str
    use_case: str
    type: str
    queue: str
    payload: dict[str, Any]
    run_at: Optional[datetime] = None
    delay_tolerance_seconds: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    backoff_policy: dict[str, Any]
    dedupe_key: Optional[str] = None
    priority: int = Field(default=0)


class EnqueueResponse(BaseModel):
    """Response from enqueuing a job."""

    job_id: UUID


class JobResponse(BaseModel):
    """Response with job details."""

    id: UUID
    tenant_id: str
    use_case: str
    type: str
    queue: str
    status: str
    payload: dict[str, Any]
    run_at: datetime
    delay_tolerance_seconds: int
    deadline_at: datetime
    priority: int
    attempts: int
    max_attempts: int
    backoff_policy: dict[str, Any]
    lease_expires_at: Optional[datetime]
    last_error: Optional[dict[str, Any]]
    dedupe_key: Optional[str]
    enqueue_failed: bool
    created_at: datetime
    updated_at: datetime


class ListJobsResponse(BaseModel):
    """Response with list of jobs."""

    jobs: list[JobResponse]


def create_jobs_router(
    job_service_factory: Callable[[], JobService],
    require_auth_token: bool = False,
    expected_auth_token: Optional[str] = None,
) -> APIRouter:
    """Create a FastAPI router for job endpoints."""
    router = APIRouter(prefix="/jobs", tags=["jobs"])

    async def get_job_service() -> JobService:
        """Dependency to get job service."""
        return job_service_factory()

    async def verify_auth_token(
        x_async_jobs_token: Optional[str] = Header(None, alias="X-Async-Jobs-Token")
    ):
        """Verify authentication token if required."""
        if require_auth_token:
            if not x_async_jobs_token:
                raise HTTPException(status_code=401, detail="Authentication token required")
            if expected_auth_token and x_async_jobs_token != expected_auth_token:
                raise HTTPException(status_code=401, detail="Invalid authentication token")

    @router.post("/enqueue", response_model=EnqueueResponse, status_code=201)
    async def enqueue_job(
        request: EnqueueRequest,
        service: JobService = Depends(get_job_service),
        _auth: None = Depends(verify_auth_token),
    ):
        """Enqueue a new job."""
        try:
            job_request = EnqueueJobRequest(
                tenant_id=request.tenant_id,
                use_case=request.use_case,
                type=request.type,
                queue=request.queue,
                payload=request.payload,
                run_at=request.run_at,
                delay_tolerance_seconds=request.delay_tolerance_seconds,
                max_attempts=request.max_attempts,
                backoff_policy=request.backoff_policy,
                dedupe_key=request.dedupe_key,
                priority=request.priority,
            )
            job_id = await service.enqueue(job_request)
            return EnqueueResponse(job_id=job_id)
        except QuotaExceededError as e:
            raise HTTPException(status_code=429, detail=str(e))
        except AsyncJobsError as e:
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/{job_id}", response_model=JobResponse)
    async def get_job(
        job_id: UUID,
        service: JobService = Depends(get_job_service),
        _auth: None = Depends(verify_auth_token),
    ):
        """Get a job by ID."""
        try:
            job = await service.get_job(job_id)
            return JobResponse(
                id=job.id,
                tenant_id=job.tenant_id,
                use_case=job.use_case,
                type=job.type,
                queue=job.queue,
                status=job.status.value,
                payload=job.payload,
                run_at=job.run_at,
                delay_tolerance_seconds=int(job.delay_tolerance.total_seconds()),
                deadline_at=job.deadline_at,
                priority=job.priority,
                attempts=job.attempts,
                max_attempts=job.max_attempts,
                backoff_policy=job.backoff_policy,
                lease_expires_at=job.lease_expires_at,
                last_error=job.last_error,
                dedupe_key=job.dedupe_key,
                enqueue_failed=job.enqueue_failed,
                created_at=job.created_at,
                updated_at=job.updated_at,
            )
        except JobNotFoundError:
            raise HTTPException(status_code=404, detail="Job not found")

    @router.get("/", response_model=ListJobsResponse)
    async def list_jobs(
        tenant_id: Optional[str] = Query(None),
        use_case: Optional[str] = Query(None),
        status: Optional[str] = Query(None),
        limit: int = Query(100, ge=1, le=1000),
        service: JobService = Depends(get_job_service),
        _auth: None = Depends(verify_auth_token),
    ):
        """List jobs with optional filters."""
        status_enum = JobStatus(status) if status else None
        jobs = await service.list_jobs(
            tenant_id=tenant_id,
            use_case=use_case,
            status=status_enum,
            limit=limit,
        )
        return ListJobsResponse(
            jobs=[
                JobResponse(
                    id=job.id,
                    tenant_id=job.tenant_id,
                    use_case=job.use_case,
                    type=job.type,
                    queue=job.queue,
                    status=job.status.value,
                    payload=job.payload,
                    run_at=job.run_at,
                    delay_tolerance_seconds=int(job.delay_tolerance.total_seconds()),
                    deadline_at=job.deadline_at,
                    priority=job.priority,
                    attempts=job.attempts,
                    max_attempts=job.max_attempts,
                    backoff_policy=job.backoff_policy,
                    lease_expires_at=job.lease_expires_at,
                    last_error=job.last_error,
                    dedupe_key=job.dedupe_key,
                    enqueue_failed=job.enqueue_failed,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                )
                for job in jobs
            ]
        )

    return router
