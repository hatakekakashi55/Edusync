"""
EduSync Backend - HOD - Analytics Routes
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

router = APIRouter(tags=["HOD - Analytics"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/hod/analytics", tags=["HOD"])
async def get_department_analytics(
    request: DepartmentStats,
    current_user: dict = Depends(verify_token)
):
    """Get detailed department analytics"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Get comprehensive analytics
        stats = await calculate_department_stats(department, request.academic_year)
        
        # Get faculty performance trends
        faculty_list = await users_collection.find({
            "user_type": UserType.FACULTY.value,
            "department": department
        }).to_list(50)
        
        faculty_performance = []
        for faculty in faculty_list:
            performance = await get_faculty_stats(str(faculty["_id"]))
            if performance:
                faculty_performance.append(performance)
        
        # Calculate averages
        avg_rating = sum(f["avg_rating"] for f in faculty_performance) / len(faculty_performance) if faculty_performance else 0
        avg_workload = sum(f["workload_percentage"] for f in faculty_performance) / len(faculty_performance) if faculty_performance else 0
        
        # ... (மீதமுள்ள கோட்)
        
        result = {
            "department": department,
            "academic_year": request.academic_year,
            "period": request.period,
            "overview": convert_objectid_to_str(stats["stats"]) if stats else {},
            "faculty_performance": convert_objectid_to_str(faculty_performance),
            # ... (மீதமுள்ள fields)
        }
        
        return convert_objectid_to_str(result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Department analytics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get department analytics")


