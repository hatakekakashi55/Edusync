"""
EduSync Backend - Career - LinkedIn Routes
Modularized and deduplicated.
"""
import logging
import uuid
import aiohttp
from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends, Query, Body

from app.dependencies import verify_token, convert_objectid_to_str
from app.database import *
from app.config import RAPIDAPI_KEY, RAPIDAPI_HOST

logger = logging.getLogger("edusync")

router = APIRouter(prefix="/api/linkedin", tags=["Career - LinkedIn"])

@router.get("/checklist", tags=["Career"])
async def get_linkedin_checklist(current_user: dict = Depends(verify_token)):
    """Get LinkedIn profile checklist"""
    checklist = [
        {"task": "Add a professional profile photo", "completed": True},
        {"task": "Write a compelling headline", "completed": True},
        {"task": "Add a summary to your profile", "completed": False},
        {"task": "List your work experience", "completed": False},
        {"task": "Add 5+ skills", "completed": False},
        {"task": "Customize your public profile URL", "completed": True},
        {"task": "Ask for a recommendation", "completed": False}
    ]
    completed_count = sum(1 for item in checklist if item["completed"])
    
    return {
        "success": True,
        "checklist": checklist,
        "completion_percentage": int((completed_count / len(checklist)) * 100)
    }

@router.get("/analyze", tags=["Career"])
async def analyze_linkedin_profile(current_user: dict = Depends(verify_token)):
    """Analyze LinkedIn profile based on EduSync user data"""
    try:
        user = await users_collection.find_one({"_id": ObjectId(current_user["_id"])})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        score = 0
        recommendations = []
        
        checks = {
            "profile_picture": (20, "Upload a professional profile picture"),
            "headline": (15, "Add a compelling headline"),
            "bio": (15, "Write a detailed summary"),
            "experience": (20, "Add your work experience"),
            "education": (10, "Add your educational background"),
            "skills": (15, "List at least 5 professional skills"),
            "recommendations": (5, "Request recommendations")
        }
        
        for key, (points, rec) in checks.items():
            val = user.get(key)
            if val and (not isinstance(val, list) or len(val) > 0):
                score += points
            else:
                recommendations.append(rec)
        
        return {
            "success": True,
            "score": score,
            "profile_strength": "Strong" if score >= 75 else "Good" if score >= 50 else "Fair",
            "recommendations": recommendations
        }
    except Exception as e:
        logger.error(f"Profile analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs", tags=["Career"])
async def search_linkedin_jobs(
    keywords: str = Query(default="Software Engineer"),
    location: str = Query(default="India"),
    current_user: dict = Depends(verify_token)
):
    """Search LinkedIn jobs with local database fallback"""
    try:
        results = []
        source = "EduSync Database"
        
        # 1. External API (Simulated/RapidAPI)
        if RAPIDAPI_KEY and len(RAPIDAPI_KEY) > 10:
             # Logic for external API...
             pass
             
        # 2. Local Fallback
        search_query = {
            "status": "active",
            "$or": [
                {"title": {"$regex": keywords, "$options": "i"}},
                {"description": {"$regex": keywords, "$options": "i"}}
            ]
        }
        
        db_jobs = await jobs_collection.find(search_query).limit(10).to_list(10)
        for job in db_jobs:
            results.append({
                "id": str(job["_id"]),
                "title": job["title"],
                "company": job["company"],
                "location": job.get("location", "Remote"),
                "jobUrl": job.get("apply_url", "#")
            })
            
        return {
            "success": True,
            "jobs": results,
            "source": source
        }
    except Exception as e:
        logger.error(f"Job search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
