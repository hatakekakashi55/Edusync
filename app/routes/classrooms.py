"""
EduSync Backend - Classrooms Routes
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

router = APIRouter(tags=["Classrooms"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/classroom/add-students", tags=["Faculty"])
async def add_students_to_classroom(
    body: dict = Body(...),
    current_user: dict = Depends(verify_token)
):
    """Directly add students to classroom (no pending approval needed)"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        classroom_id = body.get("classroom_id")
        student_ids = body.get("student_ids", [])
        
        if not classroom_id or not student_ids:
            raise HTTPException(status_code=400, detail="Missing classroom_id or student_ids")
        
        # Get classroom details
        classroom = await classrooms_collection.find_one({"_id": ObjectId(classroom_id)})
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found")
        
        # Verify faculty owns this classroom
        if str(classroom.get("faculty_id")) != str(current_user["_id"]):
            raise HTTPException(status_code=403, detail="Unauthorized to add students to this classroom")
        
        added_count = 0
        
        # Directly add each student to the classroom
        for student_id in student_ids:
            if not ObjectId.is_valid(student_id):
                continue
            
            # Check if student exists
            student = await users_collection.find_one({"_id": ObjectId(student_id)})
            if not student:
                continue
            
            # Check if already in classroom
            if classroom_id in student.get("classrooms", []):
                continue
            
            # Add classroom to student's classrooms array
            await users_collection.update_one(
                {"_id": ObjectId(student_id)},
                {"$addToSet": {"classrooms": classroom_id}}
            )
            
            # Add student to classroom's students array (if it has one)
            await classrooms_collection.update_one(
                {"_id": ObjectId(classroom_id)},
                {"$addToSet": {"students": student_id}}
            )
            
            added_count += 1
        
        return {
            "success": True,
            "added_count": added_count,
            "message": f"{added_count} student(s) added to classroom successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add students error: {e}")
        raise HTTPException(status_code=500, detail="Failed to add students")


@router.get("/api/classrooms", tags=["Classrooms"])
async def get_classrooms(
    department: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get classrooms"""
    try:
        user_id = str(current_user["_id"])
        
        query = {}
        
        if current_user["user_type"] == UserType.STUDENT:
            user_dept = current_user.get("department")
            user_year = current_user.get("year")
            
            query["$or"] = [
                {"students": user_id},
                {"department": user_dept, "year": user_year, "is_public": True}
            ]
        
        if department:
            query["department"] = department
        if year:
            query["year"] = year
        
        total = await classrooms_collection.count_documents(query)
        
        classrooms = await classrooms_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "classrooms": [
                {
                    "id": str(cls["_id"]),
                    "name": cls["name"],
                    "description": cls.get("description", ""),
                    "course_code": cls.get("course_code"),
                    "instructor_name": cls.get("instructor_name"),
                    "department": cls.get("department"),
                    "year": cls.get("year"),
                    "student_count": len(cls.get("students", [])),
                    "is_member": user_id in cls.get("students", []),
                    "created_at": cls["created_at"]
                }
                for cls in classrooms
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get classrooms error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get classrooms")


