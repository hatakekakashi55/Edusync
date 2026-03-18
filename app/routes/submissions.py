"""
EduSync Backend - Submissions Routes
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

router = APIRouter(tags=["Submissions"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/submissions", tags=["Submissions"])
async def get_submissions(
    challenge_id: Optional[str] = None,
    completed: Optional[bool] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get user submissions"""
    try:
        user_id = str(current_user["_id"])
        
        query = {"user_id": user_id}
        
        if challenge_id:
            query["challenge_id"] = challenge_id
        if completed is not None:
            query["completed"] = {"$in": [completed]}
        
        total = await submissions_collection.count_documents(query)
        
        submissions = await submissions_collection.find(query) \
            .sort("submitted_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "submissions": [
                {
                    "id": str(sub["_id"]),
                    "challenge_id": sub["challenge_id"],
                    "challenge_title": sub["challenge_title"],
                    "challenge_type": sub["challenge_type"],
                    "score": sub.get("score", 0),
                    "completed": sub.get("completed", False),
                    "submitted_at": sub.get("submitted_at"),
                    "credits_earned": sub.get("credits_earned", 0),
                    "language": sub.get("language"),
                    "has_feedback": "ai_feedback" in sub
                }
                for sub in submissions
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get submissions error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get submissions")


