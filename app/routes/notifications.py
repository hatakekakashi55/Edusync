"""
EduSync Backend - Notifications Routes
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

router = APIRouter(tags=["Notifications"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/notifications", tags=["Notifications"])
async def get_notifications(
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get user notifications"""
    try:
        user_id = str(current_user["_id"])
        
        query = {
            "$or": [
                {"user_id": user_id},
                {"broadcast": True}
            ]
        }
        
        if unread_only:
            query["read"] = {"$in": [False]}
        
        total = await notifications_collection.count_documents(query)
        
        notifications = await notifications_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "notifications": [
                {
                    "id": str(n["_id"]),
                    "title": n["title"],
                    "message": n["message"],
                    "type": n["type"],
                    "priority": n.get("priority", "normal"),
                    "created_at": n["created_at"],
                    "read": n.get("read", False),
                    "action_url": n.get("action_url"),
                    "data": n.get("data", {})
                }
                for n in notifications
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            },
            "unread_count": await notifications_collection.count_documents({
                "$or": [
                    {"user_id": user_id},
                    {"broadcast": True}
                ],
                "read": False
            })
        }
        
    except Exception as e:
        logger.error(f"Get notifications error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get notifications")


@router.post("/api/notifications/{notification_id}/read", tags=["Notifications"])
async def mark_notification_read(
    notification_id: str,
    current_user: dict = Depends(verify_token)
):
    """Mark notification as read"""
    try:
        user_id = str(current_user["_id"])
        
        result = await notifications_collection.update_one(
            {
                "_id": ObjectId(notification_id),
                "$or": [
                    {"user_id": user_id},
                    {"broadcast": True}
                ]
            },
            {"$set": {"read": True}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        return {"message": "Notification marked as read"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mark notification read error: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark notification as read")


@router.post("/api/notifications/read-all", tags=["Notifications"])
async def mark_all_notifications_read(current_user: dict = Depends(verify_token)):
    """Mark all notifications as read"""
    try:
        user_id = str(current_user["_id"])
        
        await notifications_collection.update_many(
            {
                "$or": [
                    {"user_id": user_id},
                    {"broadcast": True}
                ],
                "read": False
            },
            {"$set": {"read": True}}
        )
        
        return {"message": "All notifications marked as read"}
        
    except Exception as e:
        logger.error(f"Mark all notifications read error: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark all notifications as read")


