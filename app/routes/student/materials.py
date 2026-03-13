"""
EduSync Backend - Student - Materials Routes
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

router = APIRouter(tags=["Student - Materials"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/student/classroom/{classroom_id}/materials", tags=["Student"])
async def get_student_materials(
    classroom_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get materials for a student's classroom"""
    try:
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
            raise HTTPException(status_code=403, detail="Not enrolled in this classroom")
        
        # Get materials
        materials = classroom.get("materials", [])
        
        return {
            "success": True,
            "materials": materials
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get student materials error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch materials: {str(e)}")


