"""
EduSync Backend - Career - Applications Routes
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

router = APIRouter(tags=["Career - Applications"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/applications", tags=["Career"])
async def get_job_applications(
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(verify_token)
):
    """Get user's job applications"""
    try:
        user_id = str(current_user["_id"])
        
        query = {"user_id": user_id}
        if status:
            query["status"] = status
        
        applications = await db.job_applications.find(query).sort("applied_at", -1).to_list(50)
        
        status_counts = {
            "applied": await db.job_applications.count_documents({"user_id": user_id, "status": "applied"}),
            "reviewed": await db.job_applications.count_documents({"user_id": user_id, "status": "reviewed"}),
            "interview": await db.job_applications.count_documents({"user_id": user_id, "status": "interview"}),
            "rejected": await db.job_applications.count_documents({"user_id": user_id, "status": "rejected"}),
            "offer": await db.job_applications.count_documents({"user_id": user_id, "status": "offer"})
        }
        
        return {
            "success": True,
            "applications": [
                {
                    "id": str(app["_id"]),
                    "job_id": app.get("job_id"),
                    "company": app.get("company"),
                    "role": app.get("role"),
                    "status": app.get("status"),
                    "applied_at": app.get("applied_at"),
                    "updated_at": app.get("updated_at"),
                    "next_step": app.get("next_step")
                }
                for app in applications
            ],
            "total_applications": len(applications),
            "pending": status_counts["applied"] + status_counts["reviewed"],
            "accepted": status_counts["offer"],
            "rejected": status_counts["rejected"],
            "status_counts": status_counts
        }
        
    except Exception as e:
        logger.error(f"Get job applications error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get job applications")


