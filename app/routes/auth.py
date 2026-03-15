"""
EduSync Backend - Authentication Routes
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
import secrets
import asyncio
import hashlib
import tempfile
import subprocess
from jose import jwt, JWTError
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict, Any
from pathlib import Path
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query, Body, BackgroundTasks, Request
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, Response

from app.dependencies import get_current_user, verify_token, convert_objectid_to_str
from app.utils.auth import create_access_token, create_refresh_token, verify_password, hash_password
from app.database import *
from app.services.ai_wrapper import gemini_model, get_gemini_model, get_faculty_gemini_model, hod_gemini_model, faculty_gemini_models, AIModelWrapper
from app.services.notification_service import NotificationService
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

router = APIRouter(tags=["Authentication"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/auth/register", tags=["Authentication"])
async def register(user: UserRegister, background_tasks: BackgroundTasks):
    """Register a new user"""
    try:
        # Check if email exists
        existing = await users_collection.find_one({"email": user.email})
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Check if roll number exists (for students)
        if user.user_type == UserType.STUDENT and user.roll_number:
            existing_roll = await users_collection.find_one({"roll_number": user.roll_number})
            if existing_roll:
                raise HTTPException(status_code=400, detail="Roll number already registered")
        
        # Hash password
        hashed_pw = hash_password(user.password)
        
        # Create user document
        user_dict = user.model_dump(exclude={"password"})
        
        # Assign campus email
        clean_username = "".join(c.lower() for c in user.full_name if c.isalnum() or c == '.')
        user_dict["campus_email"] = f"{clean_username}@campus.com"
        
        user_dict["password"] = hashed_pw
        user_dict["created_at"] = datetime.now(timezone.utc)
        user_dict["updated_at"] = datetime.now(timezone.utc)
        user_dict["is_active"] = True
        user_dict["is_verified"] = False
        user_dict["verification_code"] = secrets.token_hex(16)
        
        # Add student-specific fields
        if user.user_type == UserType.STUDENT:
            user_dict["stage"] = Stage.FRESHIE.value
            user_dict["credits"] = 0
            user_dict["xp"] = 0
            user_dict["level"] = 1
            user_dict["daily_login_streak"] = 0
            user_dict["weekly_login_streak"] = 0
            user_dict["current_stage_progress"] = 0
            user_dict["last_login"] = None
            user_dict["last_active"] = None
            user_dict["weak_areas"] = []
            user_dict["strengths"] = []
            user_dict["skills"] = []
            user_dict["interests"] = []
            user_dict["career_goals"] = []
            user_dict["completed_challenges"] = 0
            user_dict["projects_completed"] = 0
            user_dict["courses_enrolled"] = []
            user_dict["badges"] = []
            user_dict["achievements"] = []
            user_dict["mood_history"] = []
            user_dict["learning_style"] = None
            user_dict["preferred_language"] = "en"
            user_dict["timezone"] = "UTC"
            user_dict["notification_preferences"] = {
                "email": True,
                "push": True,
                "sms": False,
                "challenge_reminders": True,
                "deadline_alerts": True,
                "achievement_alerts": True
            }
        
        # Insert user
        result = await users_collection.insert_one(user_dict)
        user_id = str(result.inserted_id)
        
        # Create initial badges
        await badges_collection.insert_one({
            "user_id": user_id,
            "badges": [{
                "name": "Welcome Aboard!",
                "icon": "🎉",
                "earned_date": datetime.now(timezone.utc),
                "description": "Welcome to EduSync 4.0",
                "category": "welcome"
            }],
            "created_at": datetime.now(timezone.utc)
        })

        # Create analytics entry
        await analytics_collection.insert_one({
            "user_id": user_id,
            "user_type": user.user_type,
            "joined_at": datetime.now(timezone.utc),
            "total_sessions": 0,
            "total_time_spent": 0,
            "last_active": None,
            "created_at": datetime.now(timezone.utc)
        })
        
        # Send welcome email
        background_tasks.add_task(
            send_email_async,
            user.email,
            "Welcome to EduSync 4.0!",
            f"Hello {user.full_name},\n\nWelcome to EduSync 4.0! We're excited to have you on board.\n\n"
            f"Your account has been created successfully.\n\n"
            f"Please verify your email by clicking this link: "
            f"http://localhost:3000/verify/{user_dict['verification_code']}\n\n"
            f"Best regards,\nThe EduSync Team"
        )
        
        # Send welcome notification
        await NotificationService.create_notification(
            user_id=user_id,
            title="Welcome to EduSync 4.0! 🎉",
            message=f"Hello {user.full_name}, welcome to our learning community!",
            notification_type="welcome",
            priority="high",
            action_url="/getting-started"
        )
        
        return {
            "message": "Registration successful",
            "user_id": user_id,
            "user_type": user.user_type,
            "verification_required": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")


@router.post("/api/auth/login", tags=["Authentication"])
async def login(login_data: UserLogin, background_tasks: BackgroundTasks):
    """User login with device tracking"""
    try:
        user = await users_collection.find_one({"email": login_data.email})
        if not user or not verify_password(login_data.password, user["password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        if not user.get("is_active", True):
            raise HTTPException(status_code=403, detail="Account is deactivated")
        
        # Update login stats
        now = datetime.now(timezone.utc)
        last_login = user.get("last_login")
        
        # Calculate streaks
        daily_streak = user.get("daily_login_streak", 0)
        weekly_streak = user.get("weekly_login_streak", 0)
        
        if last_login:
            last_login_date = last_login.date()
            today = now.date()
            
            # Daily streak
            if (today - last_login_date).days == 1:
                daily_streak += 1
            elif (today - last_login_date).days > 1:
                daily_streak = 1
            
            # Weekly streak (login at least once per week)
            if (today - last_login_date).days <= 7:
                weekly_streak += 1
            else:
                weekly_streak = 1
        else:
            daily_streak = 1
            weekly_streak = 1
        
        # Award credits for login streak
        login_credits = 10 + (daily_streak * 2)  # Base 10 + 2 per streak day
        
        # Update user
        update_data = {
            "last_login": now,
            "last_active": now,
            "daily_login_streak": daily_streak,
            "weekly_login_streak": weekly_streak,
            "credits": user.get("credits", 0) + login_credits,
            "login_count": user.get("login_count", 0) + 1,
            "updated_at": now
        }
        
        # Add device info if provided
        if login_data.device_info:
            device_history = user.get("device_history", [])
            device_history.append({
                "device_info": login_data.device_info,
                "login_time": now,
                "ip_address": None  # Would get from request in production
            })
            update_data["device_history"] = device_history[-10:]  # Keep last 10
        
        await users_collection.update_one(
            {"_id": user["_id"]},
            {"$set": update_data}
        )
        
        # Update analytics
        await analytics_collection.update_one(
            {"user_id": str(user["_id"])},
            {"$inc": {"total_sessions": 1}}
        )
        
        # Create tokens
        access_token = create_access_token({
            "email": user["email"],
            "user_type": user["user_type"],
            "user_id": str(user["_id"]),
            "full_name": user["full_name"]
        })
        
        refresh_token = create_refresh_token({
            "user_id": str(user["_id"]),
            "email": user["email"]
        })
        
        # Store refresh token in Redis
        redis_client = get_redis_client()
        if redis_client:
            await redis_client.setex(
                f"refresh_token:{refresh_token}",
                REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
                str(user["_id"])
            )
        
        # Send login notification
        background_tasks.add_task(
            NotificationService.create_notification,
            user_id=str(user["_id"]),
            title="Login Successful",
            message=f"Welcome back! Daily streak: {daily_streak} days. Earned {login_credits} credits.",
            notification_type="login",
            priority="low"
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "user_id": str(user["_id"]),
                "email": user["email"],
                "full_name": user["full_name"],
                "user_type": user["user_type"],
                "stage": user.get("stage"),
                "department": user.get("department"),
                "year": user.get("year"),
                "credits": user.get("credits", 0) + login_credits,
                "xp": user.get("xp", 0),
                "level": user.get("level", 1),
                "daily_streak": daily_streak,
                "weekly_streak": weekly_streak,
                "profile_picture": user.get("profile_picture"),
                "theme": user.get("theme", "light"),
                "is_verified": user.get("is_verified", False),
                "role": user.get("role", "user")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/api/auth/refresh", tags=["Authentication"])
async def refresh_token(refresh_token: str = Body(..., embed=True)):
    """Refresh access token using refresh token"""
    try:
        # Verify refresh token
        payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        # Check if refresh token is valid in Redis
        redis_client = get_redis_client()
        if redis_client:
            stored_user_id = await redis_client.get(f"refresh_token:{refresh_token}")
            if not stored_user_id or stored_user_id != payload.get("user_id"):
                raise HTTPException(status_code=401, detail="Invalid refresh token")
        
        # Get user
        user = await users_collection.find_one({"_id": ObjectId(payload["user_id"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        # Create new access token
        new_access_token = create_access_token({
            "email": user["email"],
            "user_type": user["user_type"],
            "user_id": str(user["_id"]),
            "full_name": user["full_name"]
        })
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Refresh token expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    except Exception as e:
        logger.error(f"Refresh token error: {e}")
        raise HTTPException(status_code=500, detail="Token refresh failed")


@router.post("/api/auth/logout", tags=["Authentication"])
async def logout(
    refresh_token: str = Body(None, embed=True),
    current_user: dict = Depends(verify_token)
):
    """Logout user and invalidate tokens"""
    try:
        user_id = str(current_user["_id"])
        
        # Invalidate refresh token if provided
        redis_client = get_redis_client()
        if refresh_token and redis_client:
            await redis_client.delete(f"refresh_token:{refresh_token}")
        
        return {"message": "Logout successful"}
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail="Logout failed")


