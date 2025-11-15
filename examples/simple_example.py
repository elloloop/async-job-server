"""Simple standalone example without FastAPI."""

import asyncio
import logging
from typing import Dict, Any

from asyncjobserver import Job, JobPriority
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


class SayHelloJob(Job):
    """Example job that prints hello."""

    async def handle(self) -> Dict[str, Any]:
        name = self.config.parameters.get("name", "World")
        message = f"say hello to {name}"
        print(f"\n{'='*50}")
        print(f"  {message.upper()}")
        print(f"{'='*50}\n")
        logger.info(message)
        return {"message": f"Hello executed successfully for {name}"}


class CalculationJob(Job):
    """Example calculation job."""

    async def handle(self) -> Dict[str, Any]:
        a = self.config.parameters.get("a", 0)
        b = self.config.parameters.get("b", 0)
        result = a + b
        logger.info(f"Calculation: {a} + {b} = {result}")
        return {"result": result}


async def main():
    """Main function to demonstrate the library."""
    logger.info("Starting AsyncJobServer example...")
    
    # Job registry
    job_registry = {
        "SayHelloJob": SayHelloJob,
        "CalculationJob": CalculationJob,
    }
    
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
    logger.info("✓ PostgreSQL storage initialized")
    
    # Initialize queue (using LocalStack)
    queue = SQSQueue(
        region_name="us-east-1",
        queue_name_prefix="asyncjobs",
        endpoint_url="http://localhost:4566",
    )
    await queue.initialize()
    logger.info("✓ SQS queues initialized")
    
    # Create scheduler
    scheduler = Scheduler(
        storage=storage,
        queue=queue,
        job_registry=job_registry,
        poll_interval=2.0,
    )
    await scheduler.start()
    logger.info("✓ Scheduler started")
    
    # Create worker
    worker = Worker(
        storage=storage,
        queue=queue,
        job_registry=job_registry,
        concurrency=3,
        poll_interval=1.0,
    )
    await worker.start()
    logger.info("✓ Worker started")
    
    # Submit some example jobs
    logger.info("\nSubmitting example jobs...")
    
    # Job 1: Say hello immediately
    job1 = SayHelloJob(
        priority=JobPriority.HIGH,
        delay_seconds=0,
        parameters={"name": "AsyncJobServer User"},
    )
    await storage.save_job(job1)
    logger.info(f"✓ Created SayHelloJob (ID: {job1.config.job_id})")
    
    # Job 2: Say hello with delay
    job2 = SayHelloJob(
        priority=JobPriority.MEDIUM,
        delay_seconds=5,
        parameters={"name": "Delayed User"},
    )
    await storage.save_job(job2)
    logger.info(f"✓ Created delayed SayHelloJob (ID: {job2.config.job_id})")
    
    # Job 3: Calculation
    job3 = CalculationJob(
        priority=JobPriority.LOW,
        delay_seconds=0,
        parameters={"a": 10, "b": 20},
    )
    await storage.save_job(job3)
    logger.info(f"✓ Created CalculationJob (ID: {job3.config.job_id})")
    
    logger.info("\nJobs submitted! Waiting for execution...")
    logger.info("Press Ctrl+C to stop\n")
    
    try:
        # Run for a while
        await asyncio.sleep(30)
    except KeyboardInterrupt:
        logger.info("\nShutting down...")
    finally:
        # Cleanup
        await worker.stop()
        logger.info("✓ Worker stopped")
        
        await scheduler.stop()
        logger.info("✓ Scheduler stopped")
        
        await storage.disconnect()
        logger.info("✓ Storage disconnected")
        
        logger.info("\nExample completed!")


if __name__ == "__main__":
    asyncio.run(main())
