"""FastAPI example demonstrating asyncjobserver library usage."""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from asyncjobserver import Job, JobPriority, JobStatus
from asyncjobserver.scheduler import Scheduler
from asyncjobserver.worker import Worker
from asyncjobserver.storage.postgres import PostgresJobStorage
from asyncjobserver.queue.sqs import SQSQueue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Example Job: SayHelloJob
class SayHelloJob(Job):
    """Example job that prints a hello message."""

    async def handle(self) -> Dict[str, Any]:
        """Execute the say hello job."""
        name = self.config.parameters.get("name", "World")
        message = f"say hello to {name}"
        print(message)
        logger.info(message)
        return {"message": f"Hello executed successfully for {name}"}


# Example Job: CalculationJob
class CalculationJob(Job):
    """Example job that performs a calculation."""

    async def handle(self) -> Dict[str, Any]:
        """Execute a calculation."""
        a = self.config.parameters.get("a", 0)
        b = self.config.parameters.get("b", 0)
        operation = self.config.parameters.get("operation", "add")
        
        if operation == "add":
            result = a + b
        elif operation == "multiply":
            result = a * b
        elif operation == "subtract":
            result = a - b
        elif operation == "divide":
            if b == 0:
                raise ValueError("Cannot divide by zero")
            result = a / b
        else:
            raise ValueError(f"Unknown operation: {operation}")
        
        logger.info(f"Calculation: {a} {operation} {b} = {result}")
        return {"result": result, "operation": operation}


# Job registry
JOB_REGISTRY = {
    "SayHelloJob": SayHelloJob,
    "CalculationJob": CalculationJob,
}

# Global instances
storage: PostgresJobStorage = None
queue: SQSQueue = None
scheduler: Scheduler = None
worker: Worker = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan."""
    global storage, queue, scheduler, worker
    
    logger.info("Starting application...")
    
    # Initialize storage
    storage = PostgresJobStorage(
        host="localhost",
        port=5432,
        database="asyncjobs",
        user="postgres",
        password="postgres",
    )
    await storage.connect()
    await storage.initialize()
    logger.info("PostgreSQL storage initialized")
    
    # Initialize queue (using LocalStack for local development)
    queue = SQSQueue(
        region_name="us-east-1",
        queue_name_prefix="asyncjobs",
        endpoint_url="http://localhost:4566",  # LocalStack endpoint
    )
    queue.initialize()
    logger.info("SQS queues initialized")
    
    # Initialize scheduler
    scheduler = Scheduler(
        storage=storage,
        queue=queue,
        poll_interval=5.0,
        batch_size=50,
        job_registry=JOB_REGISTRY,
    )
    await scheduler.start()
    logger.info("Scheduler started")
    
    # Initialize worker
    worker = Worker(
        storage=storage,
        queue=queue,
        job_registry=JOB_REGISTRY,
        priorities=[JobPriority.CRITICAL, JobPriority.HIGH, JobPriority.MEDIUM, JobPriority.LOW],
        concurrency=5,
    )
    await worker.start()
    logger.info("Worker started")
    
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    
    if worker:
        await worker.stop()
        logger.info("Worker stopped")
    
    if scheduler:
        await scheduler.stop()
        logger.info("Scheduler stopped")
    
    if storage:
        await storage.disconnect()
        logger.info("Storage disconnected")
    
    logger.info("Application shutdown complete")


app = FastAPI(
    title="AsyncJobServer Example",
    description="FastAPI application demonstrating asyncjobserver library",
    version="0.1.0",
    lifespan=lifespan,
)


# Request/Response models
class CreateJobRequest(BaseModel):
    """Request model for creating a job."""
    
    job_type: str
    priority: JobPriority = JobPriority.MEDIUM
    delay_seconds: int = 0
    parameters: Dict[str, Any] = {}


class JobResponse(BaseModel):
    """Response model for job information."""
    
    job_id: str
    job_type: str
    priority: str
    status: str
    created_at: str
    scheduled_at: str = None
    started_at: str = None
    completed_at: str = None
    error_message: str = None
    result: Dict[str, Any] = None


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "AsyncJobServer FastAPI Example",
        "version": "0.1.0",
        "endpoints": {
            "create_job": "POST /jobs",
            "get_job": "GET /jobs/{job_id}",
            "list_jobs": "GET /jobs",
            "health": "GET /health",
        },
    }


@app.post("/jobs", response_model=JobResponse)
async def create_job(request: CreateJobRequest):
    """
    Create a new job.
    
    Example request for SayHelloJob:
    ```json
    {
        "job_type": "SayHelloJob",
        "priority": "medium",
        "delay_seconds": 5,
        "parameters": {"name": "FastAPI"}
    }
    ```
    """
    # Validate job type
    if request.job_type not in JOB_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown job type: {request.job_type}. "
                   f"Available types: {list(JOB_REGISTRY.keys())}",
        )
    
    # Create job instance
    job_class = JOB_REGISTRY[request.job_type]
    job = job_class(
        priority=request.priority,
        delay_seconds=request.delay_seconds,
        parameters=request.parameters,
    )
    
    # Save to storage
    await storage.save_job(job)
    
    logger.info(
        f"Created job {job.config.job_id} ({request.job_type}) "
        f"with priority {request.priority}"
    )
    
    # Return job details
    job_data = job.to_dict()
    created_at = job_data.get("created_at")
    scheduled_at = job_data.get("scheduled_at")
    
    return JobResponse(
        job_id=job_data["job_id"],
        job_type=job_data["job_type"],
        priority=job_data["priority"],
        status=job_data["status"],
        created_at=created_at.isoformat() if created_at else None,
        scheduled_at=scheduled_at.isoformat() if scheduled_at else None,
    )


@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get job details by ID."""
    job_data = await storage.get_job(job_id)
    
    if not job_data:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    
    created_at = job_data.get("created_at")
    scheduled_at = job_data.get("scheduled_at")
    started_at = job_data.get("started_at")
    completed_at = job_data.get("completed_at")
    
    return JobResponse(
        job_id=job_data["job_id"],
        job_type=job_data["job_type"],
        priority=job_data["priority"],
        status=job_data["status"],
        created_at=created_at.isoformat() if created_at else None,
        scheduled_at=scheduled_at.isoformat() if scheduled_at else None,
        started_at=started_at.isoformat() if started_at else None,
        completed_at=completed_at.isoformat() if completed_at else None,
        error_message=job_data.get("error_message"),
        result=job_data.get("result"),
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "scheduler_running": scheduler._running if scheduler else False,
        "worker_running": worker._running if worker else False,
        "storage_connected": storage.pool is not None if storage else False,
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "fastapi_example:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
