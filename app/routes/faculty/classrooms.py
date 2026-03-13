"""
EduSync Backend - Faculty - Classrooms Routes
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

router = APIRouter(tags=["Faculty - Classrooms"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/faculty/classrooms", tags=["Faculty"])
async def get_faculty_classrooms(
    search: Optional[str] = None,
    department: Optional[str] = None,
    semester: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get faculty classrooms"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        query = {"instructor_id": user_id}
        
        if search:
            query["$or"] = [
                {"code": {"$regex": search, "$options": "i"}},
                {"name": {"$regex": search, "$options": "i"}}
            ]
        
        if department:
            query["department"] = department
        if semester:
            query["semester"] = semester
        if status:
            query["status"] = status
        
        total = await faculty_classrooms_collection.count_documents(query)
        
        classrooms = await faculty_classrooms_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        # Get assignment counts for each classroom
        for classroom in classrooms:
            assignment_count = await faculty_assignments_collection.count_documents({
                "classroom_id": str(classroom["_id"])
            })
            classroom["assignment_count"] = assignment_count
            
            # Get student count
            if "students" in classroom:
                classroom["current_students"] = len(classroom["students"])
        
        return {
            "classrooms": [
                {
                    "id": str(cls["_id"]),
                    "code": cls["code"],
                    "name": cls["name"],
                    "department": cls["department"],
                    "semester": cls["semester"],
                    "description": cls.get("description", ""),
                    "schedule": cls.get("schedule", ""),
                    "location": cls.get("location", ""),
                    "studentCount": cls.get("current_students", 0),
                    "maxStudents": cls.get("max_students", 50),
                    "assignmentCount": cls.get("assignment_count", 0),
                    "status": cls.get("status", "active"),
                    "createdDate": cls["created_at"],
                    "updatedDate": cls.get("updated_at", cls["created_at"]),
                    "settings": cls.get("settings", {
                        "attendance": False,
                        "assignments": False,
                        "discussions": False,
                        "announcements": False
                    }),
                    "students": cls.get("students", []),
                    "attendanceRate": cls.get("attendance_rate", 0),
                    "averageScore": cls.get("average_score", 0)
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
        logger.error(f"Get faculty classrooms error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get classrooms")


@router.delete("/api/faculty/classrooms/{classroom_id}", tags=["Faculty"])
async def delete_classroom(
    classroom_id: str,
    current_user: dict = Depends(verify_token)
):
    """Delete a classroom"""
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
        
        # Remove classroom from all students' classrooms list (try both string and ObjectId)
        if classroom.get("students"):
            await users_collection.update_many(
                {
                    "_id": {
                        "$in": [
                            ObjectId(sid) if ObjectId.is_valid(str(sid)) else None 
                            for sid in classroom.get("students", [])
                        ]
                    }
                },
                {
                    "$pull": {
                        "classrooms": {
                            "$in": [classroom_id, ObjectId(classroom_id) if ObjectId.is_valid(classroom_id) else None]
                        }
                    }
                }
            )
        
        # Delete the classroom
        result = await faculty_classrooms_collection.delete_one({
            "_id": ObjectId(classroom_id),
            "instructor_id": user_id
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Classroom not found or not authorized to delete")
        
        return {"message": "Classroom deleted successfully", "classroom_id": classroom_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete classroom error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete classroom")


@router.post("/api/faculty/classrooms/{classroom_id}/add-students", tags=["Faculty"])
async def add_students_to_classroom(
    classroom_id: str,
    student_ids: list = Body(...),
    current_user: dict = Depends(verify_token)
):
    """Directly add multiple students to classroom (no approval needed - like WhatsApp groups)"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        if not student_ids or len(student_ids) == 0:
            raise HTTPException(status_code=400, detail="No students provided")
        
        # Verify classroom exists and belongs to the faculty
        classroom = await faculty_classrooms_collection.find_one({
            "_id": ObjectId(classroom_id),
            "instructor_id": user_id
        })
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found")
        
        # Ensure classroom exists in classrooms_collection for student dashboard
        # (in case it was created before the dual-collection fix)
        classroom_exists_in_student_collection = await classrooms_collection.find_one({
            "_id": ObjectId(classroom_id)
        })
        if not classroom_exists_in_student_collection:
            logger.info(f"Copying classroom {classroom_id} to classrooms_collection")
            classroom["_id"] = ObjectId(classroom_id)
            await classrooms_collection.insert_one(classroom)
        
        added_count = 0
        
        # Log for debugging
        logger.info(f"Adding students to classroom {classroom_id}. Student IDs: {student_ids}")
        
        # Add each student to the classroom
        for student_id in student_ids:
            try:
                if not ObjectId.is_valid(student_id):
                    continue
                
                # Check if student already in classroom
                existing_students = classroom.get("students", [])
                if student_id in existing_students:
                    continue
                
                # Add student to faculty_classrooms_collection
                await faculty_classrooms_collection.update_one(
                    {"_id": ObjectId(classroom_id)},
                    {
                        "$addToSet": {"students": student_id},
                        "$inc": {"current_students": 1}
                    }
                )
                
                # Also add student to classrooms_collection (for student dashboard to see)
                await classrooms_collection.update_one(
                    {"_id": ObjectId(classroom_id)},
                    {"$addToSet": {"students": student_id}}
                )
                
                logger.info(f"✓ Added student {student_id} to classrooms_collection")
                
                # Add classroom to student's classrooms list in users collection
                await users_collection.update_one(
                    {"_id": ObjectId(student_id)},
                    {"$addToSet": {"classrooms": classroom_id}}
                )
                
                added_count += 1
            except Exception as e:
                logger.warning(f"Could not add student {student_id}: {e}")
                continue
        
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




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.post("/api/faculty/classrooms", tags=["Faculty"])
async def create_classroom(
    classroom_data: ClassroomCreate,
    current_user: dict = Depends(verify_token)
):
    """Create a new classroom"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        # Check if classroom code exists
        existing = await faculty_classrooms_collection.find_one({
            "code": classroom_data.code,
            "instructor_id": user_id
        })
        if existing:
            raise HTTPException(status_code=400, detail="Classroom code already exists")
        
        classroom = {
            "code": classroom_data.code,
            "name": classroom_data.name,
            "description": classroom_data.description,
            "department": classroom_data.department,
            "semester": classroom_data.semester,
            "schedule": classroom_data.schedule,
            "location": classroom_data.location,
            "instructor_id": user_id,
            "instructor_name": current_user.get("full_name", ""),
            "max_students": classroom_data.max_students,
            "current_students": 0,
            "settings": classroom_data.settings or {
                "attendance": True,
                "assignments": True,
                "discussions": True,
                "announcements": True
            },
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "status": "active",
            "students": [],
            "assignments": 0,
            "average_score": 0,
            "attendance_rate": 0
        }
        
        result = await faculty_classrooms_collection.insert_one(classroom)
        classroom_id = str(result.inserted_id)
        
        # Also create in classrooms_collection for student dashboard
        classroom["_id"] = result.inserted_id
        await classrooms_collection.insert_one(classroom)
        
        # Update user's classrooms
        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$push": {"classrooms": classroom_id}}
        )
        
        return {
            "message": "Classroom created successfully",
            "classroom_id": classroom_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create classroom error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create classroom: {str(e)}")


