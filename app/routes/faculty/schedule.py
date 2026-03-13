"""
EduSync Backend - Faculty - Schedule Routes
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

router = APIRouter(tags=["Faculty - Schedule"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/faculty/schedule", tags=["Faculty"])
async def get_faculty_schedule(
    day: Optional[str] = None,
    classroom_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get faculty schedule"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        query = {"instructor_id": user_id}
        
        if day:
            query["day"] = day.lower()
        
        if classroom_id:
            query["classroom_id"] = classroom_id
        
        total = await faculty_schedule_collection.count_documents(query)
        
        schedules = await faculty_schedule_collection.find(query) \
            .sort("start_time", 1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "schedule": [
                {
                    "id": str(sch["_id"]),
                    "classroom_code": sch["classroom_code"],
                    "subject": sch["subject"],
                    "day": sch["day"],
                    "start_time": sch["start_time"],
                    "end_time": sch["end_time"],
                    "type": sch["type"],
                    "location": sch.get("location"),
                    "recurrence": sch["recurrence"]
                }
                for sch in schedules
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get faculty schedule error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get schedule")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.post("/api/faculty/schedule", tags=["Faculty"])
async def create_schedule(
    schedule_data: ScheduleCreate,
    current_user: dict = Depends(verify_token)
):
    """Create a new schedule entry"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        # Verify classroom ownership
        classroom = await faculty_classrooms_collection.find_one({
            "_id": ObjectId(schedule_data.classroom_id),
            "instructor_id": user_id
        })
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found")
        
        schedule = {
            "classroom_id": schedule_data.classroom_id,
            "classroom_code": classroom["code"],
            "subject": schedule_data.subject,
            "day": schedule_data.day,
            "start_time": schedule_data.start_time,
            "end_time": schedule_data.end_time,
            "type": schedule_data.type,
            "location": schedule_data.location,
            "recurrence": schedule_data.recurrence,
            "description": schedule_data.description,
            "instructor_id": user_id,
            "instructor_name": current_user["full_name"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "status": "active"
        }
        
        result = await faculty_schedule_collection.insert_one(schedule)
        schedule_id = str(result.inserted_id)
        
        return {
            "message": "Schedule created successfully",
            "schedule_id": schedule_id,
            "schedule": schedule
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create schedule error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create schedule")


