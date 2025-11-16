"""Example of using the HTTP client to enqueue jobs remotely."""

import asyncio
from async_jobs import AsyncJobsHttpClient


async def main():
    """Example of using the HTTP client."""

    # Create client
    client = AsyncJobsHttpClient(
        base_url="http://localhost:8000/async-jobs",
        auth_token="your-secret-token",  # Optional, if configured
        timeout=10.0,
    )

    # Enqueue a job
    try:
        job_id = await client.enqueue(
            tenant_id="tenant-123",
            use_case="notifications",
            type="send_email",
            queue="async-notifications",
            payload={
                "to": "user@example.com",
                "subject": "Hello!",
                "body": "This is a test email",
            },
            max_attempts=5,
            delay_tolerance_seconds=300,
        )

        print(f"Job enqueued successfully! Job ID: {job_id}")

        # Get job status
        job_info = await client.get_job(job_id)
        print(f"Job status: {job_info['status']}")
        print(f"Job info: {job_info}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
