"""
EduSync Backend - Learning Paths Routes
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
from app.services.ai_service import AIService
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

router = APIRouter(tags=["Learning Paths"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/learning-paths/generate", tags=["Learning Path"])
async def generate_learning_path(
    request: LearningPathRequest,
    current_user: dict = Depends(verify_token)
):
    """Generate personalized learning path"""
    try:
        user_id = str(current_user["_id"])
        
        # Get user data
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Generate learning path with AI
        learning_path = await AIService.generate_learning_path({
            "stage": user.get("stage", "freshie"),
            "department": user.get("department", "Computer Science"),
            "skills": user.get("skills", []),
            "weak_areas": request.focus_areas,
            "interests": user.get("interests", []),
            "career_goals": request.goals
        })
        
        # If AI service fails, return a basic template
        if not learning_path:
            learning_path = generate_default_learning_path(
                request.focus_areas,
                request.duration_days,
                request.goals
            )
        
        # Save learning path
        path_id = str(uuid.uuid4())
        path_doc = {
            "id": path_id,
            "user_id": user_id,
            "focus_areas": request.focus_areas,
            "goals": request.goals,
            "duration_days": request.duration_days,
            "learning_path": learning_path,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "current_day": 1,
            "completed_days": [],
            "progress": 0
        }
        
        await learning_paths_collection.insert_one(path_doc)
        
        return {
            "message": "Learning path generated successfully",
            "path_id": path_id,
            "learning_path": learning_path
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate learning path error: {e}")
        # Fallback to default learning path
        return {
            "message": "AI service temporarily unavailable. Using default template.",
            "path_id": str(uuid.uuid4()),
            "learning_path": generate_default_learning_path(
                request.focus_areas if hasattr(request, 'focus_areas') else ["Programming"],
                request.duration_days if hasattr(request, 'duration_days') else 30,
                request.goals if hasattr(request, 'goals') else []
            )
        }


@router.get("/api/learning-paths", tags=["Learning Path"])
async def get_learning_paths(
    limit: int = Query(10, ge=1, le=50),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get user's learning paths"""
    try:
        user_id = str(current_user["_id"])
        
        total = await learning_paths_collection.count_documents({"user_id": user_id})
        
        paths = await learning_paths_collection.find({"user_id": user_id}) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "learning_paths": [
                {
                    "id": p["id"],
                    "focus_areas": p["focus_areas"],
                    "goals": p["goals"],
                    "duration_days": p["duration_days"],
                    "current_day": p["current_day"],
                    "progress": p["progress"],
                    "created_at": p["created_at"],
                    "overview": p["learning_path"].get("overview", "")[:200] + "..."
                }
                for p in paths
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get learning paths error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get learning paths")


