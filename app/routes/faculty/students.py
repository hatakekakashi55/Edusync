"""
EduSync Backend - Faculty - Students Routes
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

router = APIRouter(tags=["Faculty - Students"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/faculty/classrooms/{classroom_id}/students", tags=["Faculty"])
async def add_student_to_classroom(
    classroom_id: str,
    body: dict = Body(...),
    current_user: dict = Depends(verify_token)
):
    """Add a student to a classroom"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        student_id = body.get("student_id")
        
        # Validate inputs
        if not student_id:
            raise HTTPException(status_code=400, detail="student_id is required")
        
        if not ObjectId.is_valid(classroom_id):
            raise HTTPException(status_code=400, detail="Invalid classroom ID format")
        
        if not ObjectId.is_valid(student_id):
            raise HTTPException(status_code=400, detail="Invalid student ID format")
        
        # Verify classroom exists and belongs to the faculty
        classroom = await faculty_classrooms_collection.find_one({
            "_id": ObjectId(classroom_id),
            "instructor_id": user_id
        })
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found")
        
        # Verify student exists
        student = await users_collection.find_one({
            "_id": ObjectId(student_id),
            "user_type": UserType.STUDENT.value
        })
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        # Check if student already in classroom
        if student_id in classroom.get("students", []):
            raise HTTPException(status_code=400, detail="Student already in classroom")
        
        # Add student to classroom
        await faculty_classrooms_collection.update_one(
            {"_id": ObjectId(classroom_id)},
            {
                "$push": {"students": student_id},
                "$inc": {"current_students": 1}
            }
        )
        
        # Add classroom to student's classrooms list
        await users_collection.update_one(
            {"_id": ObjectId(student_id)},
            {"$push": {"classrooms": classroom_id}}
        )
        
        return {
            "message": "Student added to classroom successfully",
            "student_id": student_id,
            "classroom_id": classroom_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add student to classroom error: {e}")
        raise HTTPException(status_code=500, detail="Failed to add student to classroom")


@router.delete("/api/faculty/classrooms/{classroom_id}/students/{student_id}", tags=["Faculty"])
async def remove_student_from_classroom(
    classroom_id: str,
    student_id: str,
    current_user: dict = Depends(verify_token)
):
    """Remove a student from a classroom"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        # Verify classroom exists and belongs to the faculty
        classroom = await faculty_classrooms_collection.find_one({
            "_id": ObjectId(classroom_id),
            "instructor_id": user_id
        })
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found")
        
        # Remove student from classroom
        await faculty_classrooms_collection.update_one(
            {"_id": ObjectId(classroom_id)},
            {
                "$pull": {"students": student_id},
                "$inc": {"current_students": -1}
            }
        )
        
        # Remove classroom from student's classrooms list
        await users_collection.update_one(
            {"_id": ObjectId(student_id)},
            {"$pull": {"classrooms": classroom_id}}
        )
        
        return {"message": "Student removed from classroom", "student_id": student_id, "classroom_id": classroom_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Remove student error: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove student")


@router.get("/api/faculty/students", tags=["Faculty"])
async def get_faculty_students(
    classroom_id: Optional[str] = None,
    department: Optional[str] = None,
    year: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get faculty students"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        # Build query based on classrooms the faculty owns
        faculty_classrooms = await faculty_classrooms_collection.find({
            "instructor_id": user_id
        }).to_list(100)
        
        faculty_classroom_ids = [str(cls["_id"]) for cls in faculty_classrooms]
        
        query = {"classrooms": {"$in": faculty_classroom_ids}}
        
        if classroom_id:
            query["classrooms"] = classroom_id
        
        if department:
            query["department"] = department
        
        if year:
            query["year"] = year
        
        if search:
            query["$or"] = [
                {"first_name": {"$regex": search, "$options": "i"}},
                {"last_name": {"$regex": search, "$options": "i"}},
                {"student_id": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}}
            ]
        
        total = await faculty_students_collection.count_documents(query)
        
        students = await faculty_students_collection.find(query) \
            .sort("added_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        # Get student statistics
        for student in students:
            student_id = str(student["_id"])
            
            # Get submissions
            submissions = await faculty_submissions_collection.find({
                "student_id": student_id
            }).to_list(100)
            
            if submissions:
                completed = len([s for s in submissions if s.get("graded", False)])
                total_score = sum(s.get("score", 0) for s in submissions if s.get("graded", False))
                
                student["total_assignments"] = len(submissions)
                student["completed_assignments"] = completed
                student["average_score"] = total_score / completed if completed > 0 else 0
        
        return {
            "students": [
                {
                    "id": str(std["_id"]),
                    "first_name": std["first_name"],
                    "last_name": std["last_name"],
                    "student_id": std["student_id"],
                    "email": std["email"],
                    "department": std["department"],
                    "year": std["year"],
                    "phone": std.get("phone"),
                    "total_assignments": std.get("total_assignments", 0),
                    "completed_assignments": std.get("completed_assignments", 0),
                    "average_score": std.get("average_score", 0)
                }
                for std in students
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get faculty students error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get students")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.post("/api/faculty/students", tags=["Faculty"])
async def add_student(
    student_data: StudentCreate,
    current_user: dict = Depends(verify_token)
):
    """Add a new student"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        # Check if student already exists
        existing = await faculty_students_collection.find_one({
            "student_id": student_data.student_id
        })
        if existing:
            raise HTTPException(status_code=400, detail="Student ID already exists")
        
        # Verify classrooms exist and instructor owns them
        for classroom_id in student_data.classrooms:
            classroom = await faculty_classrooms_collection.find_one({
                "_id": ObjectId(classroom_id),
                "instructor_id": user_id
            })
            if not classroom:
                raise HTTPException(status_code=404, detail=f"Classroom {classroom_id} not found")
        
        student = {
            "first_name": student_data.first_name,
            "last_name": student_data.last_name,
            "student_id": student_data.student_id,
            "email": student_data.email,
            "classrooms": student_data.classrooms,
            "department": student_data.department,
            "year": student_data.year,
            "phone": student_data.phone,
            "notes": student_data.notes,
            "added_by": user_id,
            "added_by_name": current_user["full_name"],
            "added_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "status": "active",
            "total_assignments": 0,
            "completed_assignments": 0,
            "average_score": 0,
            "attendance_rate": 0
        }
        
        result = await faculty_students_collection.insert_one(student)
        student_id = str(result.inserted_id)
        
        # Add student to classrooms
        for classroom_id in student_data.classrooms:
            await faculty_classrooms_collection.update_one(
                {"_id": ObjectId(classroom_id)},
                {
                    "$push": {"students": student_id},
                    "$inc": {"current_students": 1}
                }
            )
        
        return {
            "message": "Student added successfully",
            "student_id": student_id,
            "student": student
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add student error: {e}")
        raise HTTPException(status_code=500, detail="Failed to add student")


