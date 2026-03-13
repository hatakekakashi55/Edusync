"""
EduSync Backend - Career - Portfolio Routes
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

router = APIRouter(tags=["Career - Portfolio"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/portfolio/data")
async def get_portfolio_data(current_user: dict = Depends(verify_token)):
    """Get user's portfolio data"""
    try:
        user_id = current_user["_id"]
        
        # Get user's projects
        projects = await projects_collection.find({
            "$or": [
                {"owner_id": str(user_id)},
                {"members": str(user_id)}
            ]
        }).to_list(length=50)
        
        # Get resume for skills
        resume = await resume_collection.find_one({"user_id": user_id})
        
        # Get badges/certificates
        badges = await badges_collection.count_documents({"user_id": str(user_id)})
        certificates = await certificates_collection.count_documents({"user_id": str(user_id)})
        
        portfolio_projects = []
        for proj in projects:
            portfolio_projects.append({
                "title": proj.get("title", "Untitled Project"),
                "description": proj.get("description", "")
            })
        
        return {
            "portfolio": {
                "stats": {
                    "total_projects": len(projects),
                    "total_skills": len(resume.get("skills", [])) if resume else 0,
                    "total_badges": badges,
                    "total_certificates": certificates,
                    "views": 0,
                    "title": current_user.get("department", "Student")
                },
                "projects": portfolio_projects
            }
        }
    except Exception as e:
        logger.error(f"Portfolio data error: {e}")
        return {
            "portfolio": {
                "stats": {
                    "total_projects": 0,
                    "total_skills": 0,
                    "total_badges": 0,
                    "total_certificates": 0,
                    "views": 0,
                    "title": "Student"
                },
                "projects": []
            }
        }


@router.post("/api/portfolio/generate", tags=["Career"])
async def generate_portfolio(
    current_user: dict = Depends(verify_token)
):
    """Generate portfolio website for user"""
    try:
        user_id = str(current_user["_id"])
        
        # Get portfolio data
        portfolio_data = await get_portfolio_data(current_user)
        
        # Generate portfolio URL
        username = current_user["full_name"].lower().replace(" ", "-")
        portfolio_url = f"https://portfolio.edusync.tech/{username}"
        
        # Update user with portfolio URL
        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "portfolio_url": portfolio_url,
                    "portfolio_updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        # Award credits
        await update_user_credits(
            user_id=user_id,
            amount=100,
            source="portfolio_generation",
            description="Generated personal portfolio website"
        )
        
        return {
            "success": True,
            "url": portfolio_url,
            "message": "Portfolio generated successfully!",
            "credits_earned": 100,
            "preview_url": f"{portfolio_url}/preview"
        }
        
    except Exception as e:
        logger.error(f"Generate portfolio error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate portfolio")


@router.post("/api/portfolio/customize", tags=["Career"])
async def customize_portfolio(
    theme: str = Form("professional"),
    color_scheme: str = Form("#f59e0b"),
    show_projects: bool = Form(True),
    show_skills: bool = Form(True),
    show_certificates: bool = Form(True),
    current_user: dict = Depends(verify_token)
):
    """Customize portfolio appearance"""
    try:
        user_id = str(current_user["_id"])
        
        customization = {
            "theme": theme,
            "color_scheme": color_scheme,
            "show_projects": show_projects,
            "show_skills": show_skills,
            "show_certificates": show_certificates,
            "updated_at": datetime.now(timezone.utc)
        }
        
        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "portfolio_customization": customization
                }
            }
        )
        
        return {
            "success": True,
            "customization": customization,
            "message": "Portfolio customization saved successfully!"
        }
        
    except Exception as e:
        logger.error(f"Customize portfolio error: {e}")
        raise HTTPException(status_code=500, detail="Failed to customize portfolio")


