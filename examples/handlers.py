"""Example job handlers for the example application."""

import logging
from typing import Any

from async_jobs.models import JobContext
from async_jobs.registry import job_registry

logger = logging.getLogger(__name__)


@job_registry.handler("example_notification")
async def example_notification(ctx: JobContext, payload: dict[str, Any]):
    """Example notification handler."""
    logger.info(f"Processing notification job {ctx.job_id} for tenant {ctx.tenant_id}")
    logger.info(f"Attempt {ctx.attempt} of job")

    # Extract payload
    recipient = payload.get("recipient")
    message = payload.get("message")
    notification_type = payload.get("type", "email")

    logger.info(f"Sending {notification_type} to {recipient}: {message}")

    # Simulate notification processing
    # In production, integrate with SendGrid, Twilio, FCM, etc.

    return {
        "status": "sent",
        "recipient": recipient,
        "type": notification_type,
        "job_id": str(ctx.job_id),
    }


@job_registry.handler("example_data_processing")
async def example_data_processing(ctx: JobContext, payload: dict[str, Any]):
    """Example data processing handler."""
    logger.info(f"Processing data job {ctx.job_id} for tenant {ctx.tenant_id}")

    # Extract payload
    data_id = payload.get("data_id")
    operation = payload.get("operation", "transform")

    logger.info(f"Performing {operation} on data {data_id}")

    # Simulate data processing
    # In production, perform actual data transformations

    return {
        "status": "completed",
        "data_id": data_id,
        "operation": operation,
        "job_id": str(ctx.job_id),
    }


@job_registry.handler("example_webhook")
async def example_webhook(ctx: JobContext, payload: dict[str, Any]):
    """Example webhook handler."""
    logger.info(f"Processing webhook job {ctx.job_id} for tenant {ctx.tenant_id}")

    # Extract payload
    url = payload.get("url")
    method = payload.get("method", "POST")
    data = payload.get("data", {})

    logger.info(f"Sending {method} request to {url}")

    # Simulate webhook call
    # In production, use httpx to make actual HTTP requests

    return {
        "status": "sent",
        "url": url,
        "method": method,
        "job_id": str(ctx.job_id),
    }
