"""Example messaging handlers."""
import logging
from typing import Any, Dict

from async_jobs.models import JobContext
from async_jobs.registry import job_registry

logger = logging.getLogger(__name__)


@job_registry.handler("label_message")
async def label_message(ctx: JobContext, payload: Dict[str, Any]):
    """Label a message using ML models."""
    logger.info(f"Labeling message for job {ctx.job_id}, tenant {ctx.tenant_id}")
    logger.info(f"Payload: {payload}")
    
    message_id = payload.get("message_id")
    message_text = payload.get("message_text")
    
    logger.info(f"Message ID: {message_id}")
    logger.info(f"Message text: {message_text[:100]}...")
    
    # Example: In a real implementation, this would call ML models to classify the message
    # Simulate labeling
    labels = {
        "sentiment": "positive",
        "category": "support",
        "priority": "medium",
        "language": "en",
    }
    
    logger.info(f"Generated labels: {labels}")
    
    return {"status": "labeled", "message_id": message_id, "labels": labels}


@job_registry.handler("analyze_conversation")
async def analyze_conversation(ctx: JobContext, payload: Dict[str, Any]):
    """Analyze a conversation thread."""
    logger.info(f"Analyzing conversation for job {ctx.job_id}, tenant {ctx.tenant_id}")
    
    conversation_id = payload.get("conversation_id")
    messages = payload.get("messages", [])
    
    logger.info(f"Conversation ID: {conversation_id}, message count: {len(messages)}")
    
    # Simulate conversation analysis
    analysis = {
        "summary": "Customer inquiry about product features",
        "sentiment": "neutral",
        "action_required": False,
        "topics": ["product", "features", "pricing"],
    }
    
    logger.info(f"Analysis complete: {analysis}")
    
    return {"status": "analyzed", "conversation_id": conversation_id, "analysis": analysis}
