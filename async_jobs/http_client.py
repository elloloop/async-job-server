"""HTTP client for async jobs API."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import httpx

from async_jobs.errors import RemoteHttpError


class AsyncJobsHttpClient:
    """HTTP client for interacting with async jobs API."""

    def __init__(self, base_url: str, auth_token: Optional[str] = None):
        """Initialize the HTTP client."""
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token

    async def enqueue(
        self,
        tenant_id: str,
        use_case: str,
        type: str,
        queue: str,
        payload: dict[str, Any],
        delay_tolerance_seconds: int,
        max_attempts: int,
        backoff_policy: dict[str, Any],
        run_at: Optional[datetime] = None,
        dedupe_key: Optional[str] = None,
        priority: int = 0,
    ) -> UUID:
        """Enqueue a job via HTTP."""
        headers = {}
        if self.auth_token:
            headers["X-Async-Jobs-Token"] = self.auth_token

        data = {
            "tenant_id": tenant_id,
            "use_case": use_case,
            "type": type,
            "queue": queue,
            "payload": payload,
            "delay_tolerance_seconds": delay_tolerance_seconds,
            "max_attempts": max_attempts,
            "backoff_policy": backoff_policy,
            "priority": priority,
        }

        if run_at:
            data["run_at"] = run_at.isoformat()

        if dedupe_key:
            data["dedupe_key"] = dedupe_key

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/jobs/enqueue",
                    json=data,
                    headers=headers,
                    timeout=30.0,
                )
                response.raise_for_status()
                result = response.json()
                return UUID(result["job_id"])
        except httpx.HTTPError as e:
            raise RemoteHttpError(f"HTTP error: {e}")

    async def get_job(self, job_id: UUID) -> dict[str, Any]:
        """Get a job by ID via HTTP."""
        headers = {}
        if self.auth_token:
            headers["X-Async-Jobs-Token"] = self.auth_token

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/jobs/{job_id}",
                    headers=headers,
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            raise RemoteHttpError(f"HTTP error: {e}")

    async def list_jobs(
        self,
        tenant_id: Optional[str] = None,
        use_case: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """List jobs via HTTP."""
        headers = {}
        if self.auth_token:
            headers["X-Async-Jobs-Token"] = self.auth_token

        params = {"limit": limit}
        if tenant_id:
            params["tenant_id"] = tenant_id
        if use_case:
            params["use_case"] = use_case
        if status:
            params["status"] = status

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/jobs/",
                    params=params,
                    headers=headers,
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as e:
            raise RemoteHttpError(f"HTTP error: {e}")
