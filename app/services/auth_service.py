"""
EduSync Backend - Auth Service Middleware
Credit protection middleware for AI features.
"""
import logging
from typing import Optional
from fastapi import HTTPException

from app.services.subscription_service import SubscriptionService
from app.models.subscription import CREDIT_COSTS

logger = logging.getLogger("edusync")


async def require_edu_credits(user_id: str, task_type: str) -> dict:
    """
    Middleware-style function to check subscription validity and 
    EduCredit balance before allowing access to AI features.
    
    Called at the start of AI service functions:
        check = await require_edu_credits(user_id, "ai_roleplay")
        if not check["allowed"]:
            raise HTTPException(status_code=402, detail=check["error"])
    
    Returns:
        dict with keys: allowed (bool), error (str), available (int), required (int)
    """
    required_credits = CREDIT_COSTS.get(task_type, 10)
    
    result = await SubscriptionService.check_subscription_and_credits(
        user_id=user_id,
        required_credits=required_credits,
    )
    
    return result


async def consume_credits_for_task(user_id: str, task_type: str, metadata: dict = None) -> dict:
    """
    Consume EduCredits after a task is completed.
    
    Call this after the AI task finishes successfully:
        result = await consume_credits_for_task(user_id, "code_compilation", {"language": "python"})
    
    Returns:
        dict with keys: success (bool), credits_consumed (int), remaining_credits (int)
    """
    return await SubscriptionService.consume_credits(
        user_id=user_id,
        task_type=task_type,
        metadata=metadata,
    )
