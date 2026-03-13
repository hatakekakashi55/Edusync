"""
EduSync Backend - HOD - Curriculum Routes
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

router = APIRouter(tags=["HOD - Curriculum"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/hod/courses", tags=["HOD - Curriculum"])
async def get_courses(
    year: Optional[int] = None,
    semester: Optional[int] = None,
    course_type: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get all courses for the department"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        query = {"department": department}
        
        if year:
            query["year"] = year
        
        if semester:
            query["semester"] = semester
        
        if course_type:
            query["type"] = course_type
        
        if search:
            query["$or"] = [
                {"course_code": {"$regex": search, "$options": "i"}},
                {"title": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}}
            ]
        
        total = await courses_collection.count_documents(query)
        
        courses = await courses_collection.find(query) \
            .sort([("year", 1), ("semester", 1), ("course_code", 1)]) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        # Get faculty assignments for each course
        for course in courses:
            course_id = str(course["_id"])
            assignments = await faculty_assignments_collection.find({
                "course_id": course_id
            }).to_list(10)
            
            course["faculty_assignments_count"] = len(assignments)
            course["assigned_faculty"] = [a["faculty_name"] for a in assignments[:3]]
        
        return {
            "courses": convert_objectid_to_str(courses),
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get courses error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get courses")


@router.post("/api/hod/courses/{course_id}/syllabus", tags=["HOD - Curriculum"])
async def add_syllabus_topic(
    course_id: str,
    syllabus_data: SyllabusCreate,
    current_user: dict = Depends(verify_token)
):
    """Add syllabus topic to a course"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        # Check if course exists and belongs to department
        course = await courses_collection.find_one({
            "_id": ObjectId(course_id),
            "department": current_user["department"]
        })
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        syllabus_topic = {
            "week_number": syllabus_data.week_number,
            "topic": syllabus_data.topic,
            "subtopics": syllabus_data.subtopics,
            "learning_objectives": syllabus_data.learning_objectives,
            "teaching_method": syllabus_data.teaching_method,
            "assessment_method": syllabus_data.assessment_method,
            "resources": syllabus_data.resources,
            "added_by": str(current_user["_id"]),
            "added_at": datetime.now(timezone.utc)
        }
        
        # Add to syllabus array
        await courses_collection.update_one(
            {"_id": ObjectId(course_id)},
            {
                "$push": {"syllabus": syllabus_topic},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )
        
        return {
            "message": "Syllabus topic added successfully",
            "syllabus_topic": syllabus_topic
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add syllabus error: {e}")
        raise HTTPException(status_code=500, detail="Failed to add syllabus")


@router.post("/api/hod/courses/assign-faculty", tags=["HOD - Curriculum"])
async def assign_faculty_to_course(
    assignment_data: FacultyAssignment,
    current_user: dict = Depends(verify_token)
):
    """Assign faculty to a course"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Verify course belongs to department
        course = await courses_collection.find_one({
            "_id": ObjectId(assignment_data.course_id),
            "department": department
        })
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")
        
        # Verify faculty belongs to department
        faculty = await users_collection.find_one({
            "_id": ObjectId(assignment_data.faculty_id),
            "department": department,
            "user_type": UserType.FACULTY.value
        })
        if not faculty:
            raise HTTPException(status_code=404, detail="Faculty not found")
        
        # Check if already assigned
        existing = await faculty_assignments_collection.find_one({
            "course_id": assignment_data.course_id,
            "faculty_id": assignment_data.faculty_id,
            "role": assignment_data.role
        })
        if existing:
            raise HTTPException(status_code=400, detail="Faculty already assigned to this course with same role")
        
        assignment = {
            "course_id": assignment_data.course_id,
            "course_code": course["course_code"],
            "course_title": course["title"],
            "faculty_id": assignment_data.faculty_id,
            "faculty_name": faculty["full_name"],
            "faculty_email": faculty["email"],
            "role": assignment_data.role,
            "section": assignment_data.section,
            "schedule": assignment_data.schedule,
            "department": department,
            "assigned_by": str(current_user["_id"]),
            "assigned_by_name": current_user["full_name"],
            "assigned_at": datetime.now(timezone.utc),
            "status": "active"
        }
        
        result = await faculty_assignments_collection.insert_one(assignment)
        
        # Update course with assignment
        await courses_collection.update_one(
            {"_id": ObjectId(assignment_data.course_id)},
            {
                "$push": {"faculty_assignments": assignment_data.faculty_id},
                "$inc": {"faculty_assignments_count": 1}
            }
        )
        
        # Update faculty profile
        await users_collection.update_one(
            {"_id": ObjectId(assignment_data.faculty_id)},
            {
                "$addToSet": {"courses_teaching": assignment_data.course_id},
                "$inc": {"classes_taught": 1}
            }
        )
        
        # Send notification to faculty
        await NotificationService.create_notification(
            user_id=assignment_data.faculty_id,
            title="Course Assignment",
            message=f"You have been assigned as {assignment_data.role} for {course['course_code']} - {course['title']}",
            notification_type="assignment",
            priority="high",
            action_url=f"/courses/{assignment_data.course_id}"
        )
        
        return {
            "message": "Faculty assigned successfully",
            "assignment_id": str(result.inserted_id),
            "assignment": assignment
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assign faculty error: {e}")
        raise HTTPException(status_code=500, detail="Failed to assign faculty")


@router.get("/api/hod/curriculum/stats", tags=["HOD - Curriculum"])
async def get_curriculum_stats(
    current_user: dict = Depends(verify_token)
):
    """Get curriculum statistics for the department"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Get course statistics
        pipeline = [
            {"$match": {"department": department}},
            {"$group": {
                "_id": None,
                "total_courses": {"$sum": 1},
                "core_courses": {"$sum": {"$cond": [{"$eq": ["$type", "core"]}, 1, 0]}},
                "elective_courses": {"$sum": {"$cond": [{"$eq": ["$type", "elective"]}, 1, 0]}},
                "lab_courses": {"$sum": {"$cond": [{"$eq": ["$type", "lab"]}, 1, 0]}},
                "total_credits": {"$sum": "$credits"},
                "by_year": {"$push": {"year": "$year", "credits": "$credits"}}
            }}
        ]
        
        stats_result = list(await courses_collection.aggregate(pipeline).to_list(length=1))
        stats = stats_result[0] if stats_result else {
            "total_courses": 0,
            "core_courses": 0,
            "elective_courses": 0,
            "lab_courses": 0,
            "total_credits": 0
        }
        
        # Get faculty assignment statistics
        faculty_pipeline = [
            {"$match": {"department": department}},
            {"$group": {
                "_id": "$faculty_id",
                "courses_count": {"$sum": 1}
            }},
            {"$group": {
                "_id": None,
                "total_faculty_assigned": {"$sum": 1},
                "avg_courses_per_faculty": {"$avg": "$courses_count"},
                "max_courses": {"$max": "$courses_count"},
                "min_courses": {"$min": "$courses_count"}
            }}
        ]
        
        faculty_stats = list(await faculty_assignments_collection.aggregate(faculty_pipeline).to_list(length=1))
        faculty_stats = faculty_stats[0] if faculty_stats else {
            "total_faculty_assigned": 0,
            "avg_courses_per_faculty": 0,
            "max_courses": 0,
            "min_courses": 0
        }
        
        # Get courses by year
        courses_by_year = {}
        for year in range(1, 6):
            year_courses = await courses_collection.count_documents({
                "department": department,
                "year": year
            })
            courses_by_year[f"Year {year}"] = year_courses
        
        # Get upcoming academic calendar events
        upcoming_events = await db.academic_calendar.find({
            "department": department,
            "start_date": {"$gte": datetime.now(timezone.utc)}
        }).sort("start_date", 1).limit(5).to_list(5)
        
        # Get courses needing faculty assignments
        unassigned_courses = await courses_collection.count_documents({
            "department": department,
            "faculty_assignments_count": 0
        })
        
        return {
            "department": department,
            "course_statistics": {
                **stats,
                "courses_by_year": courses_by_year,
                "unassigned_courses": unassigned_courses
            },
            "faculty_statistics": faculty_stats,
            "upcoming_events": convert_objectid_to_str(upcoming_events),
            "curriculum_completeness": {
                "syllabus_coverage": 85,  # This would be calculated from actual data
                "resource_availability": 78,
                "faculty_assignment_rate": (stats["total_courses"] - unassigned_courses) / stats["total_courses"] * 100 if stats["total_courses"] > 0 else 0
            }
        }
        
    except Exception as e:
        logger.error(f"Get curriculum stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get curriculum statistics")


@router.get("/api/hod/curriculum", tags=["HOD"])
async def get_department_curriculum(
    year: Optional[int] = None,
    semester: Optional[str] = None,
    current_user: dict = Depends(verify_token)
):
    """Get department curriculum"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        query = {"department": department}
        
        if year:
            query["year"] = year
        if semester:
            query["semester"] = semester
        
        # Get courses
        courses = await courses_collection.find(query).sort("year", 1).sort("semester", 1).to_list(100)
        
        # Get classes
        classes = await classrooms_collection.find(query).sort("semester", 1).to_list(100)
        
        # Get faculty assignments
        faculty_assignments = {}
        for cls in classes:
            instructor_id = cls.get("instructor_id")
            if instructor_id:
                faculty = await users_collection.find_one({"_id": ObjectId(instructor_id)})
                if faculty:
                    faculty_name = faculty["full_name"]
                    if faculty_name not in faculty_assignments:
                        faculty_assignments[faculty_name] = []
                    faculty_assignments[faculty_name].append({
                        "class": cls.get("name"),
                        "code": cls.get("code"),
                        "semester": cls.get("semester")
                    })
        
        # Organize curriculum by year and semester
        curriculum = {}
        for course in courses:
            year_key = f"Year {course.get('year', 1)}"
            semester_key = f"Semester {course.get('semester', 1)}"
            
            if year_key not in curriculum:
                curriculum[year_key] = {}
            if semester_key not in curriculum[year_key]:
                curriculum[year_key][semester_key] = []
            
            curriculum[year_key][semester_key].append({
                "course_code": course.get("course_code"),
                "title": course.get("title"),
                "credits": course.get("credits", 3),
                "type": course.get("type", "core"),
                "description": course.get("description", ""),
                "prerequisites": course.get("prerequisites", [])
            })
        
        return {
            "department": department,
            "curriculum_structure": curriculum,
            "faculty_assignments": faculty_assignments,
            "total_courses": len(courses),
            "total_classes": len(classes),
            "academic_calendar": [
                {"event": "Semester 1 Begins", "date": "2024-08-01"},
                {"event": "Mid-term Exams", "date": "2024-09-15"},
                {"event": "Semester 1 Ends", "date": "2024-11-30"},
                {"event": "Semester 2 Begins", "date": "2024-12-15"},
                {"event": "Final Exams", "date": "2025-04-01"},
                {"event": "Semester 2 Ends", "date": "2025-05-15"}
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get curriculum error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get curriculum")


@router.post("/api/hod/curriculum/upload-syllabus-pdf", tags=["HOD - Curriculum"])
async def upload_syllabus_pdf(
    course_id: str = Form(...),
    file: UploadFile = File(...),
    unit_count: int = Form(5),
    current_user: dict = Depends(verify_token)
):
    """Upload and process university syllabus PDF"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        # Validate file
        content = await file.read()
        file_size = len(content)
        
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=400, detail="PDF file too large. Max 10MB")
        
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")
        
        # Process PDF
        processor = SyllabusProcessor()
        result = await processor.process_pdf_syllabus(content, course_id, unit_count)
        
        # Save to database
        syllabus_doc = {
            "course_id": course_id,
            "original_filename": file.filename,
            "file_size": file_size,
            "uploaded_by": str(current_user["_id"]),
            "uploaded_by_name": current_user["full_name"],
            "uploaded_at": datetime.now(timezone.utc),
            "units": result["processed_units"],
            "status": "processed",
            "ai_processed": True,
            "metadata": {
                "total_units": result["total_units"],
                "total_pages": result["total_pages"],
                "processing_time": result["processing_time"]
            }
        }
        
        # Save to syllabus collection
        await syllabus_collection.insert_one(syllabus_doc)
        
        # Update course with syllabus info
        await courses_collection.update_one(
            {"_id": ObjectId(course_id)},
            {"$set": {
                "has_syllabus": True,
                "syllabus_units": result["total_units"],
                "syllabus_updated_at": datetime.now(timezone.utc)
            }}
        )
        
        # Send notification
        await NotificationService.create_notification(
            user_id=str(current_user["_id"]),
            title="📚 Syllabus Uploaded Successfully",
            message=f"Syllabus for {result['course_code']} processed with {result['total_units']} units",
            notification_type="syllabus",
            priority="medium"
        )
        
        return {
            "success": True,
            "message": "Syllabus processed successfully",
            "course": {
                "code": result["course_code"],
                "title": result["course_title"]
            },
            "units_extracted": result["total_units"],
            "syllabus_id": str(syllabus_doc["_id"]),
            "preview": result["processed_units"][:2]  # First 2 units preview
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Syllabus upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Syllabus upload failed: {str(e)}")


@router.delete("/api/hod/curriculum/{course_id}/syllabus", tags=["HOD - Curriculum"])
async def delete_syllabus(
    course_id: str,
    current_user: dict = Depends(verify_token)
):
    """Delete syllabus for a course"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        result = await syllabus_collection.delete_many({"course_id": course_id})
        
        # Update course
        await courses_collection.update_one(
            {"_id": ObjectId(course_id)},
            {"$set": {
                "has_syllabus": False,
                "syllabus_units": 0
            }}
        )
        
        return {
            "success": True,
            "message": f"Deleted {result.deleted_count} syllabus records",
            "course_id": course_id
        }
        
    except Exception as e:
        logger.error(f"Delete syllabus error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete syllabus")


@router.post("/api/hod/curriculum/manual-syllabus-unit", tags=["HOD - Curriculum"])
async def add_manual_syllabus_unit(
    unit_data: UnitCreate,
    current_user: dict = Depends(verify_token)
):
    """Manually add a syllabus unit"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        # Check if syllabus exists
        syllabus = await syllabus_collection.find_one({"course_id": unit_data.course_id})
        
        unit = {
            "unit_number": unit_data.unit_number,
            "title": unit_data.title,
            "description": unit_data.description,
            "topics": unit_data.topics,
            "learning_outcomes": unit_data.learning_outcomes,
            "references": unit_data.references,
            "created_by": str(current_user["_id"]),
            "created_at": datetime.now(timezone.utc)
        }
        
        if syllabus:
            # Update existing syllabus
            await syllabus_collection.update_one(
                {"course_id": unit_data.course_id},
                {
                    "$push": {"units": unit},
                    "$set": {
                        "updated_at": datetime.now(timezone.utc),
                        "manually_added": True
                    },
                    "$inc": {"metadata.total_units": 1}
                }
            )
        else:
            # Create new syllabus
            syllabus_doc = {
                "course_id": unit_data.course_id,
                "units": [unit],
                "uploaded_by": str(current_user["_id"]),
                "uploaded_by_name": current_user["full_name"],
                "uploaded_at": datetime.now(timezone.utc),
                "status": "manual",
                "ai_processed": False,
                "metadata": {
                    "total_units": 1,
                    "processing_time": datetime.now(timezone.utc)
                }
            }
            await syllabus_collection.insert_one(syllabus_doc)
        
        return {
            "success": True,
            "message": "Unit added successfully",
            "unit": unit
        }
        
    except Exception as e:
        logger.error(f"Add manual unit error: {e}")
        raise HTTPException(status_code=500, detail="Failed to add unit")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.post("/api/hod/courses", tags=["HOD - Curriculum"])
async def create_course(
    course_data: CourseCreate,
    current_user: dict = Depends(verify_token)
):
    """Create a new course"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Check if course code exists
        existing = await courses_collection.find_one({
            "course_code": course_data.course_code,
            "department": department
        })
        if existing:
            raise HTTPException(status_code=400, detail="Course code already exists")
        
        course = {
            "course_code": course_data.course_code,
            "title": course_data.title,
            "description": course_data.description,
            "credits": course_data.credits,
            "year": course_data.year,
            "semester": course_data.semester,
            "department": department,
            "type": course_data.type,
            "prerequisites": course_data.prerequisites,
            "learning_outcomes": course_data.learning_outcomes,
            "syllabus": course_data.syllabus,
            "textbooks": course_data.textbooks,
            "references": course_data.references,
            "created_by": str(current_user["_id"]),
            "created_by_name": current_user["full_name"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "status": "active",
            "faculty_assignments": [],
            "enrollment_count": 0,
            "average_rating": 0
        }
        
        result = await courses_collection.insert_one(course)
        course_id = str(result.inserted_id)
        
        return {
            "message": "Course created successfully",
            "course_id": course_id,
            "course": convert_objectid_to_str(course)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create course error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create course")


@router.get("/api/hod/curriculum/{course_id}/syllabus", tags=["HOD - Curriculum"])
async def get_course_syllabus(
    course_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get syllabus for a course"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        syllabus = await syllabus_collection.find_one(
            {"course_id": course_id},
            sort=[("uploaded_at", -1)]
        )
        
        if not syllabus:
            return {"has_syllabus": False, "message": "No syllabus uploaded yet"}
        
        return {
            "has_syllabus": True,
            "syllabus": convert_objectid_to_str(syllabus),
            "course": await courses_collection.find_one(
                {"_id": ObjectId(course_id)},
                {"course_code": 1, "title": 1}
            )
        }
        
    except Exception as e:
        logger.error(f"Get syllabus error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get syllabus")


