"""Tests for scheduler service."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from asyncjobserver.scheduler import Scheduler
from asyncjobserver.job import Job, JobPriority, JobStatus
from typing import Dict, Any


class MockJob(Job):
    """Mock job for testing."""

    async def handle(self) -> Dict[str, Any]:
        return {"status": "ok"}


@pytest.fixture
def mock_storage():
    """Create a mock storage."""
    storage = AsyncMock()
    storage.fetch_pending_jobs = AsyncMock(return_value=[])
    storage.update_job_status = AsyncMock()
    storage.save_job = AsyncMock()
    return storage


@pytest.fixture
def mock_queue():
    """Create a mock queue."""
    queue = MagicMock()
    queue.send_job = MagicMock(return_value="msg-123")
    return queue


@pytest.fixture
def scheduler(mock_storage, mock_queue):
    """Create a scheduler instance."""
    return Scheduler(
        storage=mock_storage,
        queue=mock_queue,
        poll_interval=0.1,
        batch_size=10,
    )


def test_scheduler_initialization(scheduler, mock_storage, mock_queue):
    """Test scheduler initialization."""
    assert scheduler.storage == mock_storage
    assert scheduler.queue == mock_queue
    assert scheduler.poll_interval == 0.1
    assert scheduler.batch_size == 10
    assert scheduler._running is False


def test_register_job_type(scheduler):
    """Test job type registration."""
    scheduler.register_job_type(MockJob)
    
    assert "MockJob" in scheduler.job_registry
    assert scheduler.job_registry["MockJob"] == MockJob


@pytest.mark.asyncio
async def test_schedule_job(scheduler, mock_storage, mock_queue):
    """Test manual job scheduling."""
    job = MockJob(priority=JobPriority.HIGH)
    
    await scheduler.schedule_job(job)
    
    # Verify job was saved
    mock_storage.save_job.assert_called_once_with(job)
    
    # Verify job was sent to queue
    assert mock_queue.send_job.called
    
    # Verify status was updated
    mock_storage.update_job_status.assert_called_once()


@pytest.mark.asyncio
async def test_schedule_job_handles_errors(scheduler, mock_storage, mock_queue):
    """Test job scheduling with errors."""
    job = MockJob(priority=JobPriority.MEDIUM)
    mock_queue.send_job.side_effect = Exception("Queue error")
    
    await scheduler.schedule_job(job)
    
    # Verify error handling updated status to failed
    calls = mock_storage.update_job_status.call_args_list
    assert any(
        call.kwargs.get("status") == JobStatus.FAILED
        for call in calls
    )
