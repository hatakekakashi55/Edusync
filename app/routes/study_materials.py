"""
EduSync Backend - Study Materials Routes
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

router = APIRouter(tags=["Study Materials"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/study-materials", tags=["Study Materials"])
async def get_study_materials(
    department: Optional[str] = None,
    year: Optional[int] = None,
    subject: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get study materials"""
    try:
        query = {}
        
        if department:
            query["department"] = department
        if year:
            query["year"] = year
        if subject:
            query["subject"] = {"$regex": subject, "$options": "i"}
        
        total = await study_materials_collection.count_documents(query)
        
        materials = await study_materials_collection.find(query) \
            .sort("uploaded_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "materials": [
                {
                    "id": str(mat["_id"]),
                    "title": mat["title"],
                    "description": mat.get("description", ""),
                    "subject": mat["subject"],
                    "department": mat.get("department"),
                    "year": mat.get("year"),
                    "file_url": mat["file_url"],
                    "file_type": mat.get("file_type"),
                    "file_size": mat.get("file_size"),
                    "uploaded_by": mat.get("uploaded_by_name"),
                    "uploaded_at": mat["uploaded_at"],
                    "download_count": mat.get("download_count", 0),
                    "tags": mat.get("tags", [])
                }
                for mat in materials
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get study materials error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get study materials")


