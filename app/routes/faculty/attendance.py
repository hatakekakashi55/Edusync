"""
EduSync Backend - Faculty - Attendance Routes
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

router = APIRouter(tags=["Faculty - Attendance"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/faculty/attendance", tags=["Faculty"])
async def get_attendance_records(
    classroom_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get attendance records"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        query = {"marked_by": user_id}
        
        if classroom_id:
            query["classroom_id"] = classroom_id
        
        if date_from and date_to:
            query["date"] = {"$gte": date_from, "$lte": date_to}
        elif date_from:
            query["date"] = {"$gte": date_from}
        elif date_to:
            query["date"] = {"$lte": date_to}
        
        total = await faculty_attendance_collection.count_documents(query)
        
        records = await faculty_attendance_collection.find(query) \
            .sort("date", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "records": [
                {
                    "id": str(rec["_id"]),
                    "classroom_code": rec["classroom_code"],
                    "date": rec["date"],
                    "session": rec["session"],
                    "period": rec.get("period"),
                    "stats": rec["stats"],
                    "marked_at": rec["marked_at"]
                }
                for rec in records
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get attendance records error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get attendance records")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.post("/api/faculty/attendance", tags=["Faculty"])
async def mark_attendance(
    attendance_data: AttendanceRecord,
    current_user: dict = Depends(verify_token)
):
    """Mark attendance for a classroom"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        # Verify classroom ownership
        classroom = await faculty_classrooms_collection.find_one({
            "_id": ObjectId(attendance_data.classroom_id),
            "instructor_id": user_id
        })
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found")
        
        attendance_record = {
            "classroom_id": attendance_data.classroom_id,
            "classroom_code": classroom["code"],
            "date": attendance_data.date,
            "session": attendance_data.session,
            "period": attendance_data.period,
            "marked_by": user_id,
            "marked_by_name": current_user["full_name"],
            "marked_at": datetime.now(timezone.utc),
            "students": attendance_data.students,
            "stats": {
                "present": len([s for s in attendance_data.students if s.get("status") == "present"]),
                "absent": len([s for s in attendance_data.students if s.get("status") == "absent"]),
                "late": len([s for s in attendance_data.students if s.get("status") == "late"]),
                "total": len(attendance_data.students)
            }
        }
        
        result = await faculty_attendance_collection.insert_one(attendance_record)
        record_id = str(result.inserted_id)
        
        return {
            "message": "Attendance marked successfully",
            "record_id": record_id,
            "stats": attendance_record["stats"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Mark attendance error: {e}")
        raise HTTPException(status_code=500, detail="Failed to mark attendance")


