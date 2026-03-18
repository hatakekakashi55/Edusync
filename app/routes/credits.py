"""
EduSync Backend - Credits Routes
Auto-extracted from main.py via AST parser.
"""
import logging
import os
import re
import json
import uuid
import io
import base64
import random
import asyncio
import hashlib
import tempfile
import subprocess
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict, Any
from pathlib import Path
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query, Body, BackgroundTasks, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, Response

from app.dependencies import get_current_user, verify_token, convert_objectid_to_str, create_access_token, create_refresh_token
from app.database import *
from app.services.ai_wrapper import gemini_model, get_gemini_model, get_faculty_gemini_model, hod_gemini_model, faculty_gemini_models, AIModelWrapper
from app.services.notification_service import NotificationService
from app.lifespan import get_redis_client, get_executor
from app.config import *

# Import all models
from app.models.auth import *
from app.models.challenge import *
from app.models.classroom import *
from app.models.communication import *
from app.models.career import *
from app.models.group import *
from app.models.ai import *
from app.models.hod import *
from app.models.curriculum import *
from app.models.resource import *
from app.models.report import *
from app.models.credit import *
from app.models.compiler import *
from app.models.speech import *
from app.models.faculty import *

# Import helper functions
from app.utils.helpers import *

logger = logging.getLogger("edusync")

