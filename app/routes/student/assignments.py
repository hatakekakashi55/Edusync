"""
EduSync Backend - Student - Assignments Routes
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

router = APIRouter(tags=["Student - Assignments"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/student/classroom/{classroom_id}/assignments", tags=["Student"])
async def get_student_assignments(classroom_id: str, current_user: dict = Depends(verify_token)):
    """Get all assignments for a student in a classroom"""
    try:
        # Validate classroom_id
        try:
            classroom_oid = ObjectId(classroom_id)
        except Exception as e:
            logger.error(f"Invalid classroom_id: {classroom_id} - {e}")
            raise HTTPException(status_code=400, detail="Invalid classroom ID format")
        
        # Check if student is enrolled in this classroom
        classroom = await classrooms_collection.find_one({
            "_id": classroom_oid,
            "students": str(current_user["_id"])
        })
        
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found or not enrolled")
        
        # Get all assignments for this classroom
        assignments = await assignment_collection.find({
            "classroom_id": classroom_oid
        }).sort("due_date", 1).to_list(100)
        
        # Convert to response format with submission status
        assignments_list = []
        for asg in assignments:
            # Check if student has submitted
            submission = await faculty_submissions_collection.find_one({
                "assignment_id": asg["_id"],
                "student_id": str(current_user["_id"])
            })
            
            assignments_list.append({
                "assignment_id": str(asg["_id"]),
                "title": asg.get("title", ""),
                "description": asg.get("description", ""),
                "due_date": asg.get("due_date", "").isoformat() if asg.get("due_date") else "",
                "max_score": asg.get("max_score", 100),
                "submission_type": asg.get("submission_type", "file"),
                "instructor_name": asg.get("instructor_name", "Unknown"),
                "assignment_type": asg.get("assignment_type", "assignment"),
                "topic": asg.get("topic", ""),
                "status": asg.get("status", "published"),
                "attachments": asg.get("attachments", []),
                "submitted": submission is not None,
                "submission_id": str(submission["_id"]) if submission else None,
                "score": submission.get("score") if submission else None,
                "feedback": submission.get("feedback") if submission else None,
                "submitted_at": submission.get("submitted_at", "").isoformat() if submission and submission.get("submitted_at") else ""
            })
        
        logger.info(f"✓ Retrieved {len(assignments_list)} assignments for student in classroom {classroom_id}")
        
        return {
            "success": True,
            "assignments": assignments_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get student assignments error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch assignments: {str(e)}")


@router.post("/api/student/assignments/{assignment_id}/submit", tags=["Student"])
async def submit_assignment(
    assignment_id: str,
    submission_text: str = Form(None),
    submission_code: str = Form(None),
    submission_link: str = Form(None),
    submission_drive_links: str = Form("[]"),
    private_comment: str = Form(""),
    files: List[UploadFile] = File(None),
    current_user: dict = Depends(verify_token)
):
    """Student submits an assignment with optional file uploads"""
    try:
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
        
        # Verify student is in the classroom
        classroom = await classrooms_collection.find_one({
            "_id": assignment["classroom_id"],
            "students": str(current_user["_id"])
        })
        
        if not classroom:
            raise HTTPException(status_code=403, detail="Not enrolled in this classroom")
        
        # Validate at least one submission type
        if not submission_text and not submission_code and not submission_link and not submission_drive_links and not files:
            raise HTTPException(status_code=400, detail="Please provide at least one type of submission (text, code, link, or file)")
        
        # Check if already submitted
        existing = await faculty_submissions_collection.find_one({
            "assignment_id": assignment_oid,
            "student_id": str(current_user["_id"])
        })
        
        # Handle file uploads
        uploaded_files = []
        if files:
            for file in files:
                if file and file.filename:
                    try:
                        # Save file to uploads directory
                        import os
                        import uuid
                        uploads_dir = "static/uploads"
                        os.makedirs(uploads_dir, exist_ok=True)
                        
                        # Generate unique filename
                        file_ext = os.path.splitext(file.filename)[1]
                        unique_filename = f"{uuid.uuid4()}{file_ext}"
                        file_path = os.path.join(uploads_dir, unique_filename)
                        
                        # Save file
                        content = await file.read()
                        with open(file_path, 'wb') as f:
                            f.write(content)
                        
                        uploaded_files.append({
                            "filename": file.filename,
                            "filepath": file_path,
                            "size": len(content)
                        })
                        logger.info(f"✓ File uploaded: {file.filename} -> {file_path}")
                    except Exception as e:
                        logger.error(f"File upload error: {e}")
                        raise HTTPException(status_code=500, detail=f"Failed to upload file {file.filename}")
        
        # Parse drive links JSON
        try:
            import json
            drive_links = json.loads(submission_drive_links) if submission_drive_links != "[]" else []
        except:
            drive_links = []
        
        # Check if submission is late
        due_date = assignment.get("due_date")
        is_late = False
        if due_date:
            # Ensure due_date is timezone-aware for comparison
            if isinstance(due_date, str):
                try:
                    due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                except:
                    due_date = None
            
            # If due_date is naive (no timezone info), make it aware
            if due_date and due_date.tzinfo is None:
                due_date = due_date.replace(tzinfo=timezone.utc)
            
            # Now compare with timezone-aware current time
            if due_date:
                is_late = datetime.now(timezone.utc) > due_date
        
        submission_doc = {
            "assignment_id": assignment_oid,
            "classroom_id": assignment["classroom_id"],
            "student_id": str(current_user["_id"]),
            "student_name": current_user.get("full_name") or f"{current_user.get('first_name', '')} {current_user.get('last_name', '')}".strip(),
            "submission_text": submission_text or "",
            "submission_code": submission_code or "",
            "submission_link": submission_link or "",
            "submitted_files": uploaded_files,
            "drive_links": drive_links,
            "private_comment": private_comment or "",
            "submitted_at": datetime.now(timezone.utc),
            "status": "late" if is_late else "submitted",
            "is_late": is_late,
            "score": None,
            "feedback": None,
            "graded_at": None
        }
        
        if existing:
            # Update existing submission (resubmit)
            await faculty_submissions_collection.update_one(
                {"_id": existing["_id"]},
                {"$set": submission_doc}
            )
            submission_id = str(existing["_id"])
            logger.info(f"✓ Updated submission {submission_id} for assignment {assignment_id}")
        else:
            # Create new submission
            result = await faculty_submissions_collection.insert_one(submission_doc)
            submission_id = str(result.inserted_id)
            
            # Increment submission count
            await assignment_collection.update_one(
                {"_id": assignment_oid},
                {"$inc": {"submissions_count": 1}}
            )
            
            logger.info(f"✓ Created submission {submission_id} for assignment {assignment_id}")
        
        return {
            "success": True,
            "submission_id": submission_id,
            "is_late": is_late,
            "message": f"Assignment submitted successfully{'(LATE)' if is_late else ''}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Submit assignment error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to submit assignment: {str(e)}")


@router.post("/api/student/assignments/{submission_id}/unsubmit", tags=["Student"])
async def unsubmit_assignment(
    submission_id: str,
    current_user: dict = Depends(verify_token)
):
    """Student unsubmits an assignment (before due date)"""
    try:
        # Validate submission_id is a valid ObjectId
        try:
            submission_oid = ObjectId(submission_id)
        except Exception as e:
            logger.error(f"Invalid submission_id: {submission_id} - {e}")
            raise HTTPException(status_code=400, detail="Invalid submission ID format")
        
        # Get submission
        submission = await faculty_submissions_collection.find_one({
            "_id": submission_oid,
            "student_id": str(current_user["_id"])
        })
        
        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")
        
        # Get assignment to check due date
        assignment = await assignment_collection.find_one({
            "_id": submission["assignment_id"]
        })
        
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        # Check if before due date
        due_date = assignment.get("due_date")
        if due_date:
            # Ensure due_date is timezone-aware for comparison
            if isinstance(due_date, str):
                try:
                    due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                except:
                    due_date = None
            
            # If due_date is naive (no timezone info), make it aware
            if due_date and due_date.tzinfo is None:
                due_date = due_date.replace(tzinfo=timezone.utc)
            
            # Now compare with timezone-aware current time
            if due_date and datetime.now(timezone.utc) > due_date:
                raise HTTPException(status_code=403, detail="Cannot unsubmit after due date")
        
        # Delete submission
        await faculty_submissions_collection.delete_one({"_id": submission_oid})
        
        # Decrement submission count
        await assignment_collection.update_one(
            {"_id": submission["assignment_id"]},
            {"$inc": {"submissions_count": -1}}
        )
        
        logger.info(f"✓ Unsubmitted assignment {submission_id}")
        
        return {
            "success": True,
            "message": "Assignment unsubmitted successfully. You can now edit and resubmit."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unsubmit assignment error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to unsubmit assignment: {str(e)}")


