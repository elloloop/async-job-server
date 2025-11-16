"""FastAPI router for async jobs HTTP API."""

from collections.abc import Callable
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from async_jobs.errors import JobNotFoundError, QuotaExceededError
from async_jobs.service import JobService


class EnqueueJobRequest(BaseModel):
    """Request model for enqueuing a job."""

    tenant_id: str = Field(..., description="Tenant identifier")
    use_case: str = Field(..., description="Use case name")
    type: str = Field(..., description="Job type")
    queue: str = Field(..., description="SQS queue name")
    payload: dict[str, Any] = Field(..., description="Job payload")
    run_at: Optional[str] = Field(None, description="ISO8601 timestamp for when to run")
    delay_tolerance_seconds: Optional[int] = Field(None, description="Delay tolerance in seconds")
    max_attempts: int = Field(5, description="Maximum retry attempts")
    backoff_policy: Optional[dict[str, Any]] = Field(None, description="Retry backoff policy")
    dedupe_key: Optional[str] = Field(None, description="Deduplication key")
    priority: int = Field(0, description="Job priority")


class EnqueueJobResponse(BaseModel):
    """Response model for enqueuing a job."""

    job_id: str = Field(..., description="Created job ID")


class JobResponse(BaseModel):
    """Response model for job information."""

    id: str
    tenant_id: str
    use_case: str
    type: str
    queue: str
    status: str
    payload: dict[str, Any]
    run_at: str
    delay_tolerance: float
    deadline_at: str
    priority: int
    attempts: int
    max_attempts: int
    backoff_policy: dict[str, Any]
    lease_expires_at: Optional[str]
    last_error: Optional[dict[str, Any]]
    dedupe_key: Optional[str]
    enqueue_failed: bool
    created_at: str
    updated_at: str


class ListJobsResponse(BaseModel):
    """Response model for listing jobs."""

    jobs: list[JobResponse]


def create_jobs_router(
    job_service_factory: Callable[[], JobService],
    auth_token: Optional[str] = None,
) -> APIRouter:
    """
    Create a FastAPI router for async jobs.

    Args:
        job_service_factory: Factory function that returns a JobService instance
        auth_token: Optional authentication token for enqueue endpoint

    Returns:
        APIRouter configured with job endpoints
    """
    router = APIRouter()

    async def verify_auth_token(x_async_jobs_token: Optional[str] = Header(None)):
        """Verify authentication token if configured."""
        if auth_token and x_async_jobs_token != auth_token:
            raise HTTPException(status_code=401, detail="Invalid or missing auth token")

    @router.post("/jobs/enqueue", response_model=EnqueueJobResponse, status_code=201)
    async def enqueue_job(
        request: EnqueueJobRequest,
        _: None = Depends(verify_auth_token),
    ) -> EnqueueJobResponse:
        """Enqueue a new job."""
        job_service = job_service_factory()

        try:
            # Parse run_at if provided
            run_at = None
            if request.run_at:
                run_at = datetime.fromisoformat(request.run_at.replace("Z", "+00:00"))

            # Convert delay_tolerance to timedelta if provided
            from datetime import timedelta

            delay_tolerance = None
            if request.delay_tolerance_seconds is not None:
                delay_tolerance = timedelta(seconds=request.delay_tolerance_seconds)

            job_id = await job_service.enqueue(
                tenant_id=request.tenant_id,
                use_case=request.use_case,
                type=request.type,
                queue=request.queue,
                payload=request.payload,
                run_at=run_at,
                delay_tolerance=delay_tolerance,
                max_attempts=request.max_attempts,
                backoff_policy=request.backoff_policy,
                dedupe_key=request.dedupe_key,
                priority=request.priority,
            )

            return EnqueueJobResponse(job_id=str(job_id))

        except QuotaExceededError as e:
            raise HTTPException(status_code=429, detail=str(e))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    @router.get("/jobs/{job_id}", response_model=JobResponse)
    async def get_job(job_id: UUID) -> JobResponse:
        """Get job information by ID."""
        job_service = job_service_factory()

        try:
            job = await job_service.get_job(job_id)
            return JobResponse(**job.to_dict())
        except JobNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    @router.get("/jobs", response_model=ListJobsResponse)
    async def list_jobs(
        tenant_id: Optional[str] = None,
        use_case: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> ListJobsResponse:
        """List jobs with optional filters."""
        job_service = job_service_factory()

        try:
            jobs = await job_service.list_jobs(
                tenant_id=tenant_id,
                use_case=use_case,
                status=status,
                limit=min(limit, 100),  # Cap at 100
            )
            job_responses = [JobResponse(**job.to_dict()) for job in jobs]
            return ListJobsResponse(jobs=job_responses)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    return router
