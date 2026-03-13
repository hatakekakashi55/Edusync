"""
EduSync Backend - HOD - Faculty Routes
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
import secrets
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

router = APIRouter(tags=["HOD - Faculty"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/hod/faculty", tags=["HOD"])
async def add_faculty_hod(
    faculty_data: FacultyCreate,
    current_user: dict = Depends(verify_token)
):
    """Add new faculty (HOD only)"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        # Check if email exists
        existing = await users_collection.find_one({"email": faculty_data.email})
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Generate temporary password
        temp_password = secrets.token_urlsafe(12)
        
        # Create faculty user
        faculty_user = {
            "email": faculty_data.email,
            "full_name": faculty_data.name,
            "user_type": UserType.FACULTY.value,
            "department": faculty_data.department,
            "designation": faculty_data.designation,
            "expertise": [faculty_data.specialization],
            "password": hash_password(temp_password),
            "is_active": True,
            "is_verified": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "profile_picture": None,
            "phone": None,
            "office": f"Block {random.choice(['A', 'B', 'C'])} - {random.randint(101, 410)}",
            "office_hours": "10:00 AM - 4:00 PM",
            "qualifications": ["Ph.D. in Computer Science"],  # Default
            "publications": [],
            "research_areas": [faculty_data.specialization],
            "courses_teaching": [],
            "bio": f"Faculty member specializing in {faculty_data.specialization}",
            "joining_date": datetime.now(timezone.utc).date().isoformat(),
            "status": "active"
        }
        
        result = await users_collection.insert_one(faculty_user)
        faculty_id = str(result.inserted_id)
        
        # Send welcome email with temporary password
        await send_email_async(
            faculty_data.email,
            "Welcome to EduSync - Faculty Account Created",
            f"""Dear {faculty_data.name},

Your faculty account has been created by the HOD of {faculty_data.department} department.

Login Credentials:
Email: {faculty_data.email}
Temporary Password: {temp_password}

Please login and change your password immediately.

Department: {faculty_data.department}
Designation: {faculty_data.designation}

Best regards,
EduSync Administration
"""
        )
        
        # Create notification for HOD
        await NotificationService.create_notification(
            user_id=str(current_user["_id"]),
            title="Faculty Added Successfully",
            message=f"Faculty member {faculty_data.name} has been added. Credentials sent to {faculty_data.email}",
            notification_type="system",
            priority="medium"
        )
        
        return {
            "message": "Faculty added successfully",
            "faculty_id": faculty_id,
            "faculty_email": faculty_data.email,
            "temporary_password": temp_password,
            "note": "Credentials have been sent to faculty email"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add faculty error: {e}")
        raise HTTPException(status_code=500, detail="Failed to add faculty")


@router.get("/api/hod/faculty/{faculty_id}", tags=["HOD"])
async def get_faculty_details(
    faculty_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get detailed faculty information"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        # Get faculty stats
        faculty_stats = await get_faculty_stats(faculty_id)
        if not faculty_stats:
            raise HTTPException(status_code=404, detail="Faculty not found")
        
        # Get faculty user details
        faculty_user = await users_collection.find_one({"_id": ObjectId(faculty_id)})
        
        return {
            "personal_info": {
                "name": faculty_user["full_name"],
                "email": faculty_user["email"],
                "designation": faculty_user.get("designation", "Assistant Professor"),
                "specialization": faculty_user.get("expertise", []),
                "office": faculty_user.get("office", "Not specified"),
                "phone": faculty_user.get("phone", "Not specified")
            },
            "performance_stats": faculty_stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get faculty details error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get faculty details")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.get("/api/hod/faculty", tags=["HOD"])
async def get_hod_faculty(
    status: Optional[str] = None,
    designation: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get faculty list for HOD"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        query = {
            "user_type": UserType.FACULTY.value,
            "department": department,
            "is_active": True
        }
        
        if status:
            query["status"] = status
        
        if designation:
            query["designation"] = designation
        
        if search:
            query["$or"] = [
                {"full_name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"expertise": {"$regex": search, "$options": "i"}}
            ]
        
        total = await users_collection.count_documents(query)
        
        faculty = await users_collection.find(query) \
            .sort("full_name", 1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        # Get detailed stats for each faculty
        faculty_with_stats = []
        for fac in faculty:
            stats = await get_faculty_stats(str(fac["_id"]))
            if stats:
                faculty_with_stats.append(stats)
        
        result = {
            "faculty": convert_objectid_to_str(faculty_with_stats),
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get HOD faculty error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get faculty list")


