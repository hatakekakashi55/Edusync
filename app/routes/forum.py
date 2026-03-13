"""
EduSync Backend - Forum Routes
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

router = APIRouter(tags=["Forum"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/forum/posts", tags=["Forum"])
async def get_forum_posts(
    category: Optional[str] = None,
    tags: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get forum posts with filters"""
    try:
        query = {}
        
        if category:
            query["category"] = category
        if tags:
            query["tags"] = {"$in": tags.split(",")}
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"content": {"$regex": search, "$options": "i"}}
            ]
        
        total = await forum_posts_collection.count_documents(query)
        
        posts = await forum_posts_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "posts": [
                {
                    "id": p["id"],
                    "title": p["title"],
                    "content": p["content"][:200] + ("..." if len(p["content"]) > 200 else ""),
                    "author_name": p["author_name"],
                    "tags": p["tags"],
                    "category": p["category"],
                    "created_at": p["created_at"],
                    "views": p["views"],
                    "upvotes": p["upvotes"],
                    "downvotes": p["downvotes"],
                    "comments": p["comments"],
                    "is_resolved": p["is_resolved"],
                    "is_pinned": p["is_pinned"]
                }
                for p in posts
            ],
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get forum posts error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get forum posts")


