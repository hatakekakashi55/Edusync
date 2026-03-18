"""
EduSync Backend - Problem Statements Routes
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

router = APIRouter(tags=["Problem Statements"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/problem-statements", tags=["Stage 3"])
async def create_problem_statement(
    ps_data: ProblemStatementCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create a new problem statement (Admin only)"""
    if current_user.get("user_type") != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create problem statements")
    
    try:
        new_ps = ps_data.model_dump()
        new_ps["created_at"] = datetime.now(timezone.utc)
        new_ps["created_by"] = str(current_user["_id"])
        
        if not new_ps.get("ps_number"):
            count = await problem_statements_collection.count_documents({})
            new_ps["ps_number"] = f"SIH{1000 + count + 1}"
            
        result = await problem_statements_collection.insert_one(new_ps)
        new_ps["_id"] = str(result.inserted_id)
        
        return {"success": True, "problem": new_ps}
    except Exception as e:
        logger.error(f"Error creating problem: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/problem-statements/generate-ai", tags=["Stage 3"])
async def generate_ai_problem_statement(
    domain: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user)
):
    """Generate a problem statement using AI"""
    # Relaxed permission: Allow all authenticated users (students, faculty, admin) 
    # to use AI generation for their projects.
    # if current_user.get("user_type") != "admin":
    #     raise HTTPException(status_code=403, detail="Only admins can trigger AI generation")
    
    try:
        model = get_gemini_model("content")
        if not model:
            # Try HOD model as fallback
            model = hod_gemini_model
            
        if not model:
            raise HTTPException(status_code=503, detail="Gemini AI service not available. Check API keys.")
        prompt = f"""
        Generate a professional industry-level problem statement for a hackathon like SIH.
        Domain: {domain}
        
        Respond ONLY with a JSON object:
        {{
            "title": "Clear and impactful title",
            "description": "Detailed description of the problem",
            "organization": "A fictional or real industry name",
            "category": "Software/Hardware",
            "theme": "Current industry theme",
            "credits": 200,
            "difficulty": "Medium/Hard",
            "constraints": ["Constraint 1", "Constraint 2"]
        }}
        """
        
        try:
            if isinstance(model, dict) and "generate_content_async" not in model:
                # Model is a dict wrapper, use call_gemini_with_retry instead
                from app.services.ai_service import call_gemini_with_retry
                response_text = await call_gemini_with_retry(prompt, model)
                content = response_text
            elif hasattr(model, 'generate_content_async'):
                response = await model.generate_content_async(prompt)
                content = response.text
            else:
                raise Exception("Invalid model format")
                
            # Extract JSON from response
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if not match:
                raise Exception("Could not find JSON in response")
            ps_json = json.loads(match.group())
        except Exception as parse_error:
            raise Exception(f"Failed to parse AI response: {str(parse_error)}")
            
        ps_json["mode"] = "ai"
        ps_json["status"] = "open"
        ps_json["created_at"] = datetime.now(timezone.utc)
        ps_json["created_by"] = "ai"
        
        count = await problem_statements_collection.count_documents({})
        ps_json["ps_number"] = f"AI{2000 + count + 1}"
        
        result = await problem_statements_collection.insert_one(ps_json)
        ps_json["_id"] = str(result.inserted_id)
        
        return {"success": True, "problem": ps_json}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating AI problem: {e}")
        # Return a cleaner error message to the client
        error_msg = str(e)
        if "429" in error_msg:
            raise HTTPException(status_code=429, detail="AI Quota Exceeded. Please try again later.")
        if "Json" in error_msg or "parse" in error_msg:
            raise HTTPException(status_code=422, detail="AI produced invalid format. Please try again.")
        raise HTTPException(status_code=500, detail=f"AI Service Error: {error_msg}")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.get("/api/problem-statements", tags=["Stage 3"])
async def list_problem_statements(
    mode: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """List all problem statements"""
    try:
        query = {}
        if mode:
            query["mode"] = mode
        
        problems = await problem_statements_collection.find(query).sort("created_at", -1).to_list(100)
        
        for p in problems:
            p["_id"] = str(p["_id"])
        
        return {"success": True, "problems": problems}
    except Exception as e:
        logger.error(f"Error listing problems: {e}")
        raise HTTPException(status_code=500, detail=str(e))


