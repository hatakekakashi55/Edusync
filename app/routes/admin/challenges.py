"""
EduSync Backend - Admin - Challenges Routes
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
from app.services.websocket_manager import WebSocketManager

logger = logging.getLogger("edusync")

router = APIRouter(tags=["Admin - Challenges"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/admin/challenges/create", tags=["Challenges"])
async def create_challenge(challenge: ChallengeCreate, current_user: dict = Depends(get_current_user)):
    """Create a new challenge"""
    try:
        logger.info(f"Creating challenge: {challenge.title} by user {current_user.get('email')}")
        
        if current_user.get("user_type") != "admin":
            logger.warning(f"Non-admin user {current_user.get('email')} tried to create challenge")
            raise HTTPException(status_code=403, detail="Admin access required")
        
        new_challenge = challenge.model_dump()
        new_challenge["created_at"] = datetime.now(timezone.utc)
        new_challenge["created_by"] = str(current_user["_id"])
        
        logger.info(f"Inserting challenge into database: {new_challenge['title']}")
        result = await challenges_collection.insert_one(new_challenge)
        
        # Broadcast real-time update to all connected students
        try:
            await WebSocketManager.broadcast({
                "type": "challenge_created",
                "data": {
                    "challenge_id": str(result.inserted_id),
                    "title": challenge.title,
                    "stage": challenge.stage,
                    "challenge_type": challenge.challenge_type,
                    "difficulty": challenge.difficulty,
                    "credits_reward": challenge.credits_reward,
                    "description": challenge.description,
                    "created_at": datetime.now(timezone.utc).isoformat()
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as ws_err:
            logger.error(f"WebSocket broadcast error: {ws_err}")

        return {
            "success": True,
            "challenge_id": str(result.inserted_id),
            "message": "Challenge created successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating challenge: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating challenge: {str(e)}")


@router.get("/api/admin/challenges", tags=["Challenges"])
async def get_admin_challenges(stage: str = Query(None), challenge_type: str = Query(None), current_user: dict = Depends(get_current_user)):
    """Get all challenges for admin (including inactive)"""
    try:
        logger.info(f"Admin {current_user.get('email')} fetching challenges - stage: {stage}, type: {challenge_type}")
        
        if current_user.get("user_type") != "admin":
            logger.warning(f"Non-admin user {current_user.get('email')} tried to access admin challenges")
            raise HTTPException(status_code=403, detail="Admin access required")
        
        query = {}
        if stage:
            query["stage"] = stage
        if challenge_type:
            query["challenge_type"] = challenge_type
            
        challenges_cursor = challenges_collection.find(query).sort("created_at", -1)
        challenges = await challenges_cursor.to_list(length=200)
        
        logger.info(f"✅ Found {len(challenges)} challenges for admin")
        return [convert_objectid_to_str(c) for c in challenges]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching admin challenges: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching challenges: {str(e)}")


@router.delete("/api/admin/challenges/{challenge_id}", tags=["Challenges"])
async def delete_challenge(challenge_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a challenge (admin only)"""
    try:
        logger.info(f"Admin {current_user.get('email')} deleting challenge: {challenge_id}")
        
        if current_user.get("user_type") != "admin":
            logger.warning(f"Non-admin user {current_user.get('email')} tried to delete challenge")
            raise HTTPException(status_code=403, detail="Admin access required")
        
        if not ObjectId.is_valid(challenge_id):
            raise HTTPException(status_code=400, detail="Invalid challenge ID")
        
        result = await challenges_collection.delete_one({"_id": ObjectId(challenge_id)})
        
        if result.deleted_count == 0:
            logger.warning(f"Challenge {challenge_id} not found for deletion")
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        logger.info(f"✅ Challenge {challenge_id} deleted successfully")
        return {"success": True, "message": "Challenge deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting challenge: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error deleting challenge: {str(e)}")


