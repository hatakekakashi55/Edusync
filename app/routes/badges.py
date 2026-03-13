"""
EduSync Backend - Badges Routes
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

router = APIRouter(tags=["Badges"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/badges", tags=["Badges"])
async def get_badges(current_user: dict = Depends(verify_token)):
    """Get user badges"""
    try:
        user_id = str(current_user["_id"])
        
        badges_doc = await badges_collection.find_one({"user_id": user_id})
        
        if not badges_doc:
            return {
                "badges": [],
                "total_badges": 0,
                "categories": {}
            }
        
        badges = badges_doc.get("badges", [])
        
        # Group by category
        categories = {}
        for badge in badges:
            category = badge.get("category", "uncategorized")
            if category not in categories:
                categories[category] = []
            categories[category].append(badge)
        
        return {
            "badges": badges,
            "total_badges": len(badges),
            "categories": categories
        }
        
    except Exception as e:
        logger.error(f"Get badges error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get badges")


