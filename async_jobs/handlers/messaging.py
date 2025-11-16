"""Example messaging handlers."""

from async_jobs.registry import job_registry


@job_registry.handler("classify_message")
async def classify_message(ctx, payload):
    """Classify message content."""
    logger = ctx["logger"]
    job = ctx["job"]
    
    message_id = payload.get("message_id")
    content = payload.get("content")
    
    logger.info(f"Classifying message {message_id}")
    # ML classification would go here
    logger.info(f"Message classified successfully for job {job.id}")


@job_registry.handler("extract_entities")
async def extract_entities(ctx, payload):
    """Extract entities from message."""
    logger = ctx["logger"]
    job = ctx["job"]
    
    message_id = payload.get("message_id")
    text = payload.get("text")
    
    logger.info(f"Extracting entities from message {message_id}")
    # NER would go here
    logger.info(f"Entities extracted successfully for job {job.id}")
