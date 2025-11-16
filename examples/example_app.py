"""Example FastAPI application using async_jobs library."""

import asyncpg
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager

from async_jobs import create_jobs_router, AsyncJobsConfig, JobService, job_registry

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global database pool
db_pool = None


# Define job handlers
@job_registry.handler("send_welcome_email")
async def send_welcome_email(ctx, payload):
    """Send a welcome email to a new user."""
    logger = ctx["logger"]
    job = ctx["job"]

    user_email = payload["email"]
    user_name = payload["name"]

    logger.info(f"Sending welcome email to {user_email}")
    # Your email sending logic here
    # await email_service.send(...)
    logger.info(f"Welcome email sent successfully for job {job.id}")


@job_registry.handler("process_signup")
async def process_signup(ctx, payload):
    """Process a new user signup."""
    logger = ctx["logger"]
    job = ctx["job"]

    user_id = payload["user_id"]

    logger.info(f"Processing signup for user {user_id}")
    # Your signup processing logic here
    # await user_service.complete_onboarding(user_id)
    logger.info(f"Signup processed successfully for job {job.id}")


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool

    # Startup
    config = AsyncJobsConfig.from_env()
    logger.info("Connecting to database...")
    db_pool = await asyncpg.create_pool(
        config.db_dsn,
        min_size=2,
        max_size=10,
    )
    logger.info("Database connected")

    yield

    # Shutdown
    logger.info("Closing database connection...")
    await db_pool.close()
    logger.info("Database connection closed")


# Create FastAPI app
app = FastAPI(
    title="Example Async Jobs Service",
    description="Example application using async_jobs library",
    version="1.0.0",
    lifespan=lifespan,
)


# Factory for JobService
def job_service_factory():
    config = AsyncJobsConfig.from_env()
    return JobService(config, db_pool, logger)


# Include async jobs router
config = AsyncJobsConfig.from_env()
jobs_router = create_jobs_router(
    job_service_factory=job_service_factory,
    auth_token=config.enqueue_auth_token,
)
app.include_router(jobs_router, prefix="/async-jobs", tags=["jobs"])


# Example application endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Example Async Jobs Service",
        "docs": "/docs",
        "jobs_api": "/async-jobs",
    }


@app.post("/users/signup")
async def signup_user(email: str, name: str):
    """
    Example endpoint that enqueues jobs.

    This would be called by your frontend/API to create a new user
    and enqueue background jobs for email and processing.
    """
    job_service = job_service_factory()

    # Simulate creating a user
    user_id = "user-123"  # Would come from database

    # Enqueue welcome email job
    email_job_id = await job_service.enqueue(
        tenant_id="default",
        use_case="notifications",
        type="send_welcome_email",
        queue=config.sqs_queue_notifications,
        payload={
            "email": email,
            "name": name,
        },
        max_attempts=3,
    )

    # Enqueue signup processing job
    signup_job_id = await job_service.enqueue(
        tenant_id="default",
        use_case="notifications",
        type="process_signup",
        queue=config.sqs_queue_notifications,
        payload={
            "user_id": user_id,
        },
        max_attempts=5,
    )

    return {
        "user_id": user_id,
        "email_job_id": str(email_job_id),
        "signup_job_id": str(signup_job_id),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
