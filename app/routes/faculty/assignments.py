"""
EduSync Backend - Faculty - Assignments Routes
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

router = APIRouter(tags=["Faculty - Assignments"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/faculty/classrooms/{classroom_id}/assignments", tags=["Faculty"])
async def get_classroom_assignments(
    classroom_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get all assignments for a classroom (faculty view)"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        # Validate classroom_id is a valid ObjectId
        try:
            classroom_oid = ObjectId(classroom_id)
        except Exception as e:
            logger.error(f"Invalid classroom_id: {classroom_id} - {e}")
            raise HTTPException(status_code=400, detail="Invalid classroom ID format")
        
        # Verify classroom exists and faculty owns it
        classroom = await faculty_classrooms_collection.find_one({
            "_id": classroom_oid,
            "instructor_id": str(current_user["_id"])
        })
        
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found or unauthorized")
        
        # Get all assignments for this classroom
        assignments = await assignment_collection.find({
            "classroom_id": classroom_oid
        }).sort("created_at", -1).to_list(100)
        
        # Convert to response format
        assignments_list = []
        for asg in assignments:
            assignments_list.append({
                "assignment_id": str(asg["_id"]),
                "title": asg.get("title", ""),
                "description": asg.get("description", ""),
                "due_date": asg.get("due_date", "").isoformat() if asg.get("due_date") else "",
                "max_score": asg.get("max_score", 100),
                "submission_type": asg.get("submission_type", "file"),
                "assignment_type": asg.get("assignment_type", "assignment"),
                "topic": asg.get("topic", ""),
                "status": asg.get("status", "published"),
                "attachments": asg.get("attachments", []),
                "submissions_count": asg.get("submissions_count", 0),
                "created_at": asg.get("created_at", "").isoformat() if asg.get("created_at") else ""
            })
        
        logger.info(f"✓ Retrieved {len(assignments_list)} assignments for classroom {classroom_id}")
        
        return {
            "success": True,
            "assignments": assignments_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get assignments error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch assignments: {str(e)}")


@router.delete("/api/faculty/classrooms/{classroom_id}/assignments/{assignment_id}", tags=["Faculty"])
async def delete_assignment(
    classroom_id: str,
    assignment_id: str,
    current_user: dict = Depends(verify_token)
):
    """Delete an assignment (and all related submissions/grades)"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        # Validate IDs
        try:
            classroom_oid = ObjectId(classroom_id)
            assignment_oid = ObjectId(assignment_id)
        except Exception as e:
            logger.error(f"Invalid ID format: {e}")
            raise HTTPException(status_code=400, detail="Invalid ID format")
        
        # Verify classroom exists and faculty owns it
        classroom = await faculty_classrooms_collection.find_one({
            "_id": classroom_oid,
            "instructor_id": str(current_user["_id"])
        })
        
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found or unauthorized")
        
        # Verify assignment exists and belongs to this classroom
        assignment = await assignment_collection.find_one({
            "_id": assignment_oid,
            "classroom_id": classroom_oid
        })
        
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Delete all submissions for this assignment
        await faculty_submissions_collection.delete_many({
            "assignment_id": assignment_oid
        })
        
        # Delete the assignment itself
        result = await assignment_collection.delete_one({
            "_id": assignment_oid
        })
        
        if result.deleted_count > 0:
            logger.info(f"✓ Deleted assignment {assignment_id} and all submissions")
            return {
                "success": True,
                "message": "Assignment deleted successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to delete assignment")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete assignment error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete assignment: {str(e)}")


