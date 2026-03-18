import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Form
from app.database import *
from app.dependencies import get_current_user, verify_token

logger = logging.getLogger("edusync")

router = APIRouter(prefix="/api/career", tags=["Career & Placement"])

@router.get("/jobs/matches", tags=["Career"])
async def get_job_matches(
    limit: int = Query(10, description="Number of matches"),
    current_user: dict = Depends(verify_token)
):
    """Get job matches based on user's real skills from database"""
    try:
        user_id = str(current_user["_id"])
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get user's resume or profile skills
        resume = await resume_collection.find_one({"user_id": user_id})
        user_skills = set([s.lower() for s in user.get("skills", [])])
        if resume:
            user_skills.update([s.lower() for s in resume.get("skills", [])])
        
        # Fetch all active jobs
        all_jobs = await jobs_collection.find({"status": "active"}).to_list(length=100)
        
        if not all_jobs:
            return {
                "success": True,
                "total_matches": 0,
                "matched_jobs": [],
                "message": "No active jobs found. Please try again later."
            }
            
        matched_jobs = []
        for job in all_jobs:
            job_requirements = [r.lower() for r in job.get("requirements", [])]
            if not job_requirements:
                job_requirements = [s.lower() for s in job.get("skills", [])]
            
            job_req_set = set(job_requirements)
            common_skills = user_skills.intersection(job_req_set)
            
            # Calculate match percentage
            if job_req_set:
                match_percentage = int((len(common_skills) / len(job_req_set)) * 100)
            else:
                match_percentage = 50 # Default for jobs with no specific requirements
                
            matched_jobs.append({
                "id": str(job.get("_id")),
                "company": job.get("company", "Unknown"),
                "role": job.get("title", job.get("role", "Developer")),
                "location": job.get("location", "Remote"),
                "salary_range": job.get("salary_range", "Competitive"),
                "experience_required": job.get("experience_required", "0-1 year"),
                "required_skills": job.get("requirements", job.get("skills", [])),
                "match_score": match_percentage,
                "matching_skills": list(common_skills)
            })
            
        # Sort by match score
        matched_jobs.sort(key=lambda x: x["match_score"], reverse=True)
        
        # Calculate summary stats for frontend
        total_matches = len(matched_jobs)
        avg_match_score = sum(j["match_score"] for j in matched_jobs) / total_matches if total_matches > 0 else 0
        
        return {
            "success": True,
            "total_matches": total_matches,
            "average_match_score": round(avg_match_score, 1),
            "skills_match": round(avg_match_score * 0.8, 1),
            "experience_match": 100 if user and user.get("experience") else 50,
            "project_match": min(100, (await projects_collection.count_documents({"owner_id": user_id})) * 33),
            "goals_match": 85 if user and user.get("career_goals") else 0,
            "matched_jobs": matched_jobs[:limit],
            "skill_demand": "High" if avg_match_score > 70 else "Medium",
            "salary_range": "₹4 - ₹18 LPA",
            "hiring_companies": len(set(j["company"] for j in matched_jobs)),
            "growth_potential": min(100, int(avg_match_score * 1.1))
        }
        
    except Exception as e:
        logger.error(f"Get job matches error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get job matches")


@router.get("/jobs/featured", tags=["Career"])
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
            if "_id" in job: del job["_id"]
            
        return {
            "success": True,
            "jobs": featured_jobs,
            "count": len(featured_jobs)
        }
        
    except Exception as e:
        logger.error(f"Get featured jobs error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get featured jobs")


@router.post("/jobs/apply", tags=["Career"])
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
