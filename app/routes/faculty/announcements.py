"""
EduSync Backend - Faculty - Announcements Routes
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

router = APIRouter(tags=["Faculty - Announcements"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/faculty/classrooms/{classroom_id}/announcements", tags=["Faculty"])
async def get_classroom_announcements(
    classroom_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get all announcements for a classroom"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        # Validate classroom_id
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
        
        # Get announcements
        announcements = await announcements_collection.find({
            "classroom_id": classroom_oid
        }).sort("created_at", -1).to_list(100)
        
        announcements_list = []
        for ann in announcements:
            announcements_list.append({
                "id": str(ann["_id"]),
                "title": ann.get("title", ""),
                "content": ann.get("content", ""),
                "date": ann.get("created_at", "").isoformat() if ann.get("created_at") else "",
                "attachments": ann.get("attachments", []),
                "faculty_name": ann.get("faculty_name", "")
            })
        
        return {
            "success": True,
            "announcements": announcements_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get announcements error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch announcements: {str(e)}")


@router.delete("/api/faculty/classrooms/{classroom_id}/announcements/{announcement_id}", tags=["Faculty"])
async def delete_announcement(
    classroom_id: str,
    announcement_id: str,
    current_user: dict = Depends(verify_token)
):
    """Delete an announcement"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        # Validate IDs
        try:
            classroom_oid = ObjectId(classroom_id)
            announcement_oid = ObjectId(announcement_id)
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
        
        # Verify announcement exists and belongs to this classroom
        announcement = await announcements_collection.find_one({
            "_id": announcement_oid,
            "classroom_id": classroom_oid
        })
        
        if not announcement:
            raise HTTPException(status_code=404, detail="Announcement not found")
        
        # Delete the announcement
        result = await announcements_collection.delete_one({
            "_id": announcement_oid
        })
        
        if result.deleted_count > 0:
            logger.info(f"✓ Deleted announcement {announcement_id}")
            return {
                "success": True,
                "message": "Announcement deleted successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to delete announcement")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete announcement error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete announcement: {str(e)}")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.post("/api/faculty/classrooms/{classroom_id}/announcements", tags=["Faculty"])
async def post_announcement(
    classroom_id: str,
    announcement: AnnouncementCreate,
    current_user: dict = Depends(verify_token)
):
    """Faculty posts an announcement to a classroom"""
    try:
        logger.info(f"POST announcement: classroom_id={classroom_id}, faculty_id={str(current_user.get('_id'))}")
        
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
        
        # Create announcement document
        announcement_doc = {
            "classroom_id": classroom_oid,
            "title": announcement.title,
            "content": announcement.content,
            "faculty_id": str(current_user["_id"]),
            "faculty_name": classroom.get("instructor_name", "Unknown"),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Insert announcement
        result = await announcements_collection.insert_one(announcement_doc)
        
        logger.info(f"✓ Posted announcement {result.inserted_id} to classroom {classroom_id}")
        
        return {
            "success": True,
            "announcement_id": str(result.inserted_id),
            "message": "Announcement posted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Post announcement error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to post announcement: {str(e)}")


