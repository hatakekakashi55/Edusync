"""
EduSync Backend - Leaderboard Routes
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

router = APIRouter(tags=["Leaderboard"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/leaderboard", tags=["Leaderboard"])
async def get_leaderboard(
    period: str = Query("weekly", pattern="^(weekly|monthly|all_time)$"),
    department: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(verify_token)
):
    """Get leaderboard with filters"""
    try:
        user_id = str(current_user["_id"])
        
        # For weekly leaderboard
        if period == "weekly":
            # Get submissions from last 7 days
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            
            pipeline = [
                {"$match": {
                    "submitted_at": {"$gte": week_ago},
                    "completed": True
                }},
                {"$group": {
                    "_id": "$user_id",
                    "total_score": {"$sum": "$score"},
                    "challenges_completed": {"$sum": 1},
                    "average_score": {"$avg": "$score"}
                }},
                {"$sort": {"total_score": -1}},
                {"$limit": limit},
                {"$lookup": {
                    "from": "users",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "user"
                }},
                {"$unwind": "$user"},
                {"$match": {
                    "user.user_type": UserType.STUDENT.value,
                    **({"user.department": department} if department else {}),
                    **({"user.year": year} if year else {})
                }},
                {"$project": {
                    "user_id": "$_id",
                    "user_name": "$user.full_name",
                    "department": "$user.department",
                    "year": "$user.year",
                    "stage": "$user.stage",
                    "profile_picture": "$user.profile_picture",
                    "total_score": 1,
                    "challenges_completed": 1,
                    "average_score": 1
                }}
            ]
            
            leaderboard = list(await submissions_collection.aggregate(pipeline).to_list(length=limit))
            
        else:
            # For monthly/all_time, get from leaderboard collection
            query = {"period": period}
            if period == "monthly":
                month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                query["month_start"] = {"$lte": datetime.now(timezone.utc)}
            
            leaderboard_entries = await leaderboard_collection.find(query) \
                .sort("total_score", -1) \
                .limit(limit) \
                .to_list(limit)
            
            # Get user details
            leaderboard = []
            for entry in leaderboard_entries:
                user = await users_collection.find_one({"_id": ObjectId(entry["user_id"])})
                if user and user["user_type"] == UserType.STUDENT.value:
                    if (department and user.get("department") != department) or \
                       (year and user.get("year") != year):
                        continue
                    
                    leaderboard.append({
                        "user_id": entry["user_id"],
                        "user_name": user["full_name"],
                        "department": user.get("department"),
                        "year": user.get("year"),
                        "stage": user.get("stage"),
                        "profile_picture": user.get("profile_picture"),
                        "total_score": entry["total_score"],
                        "challenges_completed": entry["challenges_completed"],
                        "average_score": entry.get("average_score", 0)
                    })
        
        # Get user's rank and score
        user_rank = 0
        user_score = 0
        
        for idx, entry in enumerate(leaderboard):
            if entry["user_id"] == user_id:
                user_rank = idx + 1
                user_score = entry["total_score"]
                break
        
        return {
            "period": period,
            "leaderboard": [
                {
                    "rank": idx + 1,
                    **entry
                }
                for idx, entry in enumerate(leaderboard)
            ],
            "user_stats": {
                "rank": user_rank,
                "score": user_score,
                "in_top": user_rank > 0 and user_rank <= limit
            }
        }
        
    except Exception as e:
        logger.error(f"Get leaderboard error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get leaderboard")


@router.get("/api/leaderboard/career")
async def get_career_leaderboard(current_user: dict = Depends(verify_token)):
    """Get career readiness leaderboard"""
    try:
        # Get all users with their interview stats
        all_users = await users_collection.find({}).to_list(length=100)
        
        leaderboard_data = []
        for user in all_users:
            user_id = user["_id"]
            
            # Calculate score based on interviews and resume
            interviews_count = await interviews_collection.count_documents({
                "user_id": user_id,
                "status": "completed"
            })
            
            resume = await resume_collection.find_one({"user_id": user_id})
            
            score = interviews_count * 10
            if resume:
                score += len(resume.get("skills", [])) * 2
                score += len(resume.get("experience", [])) * 5
            
            badges = await badges_collection.count_documents({"user_id": str(user_id)})
            
            leaderboard_data.append({
                "name": user.get("full_name", "Unknown"),
                "score": score,
                "badges": badges
            })
        
        # Sort by score
        leaderboard_data.sort(key=lambda x: x["score"], reverse=True)
        
        # Find current user's rank
        current_user_id = str(current_user["_id"])
        your_rank = 0
        your_score = 0
        your_badges = 0
        
        for idx, entry in enumerate(leaderboard_data):
            if entry["name"] == current_user.get("full_name"):
                your_rank = idx + 1
                your_score = entry["score"]
                your_badges = entry["badges"]
                break
        
        return {
            "your_rank": your_rank if your_rank > 0 else len(leaderboard_data) + 1,
            "your_score": your_score,
            "your_badges": your_badges,
            "leaderboard": leaderboard_data[:10]
        }
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        return {
            "your_rank": 0,
            "your_score": 0,
            "your_badges": 0,
            "leaderboard": []
        }


