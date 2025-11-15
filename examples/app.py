"""Example FastAPI application using async jobs library."""

import uvicorn
from fastapi import FastAPI
from psycopg_pool import AsyncConnectionPool

from async_jobs import AsyncJobsConfig, JobService, JobStore, create_jobs_router

# Create FastAPI app
app = FastAPI(
    title="Async Jobs Example API",
    description="Example API demonstrating the async jobs library",
    version="1.0.0",
)

# Global variables for connection pool
db_pool: AsyncConnectionPool | None = None
config: AsyncJobsConfig | None = None


@app.on_event("startup")
async def startup():
    """Initialize database connection pool on startup."""
    global db_pool, config
    config = AsyncJobsConfig.from_env()
    db_pool = AsyncConnectionPool(
        conninfo=config.db_dsn,
        min_size=2,
        max_size=10,
    )
    await db_pool.wait()
    print("✅ Database pool initialized")


@app.on_event("shutdown")
async def shutdown():
    """Close database connection pool on shutdown."""
    if db_pool:
        await db_pool.close()
        print("✅ Database pool closed")


def get_job_service() -> JobService:
    """Factory function to create job service."""
    if not db_pool or not config:
        raise RuntimeError("Application not initialized")
    store = JobStore(db_pool)
    return JobService(config, store)


# Include jobs router
jobs_router = create_jobs_router(
    job_service_factory=get_job_service,
    require_auth_token=bool(config.enqueue_auth_token) if config else False,
    expected_auth_token=config.enqueue_auth_token if config else None,
)
app.include_router(jobs_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Async Jobs Example API",
        "version": "1.0.0",
        "endpoints": {
            "enqueue": "POST /jobs/enqueue",
            "get_job": "GET /jobs/{job_id}",
            "list_jobs": "GET /jobs/",
            "docs": "/docs",
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "database": "connected" if db_pool else "not connected"}


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
