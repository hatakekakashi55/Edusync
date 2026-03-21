"""
EduSync Backend - Faculty - Communities Routes
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
from app.services.notification_service import NotificationService

logger = logging.getLogger("edusync")

router = APIRouter(tags=["Faculty - Communities"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/faculty/communities", tags=["Faculty"])
async def get_faculty_communities(
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get faculty communities"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        query = {"members": user_id}
        
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}}
            ]
        
        total = await faculty_communities_collection.count_documents(query)
        
        communities = await faculty_communities_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "communities": [
                {
                    "id": str(comm["_id"]),
                    "name": comm["name"],
                    "description": comm["description"],
                    "type": comm["type"],
                    "members": len(comm["members"]),
                    "privacy": comm["privacy"],
                    "created_at": comm["created_at"],
                    "is_owner": comm["created_by"] == user_id
                }
                for comm in communities
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get faculty communities error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get communities")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.post("/api/faculty/communities", tags=["Faculty"])
async def create_community(
    community_data: CommunityCreate,
    current_user: dict = Depends(verify_token)
):
    """Create a new community"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        members = [user_id]
        
        # Add classroom students if classroom-based community
        if community_data.type == "classroom" and community_data.classroom_id:
            classroom = await faculty_classrooms_collection.find_one({
                "_id": ObjectId(community_data.classroom_id),
                "instructor_id": user_id
            })
            if classroom:
                members.extend(classroom.get("students", []))
        
        # Add custom members
        if community_data.type == "custom" and community_data.members:
            members.extend(community_data.members)
        
        logger.info(f"Creating community {community_data.name} for user {user_id}")
        
        # Ensure unique members and all are strings
        unique_members = []
        seen = set()
        for m in members:
            m_str = str(m)
            if m_str not in seen:
                unique_members.append(m_str)
                seen.add(m_str)
        
        community = {
            "name": community_data.name,
            "description": community_data.description,
            "type": community_data.type or "general",
            "classroom_id": community_data.classroom_id,
            "created_by": user_id,
            "created_by_name": current_user.get("full_name") or current_user.get("name") or "Faculty",
            "members": unique_members,
            "privacy": community_data.privacy or "public",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "message_count": 0,
            "file_count": 0,
            "active_members": len(unique_members)
        }
        
        result = await faculty_communities_collection.insert_one(community)
        community_id = str(result.inserted_id)
        
        # Send notifications to members
        for member_id in unique_members:
            if member_id != user_id:
                try:
                    await NotificationService.create_notification(
                        user_id=member_id,
                        title="New Community",
                        message=f"You've been added to community '{community_data.name}'",
                        notification_type="community",
                        priority="medium",
                        action_url=f"/communities/{community_id}"
                    )
                except Exception as notify_err:
                    logger.warning(f"Failed to send notification to {member_id}: {notify_err}")
        
        return {
            "message": "Community created successfully",
            "community_id": community_id,
            "community": community
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create community error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create community: {str(e)}")


