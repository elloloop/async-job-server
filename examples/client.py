"""Example client script for enqueueing jobs."""

import asyncio
from datetime import datetime

from async_jobs import AsyncJobsHttpClient


async def main():
    """Example of using the HTTP client to enqueue jobs."""

    # Initialize client
    client = AsyncJobsHttpClient(
        base_url="http://localhost:8000",
        # auth_token="your-token-here"  # Add if using authentication
    )

    print("🚀 Enqueueing example jobs...\n")

    # Example 1: Enqueue a notification job
    job_id_1 = await client.enqueue(
        tenant_id="tenant-123",
        use_case="notifications",
        type="example_notification",
        queue="notifications",
        payload={
            "recipient": "user@example.com",
            "message": "Hello from async jobs!",
            "type": "email",
        },
        delay_tolerance_seconds=60,
        max_attempts=3,
        backoff_policy={
            "type": "exponential",
            "base_delay_seconds": 60,
            "max_delay_seconds": 3600,
        },
        priority=5,
    )
    print(f"✅ Enqueued notification job: {job_id_1}")

    # Example 2: Enqueue a data processing job
    job_id_2 = await client.enqueue(
        tenant_id="tenant-123",
        use_case="message_labeling",
        type="example_data_processing",
        queue="message-labeling",
        payload={
            "data_id": "data-456",
            "operation": "transform",
        },
        delay_tolerance_seconds=120,
        max_attempts=5,
        backoff_policy={
            "type": "linear",
            "base_delay_seconds": 30,
            "max_delay_seconds": 600,
        },
        dedupe_key="data-456-transform",  # Prevents duplicate processing
    )
    print(f"✅ Enqueued data processing job: {job_id_2}")

    # Example 3: Enqueue a webhook job
    job_id_3 = await client.enqueue(
        tenant_id="tenant-789",
        use_case="notifications",
        type="example_webhook",
        queue="notifications",
        payload={
            "url": "https://api.example.com/webhook",
            "method": "POST",
            "data": {"event": "user_signup", "user_id": "user-123"},
        },
        delay_tolerance_seconds=30,
        max_attempts=3,
        backoff_policy={
            "type": "constant",
            "base_delay_seconds": 60,
            "max_delay_seconds": 60,
        },
    )
    print(f"✅ Enqueued webhook job: {job_id_3}")

    print("\n📊 Checking job status...\n")

    # Get job details
    job_details = await client.get_job(job_id_1)
    print(f"Job {job_id_1}:")
    print(f"  Status: {job_details['status']}")
    print(f"  Type: {job_details['type']}")
    print(f"  Created: {job_details['created_at']}")

    # List jobs for tenant
    print("\n📋 Listing jobs for tenant-123...\n")
    jobs_response = await client.list_jobs(tenant_id="tenant-123", limit=10)
    print(f"Found {len(jobs_response['jobs'])} jobs")
    for job in jobs_response["jobs"]:
        print(f"  - {job['id']}: {job['type']} ({job['status']})")


if __name__ == "__main__":
    asyncio.run(main())
