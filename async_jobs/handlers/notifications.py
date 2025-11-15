"""Example notification handlers."""
import logging
from typing import Any, Dict

from async_jobs.models import JobContext
from async_jobs.registry import job_registry

logger = logging.getLogger(__name__)


@job_registry.handler("send_notification")
async def send_notification(ctx: JobContext, payload: Dict[str, Any]):
    """Send a notification."""
    logger.info(f"Sending notification for job {ctx.job_id}, tenant {ctx.tenant_id}")
    logger.info(f"Payload: {payload}")
    
    # Example: In a real implementation, this would send an email, SMS, push notification, etc.
    notification_type = payload.get("notification_type")
    recipient = payload.get("recipient")
    message = payload.get("message")
    
    logger.info(f"Notification type: {notification_type}, recipient: {recipient}")
    logger.info(f"Message: {message}")
    
    # Simulate notification sending
    # In production, integrate with notification service (e.g., SendGrid, Twilio, FCM)
    
    return {"status": "sent", "notification_type": notification_type, "recipient": recipient}


@job_registry.handler("send_email")
async def send_email(ctx: JobContext, payload: Dict[str, Any]):
    """Send an email notification."""
    logger.info(f"Sending email for job {ctx.job_id}, tenant {ctx.tenant_id}")
    
    to_address = payload.get("to")
    subject = payload.get("subject")
    body = payload.get("body")
    
    logger.info(f"Email to: {to_address}, subject: {subject}")
    
    # Simulate email sending
    # In production, integrate with email service
    
    return {"status": "sent", "to": to_address}
