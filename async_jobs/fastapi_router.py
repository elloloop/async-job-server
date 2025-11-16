"""FastAPI router for async jobs HTTP API."""

import logging
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from async_jobs.errors import AuthTokenError, JobNotFoundError, QuotaExceededError
from async_jobs.service import JobService


logger = logging.getLogger(__name__)


class EnqueueJobRequest(BaseModel):
    """Request model for enqueueing a job."""

    tenant_id: str
    use_case: str
    type: str
    queue: str
    payload: Dict[str, Any]
    run_at: Optional[str] = None  # ISO8601 datetime string
    delay_tolerance_seconds: Optional[int] = None
    max_attempts: int = 5
    backoff_policy: Optional[Dict[str, Any]] = None
    dedupe_key: Optional[str] = None


class EnqueueJobResponse(BaseModel):
    """Response model for enqueueing a job."""

    job_id: str


class JobResponse(BaseModel):
    """Response model for job details."""

    id: str
    tenant_id: str
    use_case: str
    type: str
    queue: str
    status: str
    payload: Dict[str, Any]
    run_at: Optional[str] = None
    delay_tolerance: Optional[str] = None
    deadline_at: Optional[str] = None
    priority: int
    attempts: int
    max_attempts: int
    backoff_policy: Dict[str, Any]
    lease_expires_at: Optional[str] = None
    last_error: Optional[Dict[str, Any]] = None
    dedupe_key: Optional[str] = None
    enqueue_failed: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


def create_jobs_router(
    job_service_factory: Callable[[], JobService],
    auth_token: Optional[str] = None,
) -> APIRouter:
    """
    Create FastAPI router for async jobs API.

    Args:
        job_service_factory: Callable that returns a JobService instance
        auth_token: Optional auth token for enqueue endpoint

    Returns:
        APIRouter instance
    """
    router = APIRouter()

    async def get_job_service() -> JobService:
        """Dependency to get JobService instance."""
        return job_service_factory()

    async def verify_auth_token(
        x_async_jobs_token: Optional[str] = Header(None, alias="X-Async-Jobs-Token")
    ) -> None:
        """Verify auth token if configured."""
        if auth_token:
            if not x_async_jobs_token or x_async_jobs_token != auth_token:
                raise HTTPException(
                    status_code=401, detail="Invalid or missing auth token"
                )

    @router.post("/jobs/enqueue", response_model=EnqueueJobResponse)
    async def enqueue_job(
        request: EnqueueJobRequest,
        job_service: JobService = Depends(get_job_service),
        _: None = Depends(verify_auth_token),
    ):
        """Enqueue a new job."""
        try:
            from datetime import datetime

            run_at = None
            if request.run_at:
                try:
                    run_at = datetime.fromisoformat(
                        request.run_at.replace("Z", "+00:00")
                    )
                except ValueError as e:
                    raise HTTPException(
                        status_code=400, detail=f"Invalid run_at format: {e}"
                    ) from e

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
            )

            return EnqueueJobResponse(job_id=str(job_id))

        except QuotaExceededError as e:
            raise HTTPException(status_code=429, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            logger.exception("Error enqueueing job")
            raise HTTPException(status_code=500, detail="Internal server error") from e

    @router.get("/jobs/{job_id}", response_model=JobResponse)
    async def get_job(
        job_id: str,
        job_service: JobService = Depends(get_job_service),
    ):
        """Get job details by ID."""
        try:
            job_uuid = UUID(job_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid job ID format") from e

        try:
            job = await job_service.get_job(job_uuid)
            return JobResponse(**job.to_dict())
        except JobNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except Exception as e:
            logger.exception("Error getting job")
            raise HTTPException(status_code=500, detail="Internal server error") from e

    @router.get("/jobs", response_model=List[JobResponse])
    async def list_jobs(
        tenant_id: Optional[str] = Query(None),
        use_case: Optional[str] = Query(None),
        status: Optional[str] = Query(None),
        limit: int = Query(50, ge=1, le=1000),
        job_service: JobService = Depends(get_job_service),
    ):
        """List jobs with optional filters."""
        try:
            jobs = await job_service.list_jobs(
                tenant_id=tenant_id,
                use_case=use_case,
                status=status,
                limit=limit,
            )
            return [JobResponse(**job.to_dict()) for job in jobs]
        except Exception as e:
            logger.exception("Error listing jobs")
            raise HTTPException(status_code=500, detail="Internal server error") from e

    return router
