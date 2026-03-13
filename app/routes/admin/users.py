"""
EduSync Backend - Admin Routes
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
from app.routes.health import health_check
from app.utils.auth import hash_password
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

router = APIRouter(tags=["Admin"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor


# Note: Admin stats and transactions endpoints 
# have been moved to app/routes/admin/stats.py to avoid duplication.

@router.get("/api/admin/users", tags=["Admin"])
async def get_all_users(current_user: dict = Depends(verify_token)):
    """Get all users for admin management"""
    try:
        if current_user.get("user_type") not in ["admin", "hod"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        users = await users_collection.find().to_list(length=None)
        
        # Remove sensitive data
        for user in users:
            user["_id"] = str(user["_id"])
            if "password" in user:
                del user["password"]
        
        return {"users": users}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get users error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")


@router.post("/api/admin/users/create", tags=["Admin"])
async def create_user_admin(
    full_name: str = Body(...),
    email: str = Body(...),
    password: str = Body(...),
    user_type: str = Body(...),
    stage: str = Body(None),  # For students
    department: str = Body(None),  # For faculty and HOD
    phone: str = Body(None),  # Optional for all
    specialization: str = Body(None),  # Optional for faculty
    year: int = Body(None),
    credits: int = Body(100),
    status: str = Body("active"),
    current_user: dict = Depends(verify_token)
):
    """Admin create user account"""
    try:
        if current_user.get("user_type") not in ["admin", "hod"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Check if user exists
        existing = await users_collection.find_one({"email": email})
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Validate user type
        if user_type not in ["student", "faculty", "hod"]:
            raise HTTPException(status_code=400, detail="Invalid user type")
        
        # Create user
        hashed_password = hash_password(password)
        user_data = {
            "full_name": full_name,
            "email": email,
            "password": hashed_password,
            "user_type": user_type,
            "is_active": status == "active",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Add type-specific fields
        if user_type == "student":
            user_data["stage"] = stage or "freshie"
            user_data["year"] = year or 1
            user_data["credits"] = credits
        elif user_type == "faculty":
            user_data["department"] = department or ""
            user_data["specialization"] = specialization or ""
        elif user_type == "hod":
            user_data["department"] = department or ""
        
        # Add optional phone for all
        if phone:
            user_data["phone"] = phone
        
        result = await users_collection.insert_one(user_data)
        
        return {
            "message": "User created successfully",
            "user_id": str(result.inserted_id),
            "email": email
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create user error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user")


@router.delete("/api/admin/users/{user_id}", tags=["Admin"])
async def delete_user_admin(user_id: str, current_user: dict = Depends(verify_token)):
    """Admin delete user"""
    try:
        if current_user.get("user_type") not in ["admin", "hod"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        result = await users_collection.delete_one({"_id": ObjectId(user_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {"message": "User deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete user error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete user")


@router.post("/api/admin/users/{user_id}/deactivate", tags=["Admin"])
async def deactivate_user(user_id: str, current_user: dict = Depends(verify_token)):
    """Deactivate user account"""
    try:
        if current_user.get("user_type") not in ["admin", "hod"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}}
        )
        
        return {"message": "User deactivated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deactivate user error: {e}")
        raise HTTPException(status_code=500, detail="Failed to deactivate user")


@router.post("/api/admin/users/{user_id}/activate", tags=["Admin"])
async def activate_user(user_id: str, current_user: dict = Depends(verify_token)):
    """Reactivate user account"""
    try:
        if current_user.get("user_type") not in ["admin", "hod"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_active": True, "updated_at": datetime.now(timezone.utc)}}
        )
        
        return {"message": "User activated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Activate user error: {e}")
        raise HTTPException(status_code=500, detail="Failed to activate user")



@router.post("/api/admin/credits/adjust", tags=["Admin"])
async def adjust_user_credits(
    user_id: str = Body(...),
    adjustment_type: str = Body(...),  # "add", "subtract", "set"
    amount: int = Body(...),
    reason: str = Body(...),
    description: str = Body(None),
    current_user: dict = Depends(verify_token)
):
    """Admin adjust user credits"""
    try:
        if current_user.get("user_type") not in ["admin", "hod"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get current user credits
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        current_credits = user.get("credits", 0)
        new_credits = current_credits
        
        if adjustment_type == "add":
            new_credits = current_credits + amount
        elif adjustment_type == "subtract":
            new_credits = max(0, current_credits - amount)
        elif adjustment_type == "set":
            new_credits = amount
        
        # Update user credits
        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"credits": new_credits, "updated_at": datetime.now(timezone.utc)}}
        )
        
        # Log transaction
        transaction_data = {
            "user_id": user_id,
            "user_name": user.get("full_name"),
            "user_email": user.get("email"),
            "transaction_type": "adjustment",
            "amount": amount if adjustment_type == "add" else -amount,
            "source": "admin_adjustment",
            "reason": reason,
            "description": description,
            "previous_credits": current_credits,
            "new_credits": new_credits,
            "created_at": datetime.now(timezone.utc),
            "admin_id": str(current_user["_id"])
        }
        
        await db["credit_transactions"].insert_one(transaction_data)
        
        return {
            "message": "Credits adjusted successfully",
            "previous_credits": current_credits,
            "new_credits": new_credits
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Adjust credits error: {e}")
        raise HTTPException(status_code=500, detail="Failed to adjust credits")


@router.post("/api/admin/quiz-questions", tags=["Admin", "Quizzes"])
async def create_quiz_question(
    quiz_data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Admin: Create a new quiz question (Meaning or Fill-in-Blank)"""
    try:
        if current_user.get("user_type") not in ["admin", "hod"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        logger.info(f"Creating quiz question with data: {quiz_data}")
        
        # Validate required fields
        required_fields = ["quiz_type", "word"]
        for field in required_fields:
            if field not in quiz_data or not quiz_data[field]:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        quiz_type = quiz_data.get("quiz_type")  # 'meaning' or 'fill'
        
        if quiz_type not in ["meaning", "fill"]:
            raise HTTPException(status_code=400, detail="Invalid quiz_type. Must be 'meaning' or 'fill'")
        
        # Base quiz document
        quiz_doc = {
            "quiz_type": quiz_type,
            "word": (quiz_data.get("word") or "").strip(),
            "points": int(quiz_data.get("points", 10)) if quiz_data.get("points") else 10,
            "is_active": quiz_data.get("is_active", True),
            "created_by": str(current_user.get("_id")),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Type-specific validation and fields
        if quiz_type == "meaning":
            if "meaning" not in quiz_data or not quiz_data["meaning"]:
                raise HTTPException(status_code=400, detail="Missing required field: meaning")
            if "options" not in quiz_data or len(quiz_data["options"]) != 4:
                raise HTTPException(status_code=400, detail="Must provide exactly 4 options for meaning quiz")
            if "correct" not in quiz_data:
                raise HTTPException(status_code=400, detail="Missing required field: correct")
            if not (isinstance(quiz_data["correct"], int) and 0 <= quiz_data["correct"] <= 3):
                raise HTTPException(status_code=400, detail="Correct answer must be between 0 and 3")
            
            quiz_doc["meaning"] = (quiz_data.get("meaning") or "").strip()
            quiz_doc["options"] = [str(opt).strip() for opt in quiz_data["options"]]
            quiz_doc["correct"] = int(quiz_data["correct"])
            
        elif quiz_type == "fill":
            if "sentence" not in quiz_data or not quiz_data["sentence"]:
                raise HTTPException(status_code=400, detail="Missing required field: sentence")
            
            quiz_doc["sentence"] = (quiz_data.get("sentence") or "").strip()
            quiz_doc["hint"] = (quiz_data.get("hint") or "").strip() or ""
            quiz_doc["difficulty"] = quiz_data.get("difficulty", "intermediate")
        
        logger.info(f"Quiz document to insert: {quiz_doc}")
        
        # Insert into database
        result = await communication_tasks_collection.insert_one(quiz_doc)
        
        quiz_doc["_id"] = str(result.inserted_id)
        
        logger.info(f"Quiz question created with ID: {quiz_doc['_id']}")
        
        return {
            "success": True,
            "message": "Quiz question created successfully",
            "quiz": quiz_doc
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating quiz question: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


