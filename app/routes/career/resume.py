"""
EduSync Backend - Career - Resume Routes
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
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

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

router = APIRouter(tags=["Career - Resume"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/resume/generate")
async def generate_resume_pdf(
    template_id: str = Form("1"),
    current_user: dict = Depends(verify_token)
):
    try:
        # Create PDF directory
        pdf_dir = Path("static/uploads")
        pdf_dir.mkdir(parents=True, exist_ok=True)
        
        pdf_filename = f"resume_{current_user['_id']}_{int(datetime.now().timestamp())}.pdf"
        pdf_path = pdf_dir / pdf_filename
        
        # Determine full absolute path for reportlab to avoid permission issues
        full_path = str(pdf_path.resolve())
        
        c = canvas.Canvas(full_path, pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 750, current_user.get("full_name", "Student Name"))
        
        c.setFont("Helvetica", 12)
        c.drawString(50, 730, f"Email: {current_user.get('email', '')}")
        c.drawString(50, 715, f"Department: {current_user.get('department', '')}")
        
        c.line(50, 700, 550, 700)
        
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, 680, "Professional Profile")
        
        c.setFont("Helvetica", 11)
        # Fetch resume data to populate
        resume = await resume_collection.find_one({"user_id": current_user["_id"]})
        if resume:
            c.drawString(50, 660, resume.get("summary", "No summary provided."))
            
            y_pos = 630
            if "skills" in resume and resume["skills"]:
                c.setFont("Helvetica-Bold", 14)
                c.drawString(50, y_pos, "Skills")
                y_pos -= 20
                c.setFont("Helvetica", 11)
                c.drawString(50, y_pos, ", ".join(resume["skills"]))
                y_pos -= 30
        else:
             c.drawString(50, 660, "No resume profile data found. Please update your profile.")

        c.save()
        
        # Return URL
        return {
            "success": True, 
            "resume_url": f"http://localhost:8000/static/uploads/{pdf_filename}"
        }
    except Exception as e:
        logger.error(f"PDF Gen Error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate resume: {str(e)}")


@router.get("/api/resume/me")
async def get_my_resume(current_user: dict = Depends(verify_token)):
    resume = await resume_collection.find_one({"user_id": current_user["_id"]})
    
    user_data = {
        "user_id": str(current_user["_id"]),
        "full_name": current_user.get("full_name", ""),
        "email": current_user.get("email", ""),
        "phone": current_user.get("phone", ""),
        "department": current_user.get("department", "")
    }
    
    if not resume:
        # Return base user data if no resume exists
        return {
            **user_data,
            "education": [],
            "experience": [],
            "skills": []
        }
        
    resume["_id"] = str(resume["_id"])
    resume["user_id"] = str(resume["user_id"])
    return {**user_data, **resume}


@router.post("/api/resume/save")
async def save_resume(resume_data: ResumeUpdate, current_user: dict = Depends(verify_token)):
    # Upsert resume
    await resume_collection.update_one(
        {"user_id": current_user["_id"]},
        {"$set": {
            **resume_data.model_dump(exclude_unset=True),
            "updated_at": datetime.now(timezone.utc),
            "full_name": current_user.get("full_name"),
            "email": current_user.get("email")
        }},
        upsert=True
    )
    return {"message": "Resume saved successfully"}


