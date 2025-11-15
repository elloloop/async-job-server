"""Tests for the Job base class."""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any

from asyncjobserver.job import Job, JobStatus, JobPriority, JobConfig


class TestJob(Job):
    """Test job implementation."""

    async def handle(self) -> Dict[str, Any]:
        """Test handle method."""
        return {"status": "success"}


class ParameterizedJob(Job):
    """Job that uses parameters."""

    async def handle(self) -> Dict[str, Any]:
        """Handle with parameters."""
        value = self.config.parameters.get("value", 0)
        multiplier = self.config.parameters.get("multiplier", 1)
        return {"result": value * multiplier}


def test_job_creation():
    """Test basic job creation."""
    job = TestJob(
        priority=JobPriority.HIGH,
        delay_seconds=10,
        max_retries=5,
        parameters={"key": "value"},
    )

    assert job.config.job_type == "TestJob"
    assert job.config.priority == JobPriority.HIGH
    assert job.config.delay_seconds == 10
    assert job.config.max_retries == 5
    assert job.config.parameters == {"key": "value"}
    assert job.config.status == JobStatus.PENDING
    assert job.config.retry_count == 0


def test_job_defaults():
    """Test job creation with default values."""
    job = TestJob()

    assert job.config.priority == JobPriority.MEDIUM
    assert job.config.delay_seconds == 0
    assert job.config.max_retries == 3
    assert job.config.parameters == {}
    assert job.config.status == JobStatus.PENDING


def test_job_scheduled_time_calculation():
    """Test scheduled time calculation."""
    job = TestJob(delay_seconds=60)
    
    scheduled_time = job.config.calculate_scheduled_time()
    expected_time = job.config.created_at + timedelta(seconds=60)
    
    # Allow for small timing differences
    assert abs((scheduled_time - expected_time).total_seconds()) < 1


def test_job_to_dict():
    """Test job serialization to dictionary."""
    job = TestJob(
        priority=JobPriority.CRITICAL,
        delay_seconds=30,
        parameters={"test": "data"},
    )
    
    job_dict = job.to_dict()
    
    assert job_dict["job_type"] == "TestJob"
    assert job_dict["priority"] == JobPriority.CRITICAL
    assert job_dict["delay_seconds"] == 30
    assert job_dict["parameters"] == {"test": "data"}
    assert job_dict["status"] == JobStatus.PENDING


def test_job_from_dict():
    """Test job deserialization from dictionary."""
    original_job = TestJob(
        priority=JobPriority.LOW,
        delay_seconds=15,
        parameters={"data": "value"},
    )
    
    job_dict = original_job.to_dict()
    restored_job = TestJob.from_dict(job_dict)
    
    assert restored_job.config.job_id == original_job.config.job_id
    assert restored_job.config.job_type == original_job.config.job_type
    assert restored_job.config.priority == original_job.config.priority
    assert restored_job.config.delay_seconds == original_job.config.delay_seconds
    assert restored_job.config.parameters == original_job.config.parameters


def test_job_from_dict_with_status():
    """Test job deserialization preserves status."""
    job_dict = {
        "job_id": "test-123",
        "job_type": "TestJob",
        "priority": "high",
        "delay_seconds": 0,
        "max_retries": 3,
        "retry_count": 2,
        "parameters": {},
        "status": "running",
        "created_at": datetime.utcnow().isoformat(),
        "scheduled_at": datetime.utcnow().isoformat(),
        "started_at": datetime.utcnow().isoformat(),
        "error_message": "Test error",
    }
    
    job = TestJob.from_dict(job_dict)
    
    assert job.config.status == JobStatus.RUNNING
    assert job.config.retry_count == 2
    assert job.config.error_message == "Test error"


@pytest.mark.asyncio
async def test_job_handle():
    """Test job handle execution."""
    job = TestJob()
    result = await job.handle()
    
    assert result == {"status": "success"}


@pytest.mark.asyncio
async def test_parameterized_job():
    """Test job with parameters."""
    job = ParameterizedJob(
        parameters={"value": 10, "multiplier": 3}
    )
    
    result = await job.handle()
    
    assert result == {"result": 30}


def test_job_repr():
    """Test job string representation."""
    job = TestJob(priority=JobPriority.HIGH)
    repr_str = repr(job)
    
    assert "TestJob" in repr_str
    assert job.config.job_id in repr_str
    assert "high" in repr_str
    # Status is represented as JobStatus.PENDING in the repr
    assert "PENDING" in repr_str
