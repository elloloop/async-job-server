"""Unit tests for FastAPI router."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient
from fastapi import FastAPI

from async_jobs.config import AsyncJobsConfig
from async_jobs.errors import QuotaExceededError
from async_jobs.fastapi_router import create_jobs_router
from async_jobs.models import Job, JobStatus
from async_jobs.service import JobService


@pytest.fixture
def mock_job_service():
    """Create a mock job service."""
    service = MagicMock(spec=JobService)
    service.enqueue = AsyncMock()
    service.get_job = AsyncMock()
    service.list_jobs = AsyncMock(return_value=[])
    return service


@pytest.fixture
def app(mock_job_service):
    """Create FastAPI app with router."""
    def job_service_factory():
        return mock_job_service

    router = create_jobs_router(job_service_factory, auth_token=None)
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


def test_enqueue_job_success(client, mock_job_service):
    """Test successful job enqueue via HTTP."""
    job_id = uuid4()
    mock_job_service.enqueue.return_value = job_id

    response = client.post(
        "/jobs/enqueue",
        json={
            "tenant_id": "tenant1",
            "use_case": "notifications",
            "type": "send_notification",
            "queue": "async-notifications",
            "payload": {"email": "test@example.com"},
        },
    )

    assert response.status_code == 200
    assert response.json()["job_id"] == str(job_id)


def test_enqueue_job_missing_fields(client):
    """Test that missing required fields return 422."""
    response = client.post(
        "/jobs/enqueue",
        json={
            "tenant_id": "tenant1",
            # Missing use_case, type, queue, payload
        },
    )

    assert response.status_code == 422


def test_enqueue_job_quota_exceeded(client, mock_job_service):
    """Test that quota exceeded returns 429."""
    mock_job_service.enqueue.side_effect = QuotaExceededError(
        "tenant1", "notifications"
    )

    response = client.post(
        "/jobs/enqueue",
        json={
            "tenant_id": "tenant1",
            "use_case": "notifications",
            "type": "send_notification",
            "queue": "async-notifications",
            "payload": {},
        },
    )

    assert response.status_code == 429


def test_enqueue_job_with_auth_token():
    """Test that auth token is required when configured."""
    mock_job_service = MagicMock(spec=JobService)
    mock_job_service.enqueue = AsyncMock()

    def job_service_factory():
        return mock_job_service

    router = create_jobs_router(job_service_factory, auth_token="secret-token")
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # Request without token should fail
    response = client.post(
        "/jobs/enqueue",
        json={
            "tenant_id": "tenant1",
            "use_case": "notifications",
            "type": "send_notification",
            "queue": "async-notifications",
            "payload": {},
        },
    )

    assert response.status_code == 401

    # Request with correct token should succeed
    job_id = uuid4()
    mock_job_service.enqueue.return_value = job_id

    response = client.post(
        "/jobs/enqueue",
        json={
            "tenant_id": "tenant1",
            "use_case": "notifications",
            "type": "send_notification",
            "queue": "async-notifications",
            "payload": {},
        },
        headers={"X-Async-Jobs-Token": "secret-token"},
    )

    assert response.status_code == 200


def test_get_job_success(client, mock_job_service):
    """Test getting a job successfully."""
    from datetime import datetime

    job_id = uuid4()
    job = Job(
        id=job_id,
        tenant_id="tenant1",
        use_case="notifications",
        type="send_notification",
        queue="async-notifications",
        status=JobStatus.PENDING,
        payload={"email": "test@example.com"},
        run_at=datetime.utcnow(),
        delay_tolerance="3 seconds",
        deadline_at=datetime.utcnow(),
        priority=0,
        attempts=0,
        max_attempts=5,
        backoff_policy={},
    )

    mock_job_service.get_job.return_value = job

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(job_id)


def test_get_job_not_found(client, mock_job_service):
    """Test getting a non-existent job returns 404."""
    from async_jobs.errors import JobNotFoundError

    job_id = uuid4()
    mock_job_service.get_job.side_effect = JobNotFoundError(str(job_id))

    response = client.get(f"/jobs/{job_id}")

    assert response.status_code == 404


def test_list_jobs(client, mock_job_service):
    """Test listing jobs."""
    from datetime import datetime

    job = Job(
        id=uuid4(),
        tenant_id="tenant1",
        use_case="notifications",
        type="send_notification",
        queue="async-notifications",
        status=JobStatus.PENDING,
        payload={},
        run_at=datetime.utcnow(),
        delay_tolerance="3 seconds",
        deadline_at=datetime.utcnow(),
        priority=0,
        attempts=0,
        max_attempts=5,
        backoff_policy={},
    )

    mock_job_service.list_jobs.return_value = [job]

    response = client.get("/jobs?tenant_id=tenant1&limit=10")

    assert response.status_code == 200
    assert len(response.json()) == 1
