"""Example notification handlers."""

from async_jobs.registry import job_registry


@job_registry.handler("send_notification")
async def send_notification(ctx, payload):
    """
    Example handler for sending notifications.

    Args:
        ctx: Context dict with job_id, tenant_id, use_case, attempt
        payload: Job payload dict
    """
    email = payload.get("email")
    template = payload.get("template", "default")

    # Example: Send email notification
    print(f"Sending {template} notification to {email} for tenant {ctx['tenant_id']}")

    # In real implementation, this would call an email service
    # await email_service.send(email, template)


@job_registry.handler("send_bulk_notification")
async def send_bulk_notification(ctx, payload):
    """Example handler for bulk notifications."""
    recipients = payload.get("recipients", [])
    template = payload.get("template")

    print(f"Sending bulk {template} notification to {len(recipients)} recipients")

    # In real implementation, this would send to multiple recipients
    # for recipient in recipients:
    #     await email_service.send(recipient, template)
