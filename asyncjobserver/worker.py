"""Worker service for executing jobs from queues."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Type, List

from asyncjobserver.job import Job, JobStatus, JobPriority
from asyncjobserver.storage.postgres import PostgresJobStorage
from asyncjobserver.queue.sqs import SQSQueue

logger = logging.getLogger(__name__)


class Worker:
    """
    Worker service that fetches and executes jobs from SQS queues.
    
    The Worker continuously polls SQS queues for jobs, executes their
    handle methods, and updates their status in the database. It supports
    multiple priority queues and can process jobs concurrently.
    
    Example:
        ```python
        # Register job types
        job_registry = {
            "SayHelloJob": SayHelloJob,
            "SendEmailJob": SendEmailJob,
        }
        
        worker = Worker(
            storage=postgres_storage,
            queue=sqs_queue,
            job_registry=job_registry,
            priorities=[JobPriority.HIGH, JobPriority.MEDIUM],
            concurrency=5
        )
        
        # Start the worker
        await worker.start()
        
        # Stop the worker
        await worker.stop()
        ```
    """

    def __init__(
        self,
        storage: PostgresJobStorage,
        queue: SQSQueue,
        job_registry: Dict[str, Type[Job]],
        priorities: Optional[List[JobPriority]] = None,
        concurrency: int = 5,
        poll_interval: float = 1.0,
        max_messages_per_poll: int = 10,
    ):
        """
        Initialize the worker.
        
        Args:
            storage: PostgreSQL storage instance
            queue: SQS queue instance
            job_registry: Dictionary mapping job type names to Job classes
            priorities: List of priorities to process (defaults to all)
            concurrency: Maximum number of concurrent job executions
            poll_interval: Time in seconds between polling cycles
            max_messages_per_poll: Maximum messages to fetch per poll
        """
        self.storage = storage
        self.queue = queue
        self.job_registry = job_registry
        self.priorities = priorities or list(JobPriority)
        self.concurrency = concurrency
        self.poll_interval = poll_interval
        self.max_messages_per_poll = max_messages_per_poll
        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._semaphore: Optional[asyncio.Semaphore] = None

    def register_job_type(self, job_class: Type[Job]) -> None:
        """
        Register a job type with the worker.
        
        Args:
            job_class: Job class to register
        """
        self.job_registry[job_class.__name__] = job_class

    async def _execute_job(self, job: Job, receipt_handle: str, priority: JobPriority) -> None:
        """
        Execute a single job.
        
        Args:
            job: Job instance to execute
            receipt_handle: SQS receipt handle for message deletion
            priority: Priority queue the job came from
        """
        job_id = job.config.job_id
        job_type = job.config.job_type
        
        try:
            # Update job status to running
            job.config.status = JobStatus.RUNNING
            job.config.started_at = datetime.utcnow()
            await self.storage.update_job_status(
                job_id=job_id,
                status=JobStatus.RUNNING,
            )
            
            logger.info(f"Executing job {job_id} ({job_type})")
            
            # Execute the job's handle method
            result = await job.handle()
            
            # Update job status to completed
            job.config.status = JobStatus.COMPLETED
            job.config.completed_at = datetime.utcnow()
            job.config.result = result
            
            await self.storage.update_job_status(
                job_id=job_id,
                status=JobStatus.COMPLETED,
                result=result,
            )
            
            # Delete message from queue
            self.queue.delete_message(receipt_handle, priority)
            
            logger.info(f"Job {job_id} ({job_type}) completed successfully")
            
        except Exception as e:
            logger.error(f"Job {job_id} ({job_type}) failed: {e}", exc_info=True)
            
            # Check if we should retry
            if job.config.retry_count < job.config.max_retries:
                job.config.retry_count += 1
                job.config.status = JobStatus.PENDING
                
                # Reset to pending status for retry
                await self.storage.update_job_status(
                    job_id=job_id,
                    status=JobStatus.PENDING,
                    error_message=f"Retry {job.config.retry_count}/{job.config.max_retries}: {str(e)}",
                )
                
                logger.info(
                    f"Job {job_id} will be retried "
                    f"({job.config.retry_count}/{job.config.max_retries})"
                )
            else:
                # Max retries reached, mark as failed
                job.config.status = JobStatus.FAILED
                job.config.completed_at = datetime.utcnow()
                job.config.error_message = str(e)
                
                await self.storage.update_job_status(
                    job_id=job_id,
                    status=JobStatus.FAILED,
                    error_message=str(e),
                )
                
                logger.error(f"Job {job_id} failed after {job.config.max_retries} retries")
            
            # Delete message from queue either way
            self.queue.delete_message(receipt_handle, priority)

    async def _process_message(self, message: Dict, priority: JobPriority) -> None:
        """
        Process a single message from the queue.
        
        Args:
            message: Message dictionary containing job data
            priority: Priority queue the message came from
        """
        try:
            job_data = message["job_data"]
            receipt_handle = message["receipt_handle"]
            job_type = job_data.get("job_type")
            
            # Check if job type is registered
            if job_type not in self.job_registry:
                logger.error(
                    f"Unknown job type: {job_type}. Available types: "
                    f"{list(self.job_registry.keys())}"
                )
                # Delete unknown job type messages
                self.queue.delete_message(receipt_handle, priority)
                return
            
            # Instantiate the job
            job_class = self.job_registry[job_type]
            job = job_class.from_dict(job_data)
            
            # Execute the job with concurrency control
            async with self._semaphore:
                await self._execute_job(job, receipt_handle, priority)
                
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

    async def _poll_queue(self, priority: JobPriority) -> None:
        """
        Poll a specific priority queue for jobs.
        
        Args:
            priority: Priority queue to poll
        """
        while self._running:
            try:
                messages = self.queue.receive_jobs(
                    priority=priority,
                    max_messages=self.max_messages_per_poll,
                    wait_time_seconds=20,  # Long polling
                )
                
                if messages:
                    logger.info(
                        f"Received {len(messages)} messages from {priority.value} queue"
                    )
                    
                    # Process messages concurrently
                    tasks = [
                        asyncio.create_task(self._process_message(msg, priority))
                        for msg in messages
                    ]
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                await asyncio.sleep(self.poll_interval)
                
            except asyncio.CancelledError:
                logger.info(f"Queue poller for {priority.value} cancelled")
                break
            except Exception as e:
                logger.error(
                    f"Error polling {priority.value} queue: {e}",
                    exc_info=True,
                )
                await asyncio.sleep(self.poll_interval)

    async def start(self) -> None:
        """Start the worker."""
        if self._running:
            logger.warning("Worker is already running")
            return
        
        self._running = True
        self._semaphore = asyncio.Semaphore(self.concurrency)
        
        # Create a polling task for each priority
        for priority in self.priorities:
            task = asyncio.create_task(self._poll_queue(priority))
            self._tasks.append(task)
        
        logger.info(
            f"Worker started with {self.concurrency} concurrent jobs, "
            f"polling {len(self.priorities)} queues"
        )

    async def stop(self) -> None:
        """Stop the worker."""
        if not self._running:
            logger.warning("Worker is not running")
            return
        
        self._running = False
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        # Wait for all tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
        self._tasks.clear()
        self._semaphore = None
        
        logger.info("Worker stopped")
