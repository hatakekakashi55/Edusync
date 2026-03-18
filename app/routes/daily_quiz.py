"""
EduSync Backend - Quizzes Routes
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

router = APIRouter(tags=["Quizzes"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/quiz-questions", tags=["Quizzes"])
async def get_quiz_questions(
    quiz_type: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Fetch quiz questions (Meaning or Fill-in-Blank)"""
    try:
        # Filter to only get quiz questions from communication_tasks_collection
        q = {"is_active": True, "quiz_type": {"$exists": True}}
        
        if quiz_type:
            if quiz_type not in ["meaning", "fill"]:
                raise HTTPException(status_code=400, detail="Invalid quiz_type. Must be 'meaning' or 'fill'")
            q["quiz_type"] = quiz_type
        
        quizzes = []
        async for quiz in communication_tasks_collection.find(q).sort("created_at", -1):
            quiz["_id"] = str(quiz["_id"])
            if "created_by" in quiz:
                quiz["created_by"] = str(quiz["created_by"])
            quizzes.append(quiz)
        
        # If no quizzes found, return empty list (frontend can use defaults)
        return {
            "success": True,
            "quizzes": quizzes,
            "total": len(quizzes)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching quiz questions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/daily-quiz-challenge", tags=["Quizzes"])
async def get_daily_quiz_challenge(
    current_user: dict = Depends(get_current_user)
):
    """Get daily quiz challenge - 5 meaning + 5 fill-in-blanks (changes daily)"""
    try:
        from datetime import date
        import random
        
        # Get today's date as seed for randomization
        today = str(date.today())
        random.seed(today)
        
        # Fetch all active meaning quizzes
        meaning_quizzes = []
        async for quiz in communication_tasks_collection.find({
            "is_active": True, 
            "quiz_type": "meaning"
        }):
            quiz["_id"] = str(quiz["_id"])
            meaning_quizzes.append(quiz)
        
        # Fetch all active fill-in-blank quizzes
        fill_quizzes = []
        async for quiz in communication_tasks_collection.find({
            "is_active": True, 
            "quiz_type": "fill"
        }):
            quiz["_id"] = str(quiz["_id"])
            fill_quizzes.append(quiz)
        
        # Select 5 random from each (or less if not enough)
        daily_meaning = random.sample(meaning_quizzes, min(5, len(meaning_quizzes)))
        daily_fill = random.sample(fill_quizzes, min(5, len(fill_quizzes)))
        
        return {
            "success": True,
            "date": today,
            "meaning_quizzes": daily_meaning,
            "fill_quizzes": daily_fill,
            "total": len(daily_meaning) + len(daily_fill)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching daily quiz challenge: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/daily-challenge/record-completion", tags=["Quizzes"])
async def record_daily_challenge_completion(
    quiz_data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Record daily challenge completion in database"""
    try:
        from datetime import date
        
        today = str(date.today())
        user_id = str(current_user["_id"])
        quiz_type = quiz_data.get("quiz_type")  # "meaning" or "fill"
        score = quiz_data.get("score", 0)
        
        if not quiz_type or quiz_type not in ["meaning", "fill"]:
            raise HTTPException(status_code=400, detail="Invalid quiz_type")
        
        # Update user document with daily challenge progress
        update_result = await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    f"daily_challenges.{today}.{quiz_type}": {
                        "completed": True,
                        "score": score,
                        "timestamp": datetime.now(timezone.utc)
                    }
                }
            },
            upsert=True
        )
        
        # Check if both quizzes are now complete
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if user:
            daily_data = user.get("daily_challenges", {}).get(today, {})
            is_both_complete = daily_data.get("meaning", {}).get("completed", False) and daily_data.get("fill", {}).get("completed", False)
        else:
            is_both_complete = False
        
        return {
            "success": True,
            "recorded": True,
            "both_complete": is_both_complete
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording daily challenge: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/daily-challenge/status", tags=["Quizzes"])
async def get_daily_challenge_status(
    current_user: dict = Depends(get_current_user)
):
    """Get today's daily challenge completion status"""
    try:
        from datetime import date
        
        today = str(date.today())
        user_id = str(current_user["_id"])
        
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            return {"success": False, "completed": False}
        
        daily_data = user.get("daily_challenges", {}).get(today, {})
        meaning_complete = daily_data.get("meaning", {}).get("completed", False)
        fill_complete = daily_data.get("fill", {}).get("completed", False)
        is_complete = meaning_complete and fill_complete
        
        return {
            "success": True,
            "date": today,
            "meaning_completed": meaning_complete,
            "fill_completed": fill_complete,
            "completed": is_complete,
            "data": daily_data
        }
    except Exception as e:
        logger.error(f"Error fetching daily challenge status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