@router.get("/api/faculty/classrooms/{classroom_id}/assignments/{assignment_id}/submissions", tags=["Faculty"])
async def get_classroom_assignment_submissions(
    classroom_id: str,
    assignment_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get all submissions for an assignment in a classroom"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        # Validate IDs
        try:
            classroom_oid = ObjectId(classroom_id)
            assignment_oid = ObjectId(assignment_id)
        except Exception as e:
            logger.error(f"Invalid ID format: {e}")
            raise HTTPException(status_code=400, detail="Invalid ID format")
        
        # Verify classroom exists and faculty owns it
        classroom = await faculty_classrooms_collection.find_one({
            "_id": classroom_oid,
            "instructor_id": str(current_user["_id"])
        })
        
        if not classroom:
            raise HTTPException(status_code=403, detail="Unauthorized - classroom not found")
        
        # Verify assignment exists and belongs to this classroom
        assignment = await assignment_collection.find_one({
            "_id": assignment_oid,
            "classroom_id": classroom_oid
        })
        
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Get all submissions for this assignment
        submissions = await faculty_submissions_collection.find({
            "assignment_id": assignment_oid
        }).sort("submitted_at", -1).to_list(500)
        
        # Get all students in classroom to determine who hasn't submitted
        students = classroom.get("students", [])
        
        # Convert submissions to response format
        submissions_list = []
        submitted_student_ids = set()
        
        for sub in submissions:
            student_id = sub.get("student_id", "")
            submitted_student_ids.add(student_id)
            
            # Format submitted files - convert from [{filename, filepath, size}] to file URLs
            submitted_files = []
            if sub.get("submitted_files"):
                for file_obj in sub.get("submitted_files", []):
                    if isinstance(file_obj, dict):
                        # Extract filepath and convert to URL
                        filepath = file_obj.get("filepath", "")
                        if filepath:
                            # Convert file path to URL (e.g., "static/uploads/abc.pdf" -> "/static/uploads/abc.pdf")
                            file_url = "/" + filepath.replace("\\", "/")
                            submitted_files.append(file_url)
                    elif isinstance(file_obj, str):
                        # Already a string (URL or path)
                        submitted_files.append(file_obj)
            
            # Get drive links
            drive_links = sub.get("drive_links", [])
            if drive_links and isinstance(drive_links, list):
                submitted_files.extend(drive_links)
            
            submissions_list.append({
                "id": str(sub["_id"]),
                "submission_id": str(sub["_id"]),
                "student_id": student_id,
                "student_name": sub.get("student_name", "Unknown"),
                "submission_text": sub.get("submission_text"),
                "submission_code": sub.get("submission_code"),
                "submission_link": sub.get("submission_link"),
                "submitted_files": submitted_files,
                "notes": sub.get("notes", ""),
                "submitted_at": sub.get("submitted_at").isoformat() if sub.get("submitted_at") else "",
                "score": sub.get("score"),
                "feedback": sub.get("feedback", ""),
                "status": sub.get("status", "submitted"),
                "is_late": sub.get("is_late", False),
                "graded_at": sub.get("graded_at", "").isoformat() if sub.get("graded_at") else None
            })
        
        # Add "missing" status for students who haven't submitted
        for student_id in students:
            if student_id not in submitted_student_ids:
                # Try to get student name
                student_data = await users_collection.find_one({"_id": ObjectId(student_id)})
                student_name = "Unknown Student"
                if student_data:
                    # Try to get full_name first, fallback to first_name + last_name
                    student_name = student_data.get('full_name') or f"{student_data.get('first_name', '')} {student_data.get('last_name', '')}".strip()
                    if not student_name:
                        student_name = "Unknown Student"
                
                submissions_list.append({
                    "id": f"missing_{student_id}",
                    "submission_id": None,
                    "student_id": student_id,
                    "student_name": student_name,
                    "submission_text": None,
                    "submission_code": None,
                    "submission_link": None,
                    "submitted_files": [],
                    "notes": "",
                    "submitted_at": None,
                    "score": None,
                    "feedback": "",
                    "status": "missing",
                    "is_late": False,
                    "graded_at": None
                })
        
        logger.info(f"✓ Retrieved {len(submissions_list)} submissions (including missing) for assignment {assignment_id}")
        
        return {
            "success": True,
            "submissions": submissions_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get submissions error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch submissions: {str(e)}")


@router.get("/api/faculty/assignments/{assignment_id}/submissions", tags=["Faculty"])
async def get_assignment_submissions(
    assignment_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get all submissions for an assignment"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        # Validate assignment_id is a valid ObjectId
        try:
            assignment_oid = ObjectId(assignment_id)
        except Exception as e:
            logger.error(f"Invalid assignment_id: {assignment_id} - {e}")
            raise HTTPException(status_code=400, detail="Invalid assignment ID format")
        
        # Get assignment
        assignment = await assignment_collection.find_one({
            "_id": assignment_oid
        })
        
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Verify faculty owns the classroom
        classroom = await faculty_classrooms_collection.find_one({
            "_id": assignment["classroom_id"],
            "instructor_id": str(current_user["_id"])
        })
        
        if not classroom:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Get all submissions
        submissions = await faculty_submissions_collection.find({
            "assignment_id": assignment_oid
        }).sort("submitted_at", -1).to_list(500)
        
        # Convert to response format
        submissions_list = []
        for sub in submissions:
            submissions_list.append({
                "submission_id": str(sub["_id"]),
                "student_id": sub.get("student_id", ""),
                "student_name": sub.get("student_name", "Unknown"),
                "submission_text": sub.get("submission_text"),
                "submission_code": sub.get("submission_code"),
                "submission_link": sub.get("submission_link"),
                "notes": sub.get("notes", ""),
                "submitted_at": sub.get("submitted_at", "").isoformat() if sub.get("submitted_at") else "",
                "score": sub.get("score"),
                "feedback": sub.get("feedback"),
                "status": sub.get("status", "submitted"),
                "graded_at": sub.get("graded_at", "").isoformat() if sub.get("graded_at") else ""
            })
        
        logger.info(f"✓ Retrieved {len(submissions_list)} submissions for assignment {assignment_id}")
        
        return {
            "success": True,
            "assignment_title": assignment.get("title", ""),
            "submissions": submissions_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get submissions error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch submissions: {str(e)}")


@router.post("/api/faculty/submissions/{submission_id}/grade", tags=["Faculty"])
async def grade_submission(
    submission_id: str,
    grade_data: GradeSubmissionForm,
    current_user: dict = Depends(verify_token)
):
    """Faculty grades a student submission"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        # Validate submission_id is a valid ObjectId
        try:
            submission_oid = ObjectId(submission_id)
        except Exception as e:
            logger.error(f"Invalid submission_id: {submission_id} - {e}")
            raise HTTPException(status_code=400, detail="Invalid submission ID format")
        
        # Get submission
        submission = await faculty_submissions_collection.find_one({
            "_id": submission_oid
        })
        
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        
        # Get assignment
        assignment = await assignment_collection.find_one({
            "_id": submission["assignment_id"]
        })
        
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Verify faculty owns the classroom
        classroom = await faculty_classrooms_collection.find_one({
            "_id": assignment["classroom_id"],
            "instructor_id": str(current_user["_id"])
        })
        
        if not classroom:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Validate score doesn't exceed max_score
        if grade_data.score > assignment.get("max_score", 100):
            raise HTTPException(status_code=400, detail=f"Score cannot exceed {assignment.get('max_score', 100)}")
        
        # Update submission with grade
        await faculty_submissions_collection.update_one(
            {"_id": submission_oid},
            {"$set": {
                "score": grade_data.score,
                "feedback": grade_data.feedback,
                "status": "graded",
                "graded_at": datetime.now(timezone.utc)
            }}
        )
        
        logger.info(f"✓ Graded submission {submission_id} with score {grade_data.score}")
        
        return {
            "success": True,
            "message": "Submission graded successfully",
            "score": grade_data.score
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Grade submission error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to grade submission: {str(e)}")


@router.get("/api/faculty/assignments", tags=["Faculty"])
async def get_faculty_assignments(
    classroom_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get faculty assignments"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        query = {"instructor_id": user_id}
        
        if classroom_id:
            query["classroom_id"] = classroom_id
        
        if status:
            if status == "active":
                query["due_date"] = {"$gt": datetime.now(timezone.utc)}
            elif status == "overdue":
                query["due_date"] = {"$lt": datetime.now(timezone.utc)}
                query["status"] = "active"
        
        total = await faculty_assignments_collection.count_documents(query)
        
        assignments = await faculty_assignments_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        # Get submission statistics
        for assignment in assignments:
            submissions = await faculty_submissions_collection.count_documents({
                "assignment_id": str(assignment["_id"])
            })
            graded = await faculty_submissions_collection.count_documents({
                "assignment_id": str(assignment["_id"]),
                "graded": True
            })
            
            assignment["submissions"] = submissions
            assignment["graded"] = graded
            assignment["pending"] = assignment.get("pending", 0) - submissions
        
        return {
            "assignments": [
                {
                    "id": str(assign["_id"]),
                    "title": assign["title"],
                    "classroom_code": assign["classroom_code"],
                    "classroom_name": assign["classroom_name"],
                    "type": assign["type"],
                    "due_date": assign["due_date"],
                    "points": assign["points"],
                    "submissions": assign.get("submissions", 0),
                    "graded": assign.get("graded", 0),
                    "pending": assign.get("pending", 0),
                    "status": "active" if assign["due_date"] > datetime.now(timezone.utc) else "overdue"
                }
                for assign in assignments
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get faculty assignments error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get assignments")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.post("/api/faculty/classrooms/{classroom_id}/assignments", tags=["Faculty"])
async def create_classroom_assignment(
    classroom_id: str,
    title: str = Form(...),
    description: str = Form(...),
    due_date: str = Form(...),
    max_score: int = Form(100),
    submission_type: str = Form("file"),
    assignment_type: str = Form("assignment"),
    topic: str = Form(""),
    status: str = Form("published"),
    publish_date: str = Form(None),
    assign_to: str = Form("all"),
    attachments: str = Form("[]"),
    current_user: dict = Depends(verify_token)
):
    """Faculty creates an assignment for a classroom"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        # Validate classroom_id is a valid ObjectId
        try:
            classroom_oid = ObjectId(classroom_id)
        except Exception as e:
            logger.error(f"Invalid classroom_id: {classroom_id} - {e}")
            raise HTTPException(status_code=400, detail="Invalid classroom ID format")
        
        # Verify classroom exists and faculty owns it
        classroom = await faculty_classrooms_collection.find_one({
            "_id": classroom_oid,
            "instructor_id": str(current_user["_id"])
        })
        
        if not classroom:
            logger.error(f"Classroom not found or unauthorized: {classroom_id}")
            raise HTTPException(status_code=404, detail="Classroom not found or unauthorized")
        
        # Parse due_date
        try:
            due_datetime = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
        except:
            due_datetime = datetime.fromisoformat(due_date)
        
        # Parse attachments JSON
        try:
            import json
            attachments_list = json.loads(attachments)
        except:
            attachments_list = []
        
        # Parse publish_date if scheduled
        publish_datetime = None
        if publish_date and status == "scheduled":
            try:
                publish_datetime = datetime.fromisoformat(publish_date.replace('Z', '+00:00'))
            except:
                try:
                    publish_datetime = datetime.fromisoformat(publish_date)
                except:
                    publish_datetime = datetime.now(timezone.utc)
        
        # Create assignment document
        assignment_doc = {
            "classroom_id": classroom_oid,
            "title": title,
            "description": description,
            "due_date": due_datetime,
            "max_score": max_score,
            "submission_type": submission_type,
            "assignment_type": assignment_type,
            "topic": topic,
            "instructor_id": str(current_user["_id"]),
            "instructor_name": classroom.get("instructor_name", "Unknown"),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "status": status,
            "publish_date": publish_datetime if publish_datetime else datetime.now(timezone.utc),
            "assign_to": assign_to,
            "attachments": attachments_list,
            "submissions_count": 0
        }
        
        # Insert assignment
        result = await assignment_collection.insert_one(assignment_doc)
        
        logger.info(f"✓ Created assignment {result.inserted_id} for classroom {classroom_id}")
        
        return {
            "success": True,
            "assignment_id": str(result.inserted_id),
            "message": "Assignment created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create assignment error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create assignment: {str(e)}")


@router.post("/api/faculty/assignments", tags=["Faculty"])
async def create_assignment(
    assignment_data: AssignmentCreateForm,
    files: List[UploadFile] = File(None),
    current_user: dict = Depends(verify_token)
):
    """Create a new assignment"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        # Check classroom exists
        classroom = await faculty_classrooms_collection.find_one({
            "_id": ObjectId(assignment_data.classroom_id),
            "instructor_id": user_id
        })
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found")
        
        uploaded_urls = []
        
        # Handle file uploads
        if files:
            for file in files:
                try:
                    content = await file.read()
                    
                    # Validate file
                    if len(content) > MAX_FILE_SIZE:
                        continue
                    
                    filename = file.filename or "unnamed_file"
                    file_ext = Path(filename).suffix.lower()
                    if file_ext not in ALLOWED_EXTENSIONS:
                        continue
                    
                    # Save file
                    filename = f"assignment_{uuid.uuid4().hex[:8]}_{file.filename}"
                    filepath = f"static/uploads/{filename}"
                    os.makedirs("static/uploads", exist_ok=True)
                    
                    with open(filepath, "wb") as f:
                        f.write(content)
                    
                    file_url = f"/static/uploads/{filename}"
                    uploaded_urls.append(file_url)
                    
                    # Save to files collection
                    await files_collection.insert_one({
                        "file_id": str(uuid.uuid4()),
                        "name": file.filename,
                        "url": file_url,
                        "type": file.content_type or "application/octet-stream",
                        "size": len(content),
                        "owner_id": user_id,
                        "uploaded_by": current_user["full_name"],
                        "uploaded_at": datetime.now(timezone.utc),
                        "is_public": False,
                        "file_ext": file_ext,
                        "assignment_id": None  # Will be updated after assignment creation
                    })
                    
                except Exception as e:
                    logger.error(f"File upload error: {e}")
                    continue
        
        assignment = {
            "title": assignment_data.title,
            "classroom_id": assignment_data.classroom_id,
            "classroom_code": classroom["code"],
            "classroom_name": classroom["name"],
            "instructor_id": user_id,
            "instructor_name": current_user["full_name"],
            "type": assignment_data.type,
            "due_date": assignment_data.due_date,
            "points": assignment_data.points,
            "instructions": assignment_data.instructions,
            "submission_type": assignment_data.submission_type,
            "requirements": assignment_data.requirements,
            "attachments": uploaded_urls,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "status": "active",
            "submissions": 0,
            "graded": 0,
            "pending": len(classroom.get("students", [])),
            "average_score": 0
        }
        
        result = await faculty_assignments_collection.insert_one(assignment)
        assignment_id = str(result.inserted_id)
        
        # Update files with assignment_id
        if uploaded_urls:
            await files_collection.update_many(
                {"url": {"$in": uploaded_urls}},
                {"$set": {"assignment_id": assignment_id}}
            )
        
        # Update classroom assignment count
        await faculty_classrooms_collection.update_one(
            {"_id": ObjectId(assignment_data.classroom_id)},
            {"$inc": {"assignments": 1}}
        )
        
        # Send notifications to students
        for student_id in classroom.get("students", []):
            await NotificationService.create_notification(
                user_id=student_id,
                title="New Assignment",
                message=f"New assignment '{assignment_data.title}' in {classroom['code']}",
                notification_type="assignment",
                priority="high",
                action_url=f"/assignments/{assignment_id}"
            )
        
        return {
            "message": "Assignment created successfully",
            "assignment_id": assignment_id,
            "assignment": assignment
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create assignment error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create assignment")


