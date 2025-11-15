"""Scheduler service for managing job execution timing and distribution."""

import asyncio
import logging
from typing import Dict, Optional, Type

from asyncjobserver.job import Job, JobStatus, JobPriority
from asyncjobserver.storage.postgres import PostgresJobStorage
from asyncjobserver.queue.sqs import SQSQueue

logger = logging.getLogger(__name__)


class Scheduler:
    """
    Scheduler service that fetches pending jobs and distributes them to queues.
    
    The Scheduler periodically polls the PostgreSQL database for jobs that are
    ready to be executed, then distributes them to the appropriate SQS queues
    based on their priority level.
    
    Example:
        ```python
        scheduler = Scheduler(
            storage=postgres_storage,
            queue=sqs_queue,
            poll_interval=5.0,
            batch_size=50
        )
        
        # Start the scheduler
        await scheduler.start()
        
        # Stop the scheduler
        await scheduler.stop()
        ```
    """

    def __init__(
        self,
        storage: PostgresJobStorage,
        queue: SQSQueue,
        poll_interval: float = 5.0,
        batch_size: int = 100,
        job_registry: Optional[Dict[str, Type[Job]]] = None,
    ):
        """
        Initialize the scheduler.
        
        Args:
            storage: PostgreSQL storage instance
            queue: SQS queue instance
            poll_interval: Time in seconds between polling cycles
            batch_size: Maximum number of jobs to fetch per cycle
            job_registry: Dictionary mapping job type names to Job classes
        """
        self.storage = storage
        self.queue = queue
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.job_registry = job_registry or {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def register_job_type(self, job_class: Type[Job]) -> None:
        """
        Register a job type with the scheduler.
        
        Args:
            job_class: Job class to register
        """
        self.job_registry[job_class.__name__] = job_class

    async def _schedule_job(self, job_data: Dict) -> None:
        """
        Schedule a single job by sending it to the appropriate queue.
        
        Args:
            job_data: Job data dictionary from storage
        """
        try:
            priority = JobPriority(job_data["priority"])
            job_id = job_data["job_id"]
            
            # Send to SQS queue
            message_id = self.queue.send_job(job_data, priority=priority)
            
            # Update job status in database
            await self.storage.update_job_status(
                job_id=job_id,
                status=JobStatus.SCHEDULED,
            )
            
            logger.info(
                f"Scheduled job {job_id} ({job_data['job_type']}) "
                f"with priority {priority.value}, message_id={message_id}"
            )
            
        except Exception as e:
            logger.error(f"Failed to schedule job {job_data.get('job_id')}: {e}")
            # Update job status to failed
            await self.storage.update_job_status(
                job_id=job_data["job_id"],
                status=JobStatus.FAILED,
                error_message=f"Scheduling failed: {str(e)}",
            )

    async def _poll_and_schedule(self) -> None:
        """Poll for pending jobs and schedule them."""
        try:
            # Fetch pending jobs for each priority
            for priority in JobPriority:
                pending_jobs = await self.storage.fetch_pending_jobs(
                    limit=self.batch_size,
                    priority=priority,
                )
                
                if pending_jobs:
                    logger.info(
                        f"Found {len(pending_jobs)} pending jobs with priority {priority.value}"
                    )
                    
                    # Schedule each job
                    for job_data in pending_jobs:
                        await self._schedule_job(job_data)
                        
        except Exception as e:
            logger.error(f"Error in scheduler poll cycle: {e}", exc_info=True)

    async def _run(self) -> None:
        """Main scheduler loop."""
        logger.info("Scheduler started")
        
        while self._running:
            try:
                await self._poll_and_schedule()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                logger.info("Scheduler cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in scheduler: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval)
        
        logger.info("Scheduler stopped")

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler is already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("Scheduler task created")

    async def stop(self) -> None:
        """Stop the scheduler."""
        if not self._running:
            logger.warning("Scheduler is not running")
            return
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        logger.info("Scheduler stopped")

    async def schedule_job(self, job: Job) -> None:
        """
        Manually schedule a single job.
        
        This is useful for immediately scheduling a job without waiting
        for the next poll cycle.
        
        Args:
            job: Job instance to schedule
        """
        # Save to storage first
        await self.storage.save_job(job)
        
        # Then schedule it
        job_data = job.to_dict()
        await self._schedule_job(job_data)
