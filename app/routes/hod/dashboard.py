"""
EduSync Backend - HOD - Dashboard Routes
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

router = APIRouter(tags=["HOD - Dashboard"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/hod/academic-calendar", tags=["HOD - Curriculum"])
async def create_academic_calendar_entry(
    calendar_data: AcademicCalendarCreate,
    current_user: dict = Depends(verify_token)
):
    """Add entry to academic calendar"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        calendar_entry = {
            "event_name": calendar_data.event_name,
            "event_type": calendar_data.event_type,
            "start_date": calendar_data.start_date,
            "end_date": calendar_data.end_date,
            "description": calendar_data.description,
            "venue": calendar_data.venue,
            "target_audience": calendar_data.target_audience,
            "department": department,
            "created_by": str(current_user["_id"]),
            "created_by_name": current_user["full_name"],
            "created_at": datetime.now(timezone.utc),
            "status": "upcoming"
        }
        
        result = await db.academic_calendar.insert_one(calendar_entry)
        
        return {
            "message": "Calendar entry created successfully",
            "entry_id": str(result.inserted_id),
            "entry": convert_objectid_to_str(calendar_entry)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create calendar entry error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create calendar entry")


@router.get("/api/hod/dashboard", tags=["HOD"])
async def get_hod_dashboard(
    current_user: dict = Depends(verify_token)
):
    """Get HOD dashboard data"""
    try:
        # Verify user is HOD
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        user_id = str(current_user["_id"])
        
        # Get department statistics
        department_stats = await calculate_department_stats(department, f"{datetime.now().year}-{datetime.now().year + 1}")
        
        if not department_stats:
            raise HTTPException(status_code=500, detail="Failed to load department stats")
        
        # Get faculty quick view
        faculty_list = await users_collection.find({
            "user_type": UserType.FACULTY.value,
            "department": department,
            "is_active": True
        }).limit(10).to_list(10)
        
        faculty_data = []
        for faculty in faculty_list:
            stats = await get_faculty_stats(str(faculty["_id"]))
            if stats:
                faculty_data.append(stats)
        
        # Get recent notifications
        recent_notifications = await notifications_collection.find({
            "user_id": user_id
        }).sort("created_at", -1).limit(5).to_list(5)
        
        # Get pending approvals count
        pending_approvals = await notifications_collection.count_documents({
            "user_id": user_id,
            "type": "approval",
            "read": False
        })
        
        # Get upcoming meetings
        upcoming_meetings = await events_collection.find({
            "department": department,
            "type": "meeting",
            "date": {"$gte": datetime.now(timezone.utc)}
        }).sort("date", 1).limit(5).to_list(5)
        
        # Convert ObjectId to string for all data
        result = {
            "user": {
                "id": user_id,
                "name": current_user["full_name"],
                "department": department,
                "role": "Head of Department"
            },
            "department_stats": convert_objectid_to_str(department_stats),
            "faculty_quick_view": convert_objectid_to_str(faculty_data[:3]),  # Only show 3 for quick view
            "recent_notifications": convert_objectid_to_str(recent_notifications),
            "pending_approvals": pending_approvals,
            "upcoming_meetings": convert_objectid_to_str(upcoming_meetings),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HOD dashboard error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load HOD dashboard")


@router.get("/api/hod/management-options", tags=["HOD"])
async def get_hod_management_options(
    current_user: dict = Depends(verify_token)
):
    """Get all management options and their data for HOD"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        user_id = str(current_user["_id"])
        
        # Get comprehensive data for all management options
        return {
            "faculty": await get_faculty_management_data(department),
            "curriculum": await get_curriculum_data(department),
            "analytics": await get_comprehensive_analytics(department),
            "approvals": await get_pending_approvals_data(user_id),
            "resources": await get_department_resources(department),
            "reports": await get_report_templates(department),
            "settings": await get_department_settings(department)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get management options error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load management options")


