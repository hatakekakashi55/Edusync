"""
EduSync Backend - Jobs Routes
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

router = APIRouter(tags=["Jobs"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/jobs/matches")
async def get_job_matches(current_user: dict = Depends(verify_token)):
    """Get personalized job matches based on user skills"""
    try:
        user_id = current_user["_id"]
        
        # Get user's resume to find skills
        resume = await resume_collection.find_one({"user_id": user_id})
        user_skills = set(resume.get("skills", [])) if resume else set()
        
        # Get all active jobs
        all_jobs = await jobs_collection.find({"status": "active"}).to_list(length=50)
        
        matched_jobs = []
        for job in all_jobs:
            job_requirements = set(job.get("requirements", []))
            
            # Calculate match score
            if user_skills and job_requirements:
                match_count = len(user_skills.intersection(job_requirements))
                match_score = int((match_count / len(job_requirements)) * 100) if job_requirements else 0
            else:
                match_score = 50  # Default match for users without skills
            
            if match_score > 30:  # Only show jobs with >30% match
                matched_jobs.append({
                    "id": str(job["_id"]),
                    "company": job.get("company", ""),
                    "role": job.get("title", ""),
                    "location": job.get("location", ""),
                    "salary_range": job.get("salary_range", ""),
                    "required_skills": job.get("requirements", [])[:3],
                    "match_score": match_score
                })
        
        # Sort by match score
        matched_jobs.sort(key=lambda x: x["match_score"], reverse=True)
        
        avg_match = int(sum(j["match_score"] for j in matched_jobs) / len(matched_jobs)) if matched_jobs else 0
        
        return {
            "total_matches": len(matched_jobs),
            "average_match_score": avg_match,
            "matched_jobs": matched_jobs[:10]
        }
    except Exception as e:
        logger.error(f"Job matches error: {e}")
        return {
            "total_matches": 0,
            "average_match_score": 0,
            "matched_jobs": []
        }


@router.get("/api/jobs/featured", tags=["Career"])
async def get_featured_jobs(
    limit: int = Query(10, description="Number of jobs"),
    current_user: dict = Depends(verify_token)
):
    """Get featured job listings from database"""
    try:
        featured_jobs = await jobs_collection.find({"is_featured": True, "status": "active"}).sort("posted_at", -1).to_list(limit)
        
        # Convert ObjectId to string
        for job in featured_jobs:
            job["id"] = str(job["_id"])
            del job["_id"]
            
        return {
            "success": True,
            "jobs": featured_jobs,
            "count": len(featured_jobs)
        }
        
    except Exception as e:
        logger.error(f"Get featured jobs error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get featured jobs")


@router.post("/api/jobs/apply", tags=["Career"])
async def apply_for_job(
    job_id: str = Form(...),
    cover_letter: str = Form(None),
    current_user: dict = Depends(verify_token)
):
    """Apply for a job"""
    try:
        user_id = str(current_user["_id"])
        
        # Check if already applied
        existing_application = await db.job_applications.find_one({
            "user_id": user_id,
            "job_id": job_id
        })
        
        if existing_application:
            raise HTTPException(status_code=400, detail="Already applied for this job")
        
        # Create application
        application = {
            "user_id": user_id,
            "user_name": current_user["full_name"],
            "job_id": job_id,
            "cover_letter": cover_letter,
            "resume_url": current_user.get("resume_url"),
            "portfolio_url": current_user.get("portfolio_url"),
            "status": "applied",
            "applied_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        await db.job_applications.insert_one(application)
        
        # Award credits for applying
        await update_user_credits(
            user_id=user_id,
            amount=20,
            source="job_application",
            description=f"Applied for job {job_id}"
        )
        
        return {
            "success": True,
            "message": "Application submitted successfully!",
            "application_id": str(application["_id"]),
            "credits_earned": 20
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Apply for job error: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit application")


@router.get("/api/jobs")
async def get_jobs(limit: int = 50, skip: int = 0):
    try:
        # Fetch active jobs from DB
        jobs_cursor = jobs_collection.find({"status": "active"}).sort("posted_at", -1).skip(skip).limit(limit)
        jobs = await jobs_cursor.to_list(length=limit)
        
        # Convert ObjectIds to strings
        for job in jobs:
            job["_id"] = str(job["_id"])
            if "posted_at" in job and isinstance(job["posted_at"], datetime):
                 job["posted_at"] = job["posted_at"].isoformat()
                 
        return jobs
    except Exception as e:
        logger.error(f"Get jobs error: {e}")
        return []


@router.get("/api/jobs/{job_id}")
async def get_job_details(job_id: str):
    if not ObjectId.is_valid(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID")
    
    job = await jobs_collection.find_one({"_id": ObjectId(job_id)})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    job["_id"] = str(job["_id"])
    if "posted_at" in job and isinstance(job["posted_at"], datetime):
         job["posted_at"] = job["posted_at"].isoformat()
         
    return job


