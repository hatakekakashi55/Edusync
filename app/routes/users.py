"""
EduSync Backend - Users Routes
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

router = APIRouter(tags=["Users"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.put("/api/users/profile", tags=["Users"])
async def update_profile(
    update_data: UserUpdate,
    current_user: dict = Depends(verify_token)
):
    """Update user profile"""
    try:
        user_id = str(current_user["_id"])
        
        # Prepare update
        update_dict = update_data.model_dump(exclude_unset=True)
        update_dict["updated_at"] = datetime.now(timezone.utc)
        
        # Update user
        result = await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_dict}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="No changes made")
        
        # Get updated user
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if user:
            user.pop("password", None)
            user["_id"] = str(user["_id"])
        else:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "message": "Profile updated successfully",
            "user": user
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update profile error: {e}")
        raise HTTPException(status_code=500, detail="Profile update failed")


@router.post("/api/users/profile/picture", tags=["Users"])
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: dict = Depends(verify_token)
):
    """Upload profile picture"""
    try:
        user_id = str(current_user["_id"])
        
        # Validate file
        content, file_size = await validate_file(file)
        
        # Upload to cloud storage
        upload_result = await upload_to_cloud_storage(
            content,
            f"profile_{user_id}_{datetime.now().timestamp()}.jpg",
            "image/jpeg"
        )
        
        # Update user profile
        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "profile_picture": upload_result["url"],
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        return {
            "message": "Profile picture uploaded successfully",
            "url": upload_result["url"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload profile picture error: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload profile picture")


@router.get("/api/users/all", tags=["Users"])
async def get_all_users(
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    user_type: Optional[str] = Query(None),
    current_user: dict = Depends(verify_token)
):
    """Get all registered users with optional search and filtering"""
    try:
        query = {}
        
        # Filter by user_type if specified
        if user_type:
            query["user_type"] = user_type
        
        # Search by name or email
        if search:
            search_pattern = {"$regex": search, "$options": "i"}
            query["$or"] = [
                {"full_name": search_pattern},
                {"email": search_pattern},
                {"department": search_pattern}
            ]
        
        users = await users_collection.find(query) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        result_users = []
        for user in users:
            result_users.append({
                "id": str(user["_id"]),
                "name": user.get("full_name", user.get("name", "Unknown")),
                "email": user.get("email", ""),
                "user_type": user.get("user_type", "student"),
                "department": user.get("department", ""),
                "year": user.get("year", ""),
                "profile_picture": user.get("profile_picture", ""),
                "phone": user.get("phone", "")
            })
        
        return {"success": True, "users": result_users, "count": len(result_users)}
    except Exception as e:
        logger.error(f"Error getting all users: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch users")


@router.get("/api/users/mail-recipients", tags=["Users"])
async def get_mail_recipients(
    search: Optional[str] = Query(None),
    current_user: dict = Depends(verify_token)
):
    """Get users for mail recipient selection (excluding current user)"""
    try:
        current_user_id = ObjectId(current_user["_id"])
        query = {"_id": {"$ne": current_user_id}}
        
        if search:
            search_pattern = {"$regex": search, "$options": "i"}
            query["$or"] = [
                {"full_name": search_pattern},
                {"email": search_pattern},
                {"department": search_pattern}
            ]
        
        users = await users_collection.find(query).limit(50).to_list(50)
        
        result_users = []
        for user in users:
            result_users.append({
                "id": str(user["_id"]),
                "name": user.get("full_name", user.get("name", "Unknown")),
                "email": user.get("email", ""),
                "user_type": user.get("user_type", "student"),
                "department": user.get("department", "")
            })
        
        return {"success": True, "users": result_users}
    except Exception as e:
        logger.error(f"Error getting mail recipients: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch recipients")


@router.get("/api/users/search", tags=["Users"])
async def search_users(
    query: str,
    current_user: dict = Depends(verify_token)
):
    try:
        users = await users_collection.find({
            "$or": [
                {"full_name": {"$regex": query, "$options": "i"}},
                {"email": {"$regex": query, "$options": "i"}}
            ]
        }).limit(20).to_list(length=20)
        
        results = []
        for user in users:
            results.append({
                "id": str(user["_id"]),
                "name": user.get("full_name", "Unknown"),
                "department": user.get("department", ""),
                "year": user.get("year", ""),
                "profile_picture": user.get("profile_picture")
            })
        return {"success": True, "users": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Search failed")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.get("/api/users/profile", tags=["Users"])
async def get_profile(current_user: dict = Depends(verify_token)):
    """Get current user profile"""
    try:
        user_id = str(current_user["_id"])
        
        # Get user with extended data
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get badges
        badges_doc = await badges_collection.find_one({"user_id": user_id})
        badges = badges_doc.get("badges", []) if badges_doc else []
        
        # Get stats
        total_submissions = await submissions_collection.count_documents({"user_id": user_id})
        completed_challenges = await submissions_collection.count_documents({
            "user_id": user_id,
            "completed": True
        })
        
        # Get repository stats
        repo_count = await code_repositories_collection.count_documents({"owner_id": user_id})
        
        # Remove sensitive data
        user.pop("password", None)
        user.pop("verification_code", None)
        user.pop("reset_token", None)
        
        # Convert ObjectId to string
        user["_id"] = str(user["_id"])
        
        # Add computed fields
        user["badges"] = badges
        user["stats"] = {
            "total_submissions": total_submissions,
            "completed_challenges": completed_challenges,
            "projects_completed": user.get("projects_completed", 0),
            "courses_enrolled": len(user.get("courses_enrolled", [])),
            "repositories": repo_count,
            "completion_rate": (completed_challenges / total_submissions * 100) if total_submissions > 0 else 0
        }
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get profile error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get profile")


