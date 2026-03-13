"""
EduSync Backend - Student - Announcements Routes
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

router = APIRouter(tags=["Student - Announcements"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/student/classroom/{classroom_id}/announcements", tags=["Student"])
async def get_announcements(
    classroom_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get announcements for a classroom the student is enrolled in"""
    try:
        logger.info(f"GET announcements: classroom_id={classroom_id}, student_id={str(current_user.get('_id'))}")
        
        # Validate classroom_id is a valid ObjectId
        try:
            classroom_oid = ObjectId(classroom_id)
        except Exception as e:
            logger.error(f"Invalid classroom_id: {classroom_id} - {e}")
            raise HTTPException(status_code=400, detail="Invalid classroom ID format")
        
        # Verify student is in this classroom
        classroom = await classrooms_collection.find_one({
            "_id": classroom_oid,
            "students": str(current_user["_id"])
        })
        
        if not classroom:
            logger.error(f"Classroom not found or student not enrolled: {classroom_id}")
            raise HTTPException(status_code=404, detail="Classroom not found or not enrolled")
        
        # Fetch announcements ordered by newest first
        announcements = await announcements_collection.find({
            "classroom_id": classroom_oid
        }).sort("created_at", -1).to_list(100)
        
        # Convert to proper response format
        announcements_list = []
        for ann in announcements:
            announcements_list.append({
                "announcement_id": str(ann["_id"]),
                "title": ann.get("title", ""),
                "content": ann.get("content", ""),
                "faculty_name": ann.get("faculty_name", "Unknown"),
                "created_at": ann.get("created_at", "").isoformat() if ann.get("created_at") else "",
                "updated_at": ann.get("updated_at", "").isoformat() if ann.get("updated_at") else ""
            })
        
        logger.info(f"✓ Retrieved {len(announcements_list)} announcements for classroom {classroom_id}")
        
        return {
            "success": True,
            "announcements": announcements_list
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get announcements error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch announcements: {str(e)}")


