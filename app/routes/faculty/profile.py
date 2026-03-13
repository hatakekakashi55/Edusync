"""
EduSync Backend - Faculty - Profile Routes
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

router = APIRouter(tags=["Faculty - Profile"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/faculty/send-classroom-invitations", tags=["Faculty"])
async def send_classroom_invitations(
    body: dict = Body(...),
    current_user: dict = Depends(verify_token)
):
    """Send classroom invitations to students (creates pending requests)"""
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
            raise HTTPException(status_code=403, detail="Unauthorized to invite for this classroom")
        
        faculty_name = f"{current_user.get('firstName', '')} {current_user.get('lastName', '')}".strip()
        
        invitation_count = 0
        
        # Create pending request for each student
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
            
            # Check if invitation already pending
            existing = await classroom_requests_collection.find_one({
                "student_id": student_id,
                "classroom_id": classroom_id,
                "status": "pending"
            })
            
            if existing:
                continue
            
            # Create new invitation
            invitation = {
                "student_id": student_id,
                "student_name": f"{student.get('firstName', '')} {student.get('lastName', '')}".strip(),
                "student_email": student.get("email", ""),
                "classroom_id": classroom_id,
                "classroom_name": classroom.get("name", ""),
                "classroom_description": classroom.get("description", ""),
                "classroom_code": classroom.get("code", ""),
                "faculty_id": str(current_user["_id"]),
                "faculty_name": faculty_name,
                "status": "pending",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "response_date": None,
                "message": ""
            }
            
            result = await classroom_requests_collection.insert_one(invitation)
            if result.inserted_id:
                invitation_count += 1
        
        return {
            "success": True,
            "invitation_count": invitation_count,
            "message": f"{invitation_count} invitation(s) sent successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Send classroom invitations error: {e}")
        raise HTTPException(status_code=500, detail="Failed to send invitations")


@router.put("/api/faculty/profile", tags=["Faculty"])
async def update_faculty_profile(
    update_data: dict = Body(...),
    current_user: dict = Depends(verify_token)
):
    """Update faculty profile"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        # Allowed fields for faculty
        allowed_fields = [
            "full_name", "phone", "profile_picture", "bio", 
            "qualifications", "research_areas", "expertise",
            "office_hours", "publications", "courses_teaching"
        ]
        
        # Filter only allowed fields
        filtered_update = {k: v for k, v in update_data.items() if k in allowed_fields}
        
        if not filtered_update:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        
        filtered_update["updated_at"] = datetime.now(timezone.utc)
        
        # Update user
        result = await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": filtered_update}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="No changes made")
        
        return {
            "message": "Faculty profile updated successfully",
            "updated_fields": list(filtered_update.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update faculty profile error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update faculty profile")


@router.get("/api/faculty/dashboard-stats", tags=["Faculty"])
async def get_faculty_dashboard_stats(
    current_user: dict = Depends(verify_token)
):
    """Get faculty dashboard statistics"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        # Get classrooms
        classrooms = await classrooms_collection.find({
            "$or": [
                {"instructor_id": user_id},
                {"created_by": user_id}
            ]
        }).to_list(50)
        
        # Calculate statistics
        total_students = 0
        for classroom in classrooms:
            total_students += len(classroom.get("students", []))
        
        # Get pending assignments
        pending_assignments = await assignment_collection.count_documents({
            "instructor_id": user_id,
            "status": "pending_review"
        })
        
        # Get total assignments
        total_assignments = await assignment_collection.count_documents({
            "instructor_id": user_id
        })
        
        # Get recent submissions
        recent_submissions = await submissions_collection.find({
            "challenge_type": {"$in": ["coding", "voice", "quiz"]}
        }).sort("submitted_at", -1).limit(10).to_list(10)
        
        # Get attendance average (simulated)
        attendance_avg = 94  # This would be calculated from actual data
        
        # Format classroom data
        classroom_data = []
        for classroom in classrooms[:5]:
            assignments_count = await assignment_collection.count_documents({
                "classroom_id": str(classroom["_id"])
            })
            
            classroom_data.append({
                "id": str(classroom["_id"]),
                "code": classroom.get("course_code", "N/A"),
                "name": classroom.get("name", "Unnamed Classroom"),
                "student_count": len(classroom.get("students", [])),
                "assignments": assignments_count,
                "status": "active" if classroom.get("is_active", True) else "inactive"
            })
        
        # Format recent submissions
        submission_data = []
        for sub in recent_submissions[:5]:
            submission_data.append({
                "id": str(sub["_id"]),
                "student_name": sub.get("user_name", "Student"),
                "type": sub.get("challenge_type", "assignment"),
                "title": sub.get("challenge_title", "Submission"),
                "status": "graded" if sub.get("score") else "pending",
                "score": sub.get("score", 0),
                "submitted_at": sub.get("submitted_at")
            })
        
        return {
            "stats": {
                "classrooms": len(classrooms),
                "students": total_students,
                "assignments": total_assignments,
                "pending_grading": pending_assignments,
                "attendance_avg": f"{attendance_avg}%"
            },
            "classrooms": classroom_data,
            "recent_submissions": submission_data,
            "quick_actions": [
                {"id": "create_assignment", "title": "Create Assignment", "icon": "fa-file-alt", "description": "Create new assignment"},
                {"id": "grade_submissions", "title": "Grade Submissions", "icon": "fa-check-double", "description": "Review and grade student work"},
                {"id": "schedule_class", "title": "Schedule Class", "icon": "fa-calendar-plus", "description": "Plan upcoming lectures"},
                {"id": "upload_content", "title": "Upload Content", "icon": "fa-cloud-upload-alt", "description": "Share study materials"}
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Faculty dashboard stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to load dashboard stats")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.get("/api/faculty/profile", tags=["Faculty"])
async def get_faculty_profile(
    current_user: dict = Depends(verify_token)
):
    """Get faculty profile"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        # Get faculty user
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get faculty-specific data
        classrooms = await classrooms_collection.count_documents({
            "$or": [
                {"instructor_id": user_id},
                {"created_by": user_id}
            ]
        })
        
        total_students = 0
        if classrooms > 0:
            classrooms_data = await classrooms_collection.find({
                "$or": [
                    {"instructor_id": user_id},
                    {"created_by": user_id}
                ]
            }).to_list(100)
            
            for classroom in classrooms_data:
                total_students += len(classroom.get("students", []))
        
        # Remove sensitive data
        user.pop("password", None)
        user.pop("verification_code", None)
        user.pop("reset_token", None)
        
        # Convert ObjectId to string
        user["_id"] = str(user["_id"])
        
        # Add faculty-specific stats
        user["faculty_stats"] = {
            "classrooms": classrooms,
            "total_students": total_students,
            "courses_teaching": user.get("courses_teaching", []),
            "research_areas": user.get("research_areas", []),
            "office_hours": user.get("office_hours", ""),
            "qualifications": user.get("qualifications", []),
            "publications": user.get("publications", []),
            "expertise": user.get("expertise", [])
        }
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get faculty profile error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get faculty profile")


