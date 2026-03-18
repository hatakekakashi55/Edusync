"""
EduSync Backend - Pair Programming Routes
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
from app.services.notification_service import NotificationService
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

router = APIRouter(tags=["Pair Programming"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/pair-programming/sessions", tags=["Pair Programming"])
async def create_pair_programming_session(
    session_data: PairProgrammingRequest,
    current_user: dict = Depends(verify_token)
):
    """Create a pair programming session"""
    try:
        user_id = str(current_user["_id"])
        partner_id = session_data.partner_id
        
        # Check if partner exists
        partner = await users_collection.find_one({"_id": ObjectId(partner_id)})
        if not partner:
            raise HTTPException(status_code=404, detail="Partner not found")
        
        # Check if partner is available (simplified check)
        # In production, you'd check for active sessions
        
        session_id = str(uuid.uuid4())
        
        session = {
            "session_id": session_id,
            "user1_id": user_id,
            "user2_id": partner_id,
            "language": session_data.language,
            "duration": session_data.session_duration,
            "status": "pending",  # pending, active, completed, cancelled
            "created_at": datetime.now(timezone.utc),
            "started_at": None,
            "ended_at": None,
            "code": "",
            "cursor_positions": {},
            "chat_messages": []
        }
        
        await pair_programming_collection.insert_one(session)
        
        # Send invitation to partner
        await NotificationService.create_notification(
            user_id=partner_id,
            title="Pair Programming Invitation",
            message=f"{current_user['full_name']} has invited you to a pair programming session in {session_data.language}",
            notification_type="pair_programming",
            priority="high",
            action_url=f"/pair-programming/{session_id}",
            data={
                "session_id": session_id,
                "inviter_id": user_id,
                "inviter_name": current_user["full_name"],
                "language": session_data.language,
                "duration": session_data.session_duration
            }
        )
        
        return {
            "message": "Pair programming session created",
            "session_id": session_id,
            "status": "pending"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create pair programming session error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session")


