"""HTTP client for async jobs service."""

import json
from typing import Any, Dict, List, Optional
from uuid import UUID

import aiohttp

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
            base_url: Base URL of the async jobs service (e.g., "https://async-jobs.internal")
            auth_token: Optional auth token for X-Async-Jobs-Token header
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def enqueue(
        self,
        *,
        tenant_id: str,
        use_case: str,
        type: str,
        queue: str,
        payload: Dict[str, Any],
        run_at: Optional[str] = None,  # ISO8601 string
        delay_tolerance_seconds: Optional[int] = None,
        max_attempts: int = 5,
        backoff_policy: Optional[Dict[str, Any]] = None,
        dedupe_key: Optional[str] = None,
    ) -> UUID:
        """
        Enqueue a job via HTTP API.

        Returns:
            Job ID (UUID)

        Raises:
            RemoteHttpError: If the HTTP request fails
        """
        url = f"{self.base_url}/jobs/enqueue"

        request_body = {
            "tenant_id": tenant_id,
            "use_case": use_case,
            "type": type,
            "queue": queue,
            "payload": payload,
            "max_attempts": max_attempts,
        }

        if run_at:
            request_body["run_at"] = run_at
        if delay_tolerance_seconds is not None:
            request_body["delay_tolerance_seconds"] = delay_tolerance_seconds
        if backoff_policy:
            request_body["backoff_policy"] = backoff_policy
        if dedupe_key:
            request_body["dedupe_key"] = dedupe_key

        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["X-Async-Jobs-Token"] = self.auth_token

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.post(url, json=request_body, headers=headers) as resp:
                    response_body = await resp.text()

                    if resp.status >= 400:
                        raise RemoteHttpError(
                            status_code=resp.status,
                            message=f"Failed to enqueue job: {response_body}",
                            response_body=response_body,
                        )

                    response_data = await resp.json()
                    return UUID(response_data["job_id"])

            except aiohttp.ClientError as e:
                raise RemoteHttpError(
                    status_code=0,
                    message=f"Network error: {str(e)}",
                ) from e

    async def get_job(self, job_id: UUID) -> Dict[str, Any]:
        """
        Get job details by ID.

        Returns:
            Job data as dictionary

        Raises:
            RemoteHttpError: If the HTTP request fails
        """
        url = f"{self.base_url}/jobs/{job_id}"

        headers = {}
        if self.auth_token:
            headers["X-Async-Jobs-Token"] = self.auth_token

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.get(url, headers=headers) as resp:
                    response_body = await resp.text()

                    if resp.status == 404:
                        raise RemoteHttpError(
                            status_code=404,
                            message="Job not found",
                            response_body=response_body,
                        )

                    if resp.status >= 400:
                        raise RemoteHttpError(
                            status_code=resp.status,
                            message=f"Failed to get job: {response_body}",
                            response_body=response_body,
                        )

                    return await resp.json()

            except aiohttp.ClientError as e:
                raise RemoteHttpError(
                    status_code=0,
                    message=f"Network error: {str(e)}",
                ) from e

    async def list_jobs(
        self,
        *,
        tenant_id: Optional[str] = None,
        use_case: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        List jobs with optional filters.

        Returns:
            List of job dictionaries

        Raises:
            RemoteHttpError: If the HTTP request fails
        """
        url = f"{self.base_url}/jobs"

        params = {"limit": limit}
        if tenant_id:
            params["tenant_id"] = tenant_id
        if use_case:
            params["use_case"] = use_case
        if status:
            params["status"] = status

        headers = {}
        if self.auth_token:
            headers["X-Async-Jobs-Token"] = self.auth_token

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.get(url, params=params, headers=headers) as resp:
                    response_body = await resp.text()

                    if resp.status >= 400:
                        raise RemoteHttpError(
                            status_code=resp.status,
                            message=f"Failed to list jobs: {response_body}",
                            response_body=response_body,
                        )

                    return await resp.json()

            except aiohttp.ClientError as e:
                raise RemoteHttpError(
                    status_code=0,
                    message=f"Network error: {str(e)}",
                ) from e
