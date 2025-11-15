"""Job base class and related types for asyncjobserver."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Status of a job in the system."""
    
    PENDING = "pending"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(str, Enum):
    """Priority levels for job execution."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class JobConfig(BaseModel):
    """Configuration for a job instance."""
    
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    job_type: str
    priority: JobPriority = JobPriority.MEDIUM
    delay_seconds: int = 0
    max_retries: int = 3
    retry_count: int = 0
    parameters: Dict[str, Any] = Field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

    def calculate_scheduled_time(self) -> datetime:
        """Calculate when this job should be executed."""
        if self.scheduled_at:
            return self.scheduled_at
        return self.created_at + timedelta(seconds=self.delay_seconds)

    model_config = {
        "use_enum_values": True,
    }


class Job(ABC):
    """
    Base class for all jobs in the asyncjobserver system.
    
    Jobs are the fundamental unit of work. Each job type should inherit from this
    class and implement the `handle` method to define what work should be done.
    
    Example:
        ```python
        class SayHelloJob(Job):
            async def handle(self) -> Dict[str, Any]:
                print("say hello")
                return {"message": "Hello executed successfully"}
        
        # Create and configure a job
        job = SayHelloJob(
            priority=JobPriority.MEDIUM,
            delay_seconds=10,
            parameters={"name": "World"}
        )
        ```
    """

    def __init__(
        self,
        priority: JobPriority = JobPriority.MEDIUM,
        delay_seconds: int = 0,
        max_retries: int = 3,
        parameters: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
    ):
        """
        Initialize a new job instance.
        
        Args:
            priority: Priority level for job execution
            delay_seconds: Number of seconds to delay before execution
            max_retries: Maximum number of retry attempts on failure
            parameters: Dictionary of parameters to pass to the job
            job_id: Optional job ID (generated if not provided)
        """
        self.config = JobConfig(
            job_id=job_id or str(uuid4()),
            job_type=self.__class__.__name__,
            priority=priority,
            delay_seconds=delay_seconds,
            max_retries=max_retries,
            parameters=parameters or {},
        )

    @abstractmethod
    async def handle(self) -> Dict[str, Any]:
        """
        Execute the job's main logic.
        
        This method must be implemented by all job subclasses to define
        what work should be performed when the job is executed.
        
        Returns:
            A dictionary containing the job's execution result.
            
        Raises:
            Exception: Any exception raised will cause the job to fail
                      and potentially be retried based on max_retries.
        """
        pass

    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary representation for storage/serialization."""
        return self.config.model_dump()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """
        Create a job instance from dictionary data.
        
        Args:
            data: Dictionary containing job configuration
            
        Returns:
            A new job instance
        """
        job_type = data.get("job_type")
        if job_type != cls.__name__:
            raise ValueError(f"Job type mismatch: expected {cls.__name__}, got {job_type}")
        
        job = cls(
            priority=JobPriority(data.get("priority", JobPriority.MEDIUM)),
            delay_seconds=data.get("delay_seconds", 0),
            max_retries=data.get("max_retries", 3),
            parameters=data.get("parameters", {}),
            job_id=data.get("job_id"),
        )
        
        # Restore status and timestamps
        job.config.status = JobStatus(data.get("status", JobStatus.PENDING))
        job.config.retry_count = data.get("retry_count", 0)
        
        if data.get("created_at"):
            job.config.created_at = (
                data["created_at"]
                if isinstance(data["created_at"], datetime)
                else datetime.fromisoformat(data["created_at"])
            )
        if data.get("scheduled_at"):
            job.config.scheduled_at = (
                data["scheduled_at"]
                if isinstance(data["scheduled_at"], datetime)
                else datetime.fromisoformat(data["scheduled_at"])
            )
        if data.get("started_at"):
            job.config.started_at = (
                data["started_at"]
                if isinstance(data["started_at"], datetime)
                else datetime.fromisoformat(data["started_at"])
            )
        if data.get("completed_at"):
            job.config.completed_at = (
                data["completed_at"]
                if isinstance(data["completed_at"], datetime)
                else datetime.fromisoformat(data["completed_at"])
            )
        
        job.config.error_message = data.get("error_message")
        job.config.result = data.get("result")
        
        return job

    def __repr__(self) -> str:
        """String representation of the job."""
        return (
            f"{self.__class__.__name__}(job_id={self.config.job_id}, "
            f"priority={self.config.priority}, status={self.config.status})"
        )
