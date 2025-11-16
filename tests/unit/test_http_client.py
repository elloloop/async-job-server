"""Unit tests for HTTP client."""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import aiohttp

from async_jobs.errors import RemoteHttpError
from async_jobs.http_client import AsyncJobsHttpClient


@pytest.mark.asyncio
async def test_enqueue_success():
    """Test successful job enqueue via HTTP."""
    client = AsyncJobsHttpClient("https://api.example.com", auth_token="token")

    job_id = uuid4()

    with patch("aiohttp.ClientSession") as mock_session:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"job_id": str(job_id)})
        mock_resp.text = AsyncMock(return_value='{"job_id": "' + str(job_id) + '"}')

        mock_session.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_resp
        )
        mock_session.return_value.__aenter__.return_value.__aexit__ = AsyncMock()

        result = await client.enqueue(
            tenant_id="tenant1",
            use_case="notifications",
            type="send_notification",
            queue="async-notifications",
            payload={"email": "test@example.com"},
        )

    assert result == job_id


@pytest.mark.asyncio
async def test_enqueue_http_error():
    """Test that HTTP errors raise RemoteHttpError."""
    client = AsyncJobsHttpClient("https://api.example.com")

    with patch("aiohttp.ClientSession") as mock_session:
        mock_resp = AsyncMock()
        mock_resp.status = 429
        mock_resp.text = AsyncMock(return_value="Quota exceeded")

        mock_session.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=mock_resp
        )
        mock_session.return_value.__aenter__.return_value.__aexit__ = AsyncMock()

        with pytest.raises(RemoteHttpError) as exc_info:
            await client.enqueue(
                tenant_id="tenant1",
                use_case="notifications",
                type="send_notification",
                queue="async-notifications",
                payload={},
            )

        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_enqueue_network_error():
    """Test that network errors raise RemoteHttpError."""
    client = AsyncJobsHttpClient("https://api.example.com")

    with patch("aiohttp.ClientSession") as mock_session:
        mock_session.return_value.__aenter__.return_value.post = AsyncMock(
            side_effect=aiohttp.ClientError("Connection failed")
        )
        mock_session.return_value.__aenter__.return_value.__aexit__ = AsyncMock()

        with pytest.raises(RemoteHttpError):
            await client.enqueue(
                tenant_id="tenant1",
                use_case="notifications",
                type="send_notification",
                queue="async-notifications",
                payload={},
            )


@pytest.mark.asyncio
async def test_enqueue_with_auth_token():
    """Test that auth token is included in headers."""
    client = AsyncJobsHttpClient("https://api.example.com", auth_token="secret-token")

    job_id = uuid4()

    with patch("aiohttp.ClientSession") as mock_session:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"job_id": str(job_id)})
        mock_resp.text = AsyncMock(return_value='{"job_id": "' + str(job_id) + '"}')

        mock_post = AsyncMock(return_value=mock_resp)
        mock_session.return_value.__aenter__.return_value.post = mock_post
        mock_session.return_value.__aenter__.return_value.__aexit__ = AsyncMock()

        await client.enqueue(
            tenant_id="tenant1",
            use_case="notifications",
            type="send_notification",
            queue="async-notifications",
            payload={},
        )

        # Check that auth token was in headers
        call_kwargs = mock_post.call_args[1]
        assert "X-Async-Jobs-Token" in call_kwargs["headers"]
        assert call_kwargs["headers"]["X-Async-Jobs-Token"] == "secret-token"
