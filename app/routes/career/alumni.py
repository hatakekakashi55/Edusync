"""
EduSync Backend - Career - Alumni Routes
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

router = APIRouter(tags=["Career - Alumni"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/alumni/network")
async def get_alumni_network(current_user: dict = Depends(verify_token)):
    """Get alumni network for mentorship"""
    try:
        # Find users with role 'alumni' or stage 'alumni'
        alumni = await users_collection.find({
            "$or": [
                {"role": "alumni"},
                {"stage": "alumni"}
            ]
        }).to_list(length=50)
        
        alumni_list = []
        for alum in alumni:
            alumni_list.append({
                "id": str(alum["_id"]),
                "name": alum.get("full_name", "Alumni"),
                "role": alum.get("role", "Professional"),
                "company": alum.get("company", "Tech Company"),
                "graduation_year": alum.get("graduation_year", 2020),
                "department": alum.get("department", "Computer Science"),
                "skills": alum.get("skills", []),
                "available_for_mentorship": True,
                "linkedin_url": f"https://linkedin.com/in/{alum.get('full_name', 'user').lower().replace(' ', '-')}"
            })
        
        return {"alumni": alumni_list}
    except Exception as e:
        logger.error(f"Alumni network error: {e}")
        return {"alumni": []}


@router.post("/api/alumni/connect", tags=["Career"])
async def connect_with_alumni(
    alumni_id: str = Form(...),
    message: str = Form(...),
    current_user: dict = Depends(verify_token)
):
    """Connect with alumni for mentorship"""
    try:
        user_id = str(current_user["_id"])
        
        # Create connection request
        connection = {
            "user_id": user_id,
            "user_name": current_user["full_name"],
            "alumni_id": alumni_id,
            "message": message,
            "status": "pending",
            "requested_at": datetime.now(timezone.utc),
            "department": current_user.get("department")
        }
        
        await db.alumni_connections.insert_one(connection)
        
        return {
            "success": True,
            "message": "Connection request sent successfully!",
            "connection_id": str(connection["_id"])
        }
        
    except Exception as e:
        logger.error(f"Connect with alumni error: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect with alumni")


