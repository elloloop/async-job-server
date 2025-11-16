"""HTTP client for async jobs service."""

from typing import Any, Dict, Optional
from uuid import UUID

import httpx

from async_jobs.errors import RemoteHttpError


class AsyncJobsHttpClient:
    """HTTP client for calling async jobs service."""

    def __init__(
        self,
        base_url: str,
        auth_token: Optional[str] = None,
        timeout: float = 5.0,
    ):
        """
        Initialize HTTP client.

        Args:
            base_url: Base URL of the async jobs service
            auth_token: Optional authentication token
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = timeout

    async def enqueue(
        self,
        *,
        tenant_id: str,
        use_case: str,
        type: str,
        queue: str,
        payload: Dict[str, Any],
        run_at: Optional[str] = None,
        delay_tolerance_seconds: Optional[int] = None,
        max_attempts: int = 5,
        backoff_policy: Optional[Dict[str, Any]] = None,
        dedupe_key: Optional[str] = None,
        priority: int = 0,
    ) -> UUID:
        """
        Enqueue a job via HTTP.

        Args:
            tenant_id: Tenant identifier
            use_case: Use case name
            type: Job type
            queue: SQS queue name
            payload: Job payload
            run_at: Optional ISO8601 timestamp
            delay_tolerance_seconds: Optional delay tolerance in seconds
            max_attempts: Maximum retry attempts
            backoff_policy: Retry backoff policy
            dedupe_key: Optional deduplication key
            priority: Job priority

        Returns:
            UUID: The created job ID

        Raises:
            RemoteHttpError: If the HTTP request fails
        """
        url = f"{self.base_url}/jobs/enqueue"

        headers = {}
        if self.auth_token:
            headers["X-Async-Jobs-Token"] = self.auth_token

        request_body = {
            "tenant_id": tenant_id,
            "use_case": use_case,
            "type": type,
            "queue": queue,
            "payload": payload,
            "max_attempts": max_attempts,
            "priority": priority,
        }

        if run_at is not None:
            request_body["run_at"] = run_at

        if delay_tolerance_seconds is not None:
            request_body["delay_tolerance_seconds"] = delay_tolerance_seconds

        if backoff_policy is not None:
            request_body["backoff_policy"] = backoff_policy

        if dedupe_key is not None:
            request_body["dedupe_key"] = dedupe_key

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=request_body, headers=headers)
                response.raise_for_status()
                data = response.json()
                return UUID(data["job_id"])
        except httpx.HTTPStatusError as e:
            raise RemoteHttpError(
                f"HTTP {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise RemoteHttpError(f"Request failed: {str(e)}") from e
        except (KeyError, ValueError) as e:
            raise RemoteHttpError(f"Invalid response format: {str(e)}") from e

    async def get_job(self, job_id: UUID) -> Dict[str, Any]:
        """
        Get job information by ID.

        Args:
            job_id: Job UUID

        Returns:
            Dict containing job information

        Raises:
            RemoteHttpError: If the HTTP request fails
        """
        url = f"{self.base_url}/jobs/{job_id}"

        headers = {}
        if self.auth_token:
            headers["X-Async-Jobs-Token"] = self.auth_token

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            raise RemoteHttpError(
                f"HTTP {e.response.status_code}: {e.response.text}"
            ) from e
        except httpx.RequestError as e:
            raise RemoteHttpError(f"Request failed: {str(e)}") from e
