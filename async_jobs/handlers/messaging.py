"""Example messaging handlers."""

from async_jobs.registry import job_registry


@job_registry.handler("label_message")
async def label_message(ctx, payload):
    """
    Example handler for message labeling.

    Args:
        ctx: Context dict with job_id, tenant_id, use_case, attempt
        payload: Job payload dict
    """
    message_id = payload.get("message_id")
    labels = payload.get("labels", [])

    print(f"Labeling message {message_id} with labels {labels} for tenant {ctx['tenant_id']}")

    # In real implementation, this would call a labeling service
    # await labeling_service.label(message_id, labels)
