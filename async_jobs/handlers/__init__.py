"""Sample job handlers."""

from async_jobs.registry import job_registry


@job_registry.handler("send_notification")
async def send_notification(ctx, payload):
    """
    Sample handler for sending notifications.

    Args:
        ctx: Context dict with job and logger
        payload: Job payload dict
    """
    logger = ctx["logger"]
    job = ctx["job"]

    logger.info(f"Sending notification for job {job.id}")

    # Extract payload fields
    email = payload.get("email")
    template = payload.get("template")

    logger.info(f"Notification: email={email}, template={template}")

    # Simulate sending notification
    # In real implementation, this would call email service, push notification service, etc.

    logger.info(f"Notification sent successfully for job {job.id}")


@job_registry.handler("label_message")
async def label_message(ctx, payload):
    """
    Sample handler for message labeling.

    Args:
        ctx: Context dict with job and logger
        payload: Job payload dict
    """
    logger = ctx["logger"]
    job = ctx["job"]

    logger.info(f"Labeling message for job {job.id}")

    # Extract payload fields
    message_id = payload.get("message_id")
    labels = payload.get("labels", [])

    logger.info(f"Message labeling: message_id={message_id}, labels={labels}")

    # Simulate labeling
    # In real implementation, this would call ML service, database update, etc.

    logger.info(f"Message labeled successfully for job {job.id}")