router = APIRouter(tags=["Credits"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/credits/award", tags=["Credits"])
async def award_credits(
    credit_data: CreditAward,
    current_user: dict = Depends(verify_token)
):
    """Award credits for completing tasks - supports both legacy and new formats"""
    try:
        # Handle both old format (credits, source) and new format (task_type, task_data)
        if credit_data.credits is not None:
            # Legacy format: credits, source, details
            credits = credit_data.credits
            task_type = credit_data.source or "voice_challenge"
            task_data = {"details": credit_data.details or ""}
        else:
            # New format: task_type, task_data
            task_type = credit_data.task_type or "coding_challenge"
            task_data = credit_data.task_data or {}
        
        logger.info(f"📊 Award credits request: task_type={task_type}, user={current_user.get('email')}")
        
        user_id = str(current_user["_id"])
        
        # Credit configuration
        CREDIT_CONFIG = {
            "daily_login": {"base": 10, "bonus": 70, "conditions": {"max_per_day": 1}},
            "voice_challenge": {"base": 50, "per_percentage": 0.5},
            "reading_challenge": {"base": 50, "per_percentage": 0.5},
            "listening_challenge": {"base": 50, "per_percentage": 0.5},
            "writing_challenge": {"base": 75, "per_percentage": 0.5},
            "coding_challenge": {"base": 75, "per_star": 25},
            "project_completion": {"base": 200, "bonus": 50},
            "badge_earned": {"base": 100},
            "streak_extension": {"base": 70},
            "lesson_completion": {"base": 30},
            "quiz_completion": {"base": 20, "per_correct": 2},
            "peer_review": {"base": 40},
            "profile_completion": {"base": 50}
        }
        
        if task_type not in CREDIT_CONFIG:
            logger.warning(f"⚠️ Unknown task type: {task_type}. Using default coding_challenge config.")
            task_type = "coding_challenge"
        
        config = CREDIT_CONFIG[task_type]
        
        # For legacy format with pre-calculated credits, use those directly
        if credit_data.credits is not None:
            credits = credit_data.credits
        else:
            # Calculate based on task_data
            credits = config.get("base", 0)
        
        # Calculate additional credits based on task data
        if task_type == "voice_challenge":
            score = task_data.get("score", 0)
            credits += int(score * config.get("per_percentage", 0))
        
        elif task_type == "coding_challenge":
            stars = task_data.get("stars", 0)
            credits += stars * config.get("per_star", 0)
            
            # Bonus for difficulty
            difficulty = task_data.get("difficulty", "easy")
            if difficulty == "medium":
                credits += 25
            elif difficulty == "hard":
                credits += 50
            elif difficulty == "expert":
                credits += 100
        
        elif task_type == "quiz_completion":
            correct_answers = task_data.get("correct_answers", 0)
            credits += correct_answers * config.get("per_correct", 0)
        
        elif task_type == "project_completion":
            if task_data.get("completed"):
                credits += config.get("bonus", 0)
        
        # Check for daily limits
        if task_type == "daily_login":
            today = datetime.now(timezone.utc).date()
            start_of_day = datetime.combine(today, datetime.min.time())
            
            # Check if already awarded today
            existing = await credit_transactions_collection.count_documents({
                "user_id": user_id,
                "source": "daily_login",
                "created_at": {"$gte": start_of_day}
            })
            
            if existing >= config["conditions"]["max_per_day"]:
                return {
                    "success": False,
                    "message": "Daily login credits already awarded",
                    "awarded_credits": 0,
                    "new_credits": current_user.get("credits", 0)
                }
        
        # Award credits
        success = await update_user_credits(
            user_id=user_id,
            amount=credits,
            source=task_type,
            description=f"Credits awarded for {task_type.replace('_', ' ')}",
            metadata=task_data
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to award credits")
        
        # Get updated user data
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        
        new_credits = user.get("credits", 0) if user else 0
        
        return {
            "success": True,
            "message": f"Awarded {credits} credits",
            "awarded_credits": credits,
            "new_credits": new_credits,
            "xp_earned": credits * 2
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Award credits error: {e}")
        raise HTTPException(status_code=500, detail="Failed to award credits")


@router.get("/api/credits/summary", tags=["Credits"])
async def get_credits_summary(
    current_user: dict = Depends(verify_token)
):
    """Get user's credit summary"""
    try:
        user_id = str(current_user["_id"])
        summary = await get_user_credits_summary(user_id)
        
        if not summary:
            raise HTTPException(status_code=404, detail="User not found")
        
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get credits summary error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get credits summary")


@router.get("/api/credits/transactions", tags=["Credits"])
async def get_credit_transactions(
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get user's credit transactions"""
    try:
        user_id = str(current_user["_id"])
        
        total = await credit_transactions_collection.count_documents({"user_id": user_id})
        
        transactions = await credit_transactions_collection.find(
            {"user_id": user_id}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
        
        return {
            "transactions": convert_objectid_to_str(transactions),
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get transactions error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get transactions")


@router.post("/api/credits/transfer", tags=["Credits"])
async def transfer_credits(
    recipient_id: str = Form(...),
    amount: int = Form(..., ge=10, le=1000),
    message: Optional[str] = Form(None),
    current_user: dict = Depends(verify_token)
):
    """Transfer credits to another user"""
    try:
        sender_id = str(current_user["_id"])
        
        # Check if transferring to self
        if sender_id == recipient_id:
            raise HTTPException(status_code=400, detail="Cannot transfer to yourself")
        
        # Check sender has enough credits
        sender = await users_collection.find_one({"_id": ObjectId(sender_id)})
        if not sender or sender.get("credits", 0) < amount:
            raise HTTPException(status_code=400, detail="Insufficient credits")
        
        # Check recipient exists
        recipient = await users_collection.find_one({"_id": ObjectId(recipient_id)})
        if not recipient:
            raise HTTPException(status_code=404, detail="Recipient not found")
        
        # Perform transfer (atomic operation would be better with transactions)
        # For now, we'll update one by one
        
        # Deduct from sender
        await users_collection.update_one(
            {"_id": ObjectId(sender_id)},
            {"$inc": {"credits": -amount}}
        )
        
        # Add to recipient
        await users_collection.update_one(
            {"_id": ObjectId(recipient_id)},
            {"$inc": {"credits": amount}}
        )
        
        # Log sender transaction
        sender_transaction = {
            "user_id": sender_id,
            "amount": -amount,
            "transaction_type": "transfer",
            "source": "credit_transfer",
            "description": f"Transferred to {recipient.get('full_name', 'User')}" + (f": {message}" if message else ""),
            "metadata": {"recipient_id": recipient_id, "recipient_name": recipient.get("full_name")},
            "created_at": datetime.now(timezone.utc)
        }
        await credit_transactions_collection.insert_one(sender_transaction)
        
        # Log recipient transaction
        recipient_transaction = {
            "user_id": recipient_id,
            "amount": amount,
            "transaction_type": "transfer",
            "source": "credit_transfer",
            "description": f"Received from {sender.get('full_name', 'User')}" + (f": {message}" if message else ""),
            "metadata": {"sender_id": sender_id, "sender_name": sender.get("full_name")},
            "created_at": datetime.now(timezone.utc)
        }
        await credit_transactions_collection.insert_one(recipient_transaction)
        
        # Send notification to recipient
        await NotificationService.create_notification(
            user_id=recipient_id,
            title="💰 Credits Received",
            message=f"You received {amount} credits from {sender['full_name']}",
            notification_type="credit_transfer",
            priority="medium",
            data={"amount": amount, "sender": sender["full_name"]}
        )
        
        return {
            "success": True,
            "message": f"Successfully transferred {amount} credits",
            "amount": amount,
            "recipient": recipient.get("full_name"),
            "sender_balance": sender.get("credits", 0) - amount,
            "recipient_balance": recipient.get("credits", 0) + amount
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transfer credits error: {e}")
        raise HTTPException(status_code=500, detail="Failed to transfer credits")


@router.post("/api/credits/spend", tags=["Credits"])
async def spend_credits(
    item_id: str = Form(...),
    item_name: str = Form(...),
    amount: int = Form(..., gt=0),
    current_user: dict = Depends(verify_token)
):
    """Spend credits on items"""
    try:
        user_id = str(current_user["_id"])
        
        # Check user has enough credits
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user or user.get("credits", 0) < amount:
            raise HTTPException(status_code=400, detail="Insufficient credits")
        
        # Deduct credits
        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {"credits": -amount}}
        )
        
        # Log transaction
        transaction = {
            "user_id": user_id,
            "amount": -amount,
            "transaction_type": "purchase",
            "source": "marketplace",
            "description": f"Purchased: {item_name}",
            "metadata": {"item_id": item_id, "item_name": item_name},
            "created_at": datetime.now(timezone.utc)
        }
        await credit_transactions_collection.insert_one(transaction)
        
        # Record purchase
        purchase_record = {
            "user_id": user_id,
            "item_id": item_id,
            "item_name": item_name,
            "amount": amount,
            "purchased_at": datetime.now(timezone.utc)
        }
        await db.purchases.insert_one(purchase_record)
        
        return {
            "success": True,
            "message": f"Successfully purchased {item_name}",
            "amount": amount,
            "remaining_credits": user.get("credits", 0) - amount,
            "purchase_id": str(purchase_record["_id"])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Spend credits error: {e}")
        raise HTTPException(status_code=500, detail="Failed to spend credits")


