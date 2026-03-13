"""
EduSync Backend - Student - Classrooms Routes
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

router = APIRouter(tags=["Student - Classrooms"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/student/classrooms", tags=["Student", "Classrooms"])
async def get_student_classrooms(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get classrooms enrolled by the current student"""
    try:
        if current_user["user_type"] != UserType.STUDENT.value:
            raise HTTPException(status_code=403, detail="For students only")
        
        user_id = str(current_user["_id"])
        
        # Find classrooms where the student is enrolled
        query = {"students": user_id}
        
        logger.info(f"Searching for classrooms with student_id: {user_id}")
        
        total = await classrooms_collection.count_documents(query)
        
        logger.info(f"Found {total} classrooms for student {user_id}")
        
        classrooms = await classrooms_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "classrooms": [
                {
                    "id": str(cls["_id"]),
                    "code": cls.get("code", ""),
                    "name": cls.get("name", "Classroom"),
                    "description": cls.get("description", ""),
                    "course_code": cls.get("course_code", ""),
                    "instructor_name": cls.get("instructor_name", ""),
                    "department": cls.get("department", ""),
                    "year": cls.get("year", ""),
                    "student_count": len(cls.get("students", [])),
                    "is_member": True,
                    "created_at": cls.get("created_at", datetime.now(timezone.utc).isoformat())
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
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get student classrooms error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get student classrooms")


@router.get("/api/student/classroom-requests/pending", tags=["Student", "Classrooms"])
async def get_pending_classroom_requests(
    current_user: dict = Depends(verify_token)
):
    """Get pending classroom requests for the current student"""
    try:
        if current_user["user_type"] != UserType.STUDENT.value:
            raise HTTPException(status_code=403, detail="For students only")
        
        user_id = str(current_user["_id"])
        
        # Find pending classroom requests for this student
        # Check if classroom_requests_collection has any documents with student_id matching
        pending_requests = await classroom_requests_collection.find({
            "student_id": user_id,
            "status": "pending"
        }).sort("created_at", -1).to_list(None)
        
        return {
            "pending_requests": [
                {
                    "request_id": str(req["_id"]),
                    "student_id": req["student_id"],
                    "classroom_id": req.get("classroom_id", ""),
                    "classroom_name": req.get("classroom_name", ""),
                    "classroom_description": req.get("classroom_description", ""),
                    "faculty_name": req.get("faculty_name", ""),
                    "status": req.get("status", "pending"),
                    "created_at": req.get("created_at", datetime.now(timezone.utc).isoformat()),
                    "message": req.get("message", "")
                }
                for req in pending_requests
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get pending classroom requests error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get pending classroom requests")


@router.post("/api/student/classroom-requests/{request_id}/respond", tags=["Student", "Classrooms"])
async def respond_to_classroom_request(
    request_id: str,
    body: dict = Body(...),
    current_user: dict = Depends(verify_token)
):
    """Student accepts or rejects a classroom invitation"""
    try:
        if current_user["user_type"] != UserType.STUDENT.value:
            raise HTTPException(status_code=403, detail="For students only")
        
        if not ObjectId.is_valid(request_id):
            raise HTTPException(status_code=400, detail="Invalid request ID")
        
        response = body.get("response")  # "accept" or "reject"
        
        if response not in ["accept", "reject"]:
            raise HTTPException(status_code=400, detail="Invalid response. Must be 'accept' or 'reject'")
        
        user_id = str(current_user["_id"])
        
        # Find the request
        request_record = await classroom_requests_collection.find_one({
            "_id": ObjectId(request_id),
            "student_id": user_id
        })
        
        if not request_record:
            raise HTTPException(status_code=404, detail="Request not found")
        
        if request_record.get("status") != "pending":
            raise HTTPException(status_code=400, detail="Request is no longer pending")
        
        if response == "accept":
            # Add classroom to student's classrooms list
            student = await users_collection.find_one({"_id": ObjectId(user_id)})
            classrooms = student.get("classrooms", [])
            
            if request_record["classroom_id"] not in classrooms:
                classrooms.append(request_record["classroom_id"])
                await users_collection.update_one(
                    {"_id": ObjectId(user_id)},
                    {"$set": {"classrooms": classrooms}}
                )
            
            # Update request status to accepted
            await classroom_requests_collection.update_one(
                {"_id": ObjectId(request_id)},
                {
                    "$set": {
                        "status": "accepted",
                        "response_date": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            
            return {
                "success": True,
                "message": f"Accepted invitation to {request_record.get('classroom_name', 'Classroom')}"
            }
        
        else:  # reject
            # Update request status to rejected
            await classroom_requests_collection.update_one(
                {"_id": ObjectId(request_id)},
                {
                    "$set": {
                        "status": "rejected",
                        "response_date": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            
            return {
                "success": True,
                "message": f"Rejected invitation to {request_record.get('classroom_name', 'Classroom')}"
            }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Respond to classroom request error: {e}")
        raise HTTPException(status_code=500, detail="Failed to respond to request")


@router.get("/api/search-students", tags=["Students"])
async def search_students(
    query: str = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Search for students by name, email, or student ID"""
    try:
        # Only faculty can search students
        if current_user.get("user_type") not in ["faculty", "admin", "hod"]:
            raise HTTPException(status_code=403, detail="Forbidden")
        
        # Search in users collection for students matching the query
        search_pattern = {"$regex": query, "$options": "i"}
        
        students = []
        async for student in users_collection.find({
            "user_type": "student",
            "$or": [
                {"firstName": search_pattern},
                {"lastName": search_pattern},
                {"email": search_pattern},
                {"studentId": search_pattern}
            ]
        }).limit(20):
            students.append({
                "_id": str(student["_id"]),
                "firstName": student.get("firstName", ""),
                "lastName": student.get("lastName", ""),
                "email": student.get("email", ""),
                "studentId": student.get("studentId", ""),
                "classrooms": student.get("classrooms", [])
            })
        
        return {"success": True, "students": students}
    except Exception as e:
        logger.error(f"Error searching students: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/add-student-to-classroom", tags=["Students", "Classrooms"])
async def add_student_to_classroom(
    body: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Add an existing student to a classroom"""
    try:
        # Only faculty can add students to classrooms
        if current_user.get("user_type") not in ["faculty", "admin", "hod"]:
            raise HTTPException(status_code=403, detail="Forbidden")
        
        studentId = body.get("studentId")
        classroomId = body.get("classroomId")
        
        logger.info(f"Adding student {studentId} to classroom {classroomId}")
        
        if not studentId or not classroomId:
            raise HTTPException(status_code=400, detail="Missing studentId or classroomId")
        
        # Validate ObjectId format
        if not ObjectId.is_valid(studentId):
            logger.error(f"Invalid student ID format: {studentId}")
            raise HTTPException(status_code=400, detail="Invalid student ID format")
        
        # Update student's classrooms array
        student = await users_collection.find_one({"_id": ObjectId(studentId)})
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        classrooms = student.get("classrooms", [])
        if classroomId not in classrooms:
            classrooms.append(classroomId)
            result = await users_collection.update_one(
                {"_id": ObjectId(studentId)},
                {"$set": {"classrooms": classrooms}}
            )
            logger.info(f"Updated student {studentId}: matched={result.matched_count}, modified={result.modified_count}")
        
        return {
            "success": True,
            "message": "Student added to classroom successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding student to classroom: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


