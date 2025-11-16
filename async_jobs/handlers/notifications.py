"""Example notification handlers."""

from async_jobs.registry import job_registry


@job_registry.handler("send_email")
async def send_email(ctx, payload):
    """Send email notification."""
    logger = ctx["logger"]
    job = ctx["job"]
    
    to_email = payload.get("to")
    subject = payload.get("subject")
    body = payload.get("body")
    
    logger.info(f"Sending email to {to_email}: {subject}")
    # Implementation would go here
    logger.info(f"Email sent successfully for job {job.id}")


@job_registry.handler("send_sms")
async def send_sms(ctx, payload):
    """Send SMS notification."""
    logger = ctx["logger"]
    job = ctx["job"]
    
    phone = payload.get("phone")
    message = payload.get("message")
    
    logger.info(f"Sending SMS to {phone}")
    # Implementation would go here
    logger.info(f"SMS sent successfully for job {job.id}")
