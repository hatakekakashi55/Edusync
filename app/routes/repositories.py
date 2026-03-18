"""
EduSync Backend - Repositories Routes
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
from app.services.version_control import VersionControlService
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

router = APIRouter(tags=["Repositories"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/repositories", tags=["Repositories"])
async def get_repositories(
    owner_id: Optional[str] = None,
    is_public: Optional[bool] = None,
    language: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get repositories with filters"""
    try:
        user_id = str(current_user["_id"])
        
        query = {}
        
        # Build query based on access
        if owner_id:
            query["owner_id"] = owner_id
            if owner_id != user_id:
                query["is_public"] = True
        else:
            # Show user's repos and public repos
            query["$or"] = [
                {"owner_id": user_id},
                {"collaborators": user_id},
                {"is_public": True}
            ]
        
        if is_public is not None:
            query["is_public"] = is_public
        
        if language:
            query[f"language_stats.{language}"] = {"$exists": True}
        
        total = await code_repositories_collection.count_documents(query)
        
        repositories = await code_repositories_collection.find(query) \
            .sort("updated_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        # Clean the documents
        cleaned_repositories = [clean_mongodb_document(repo) for repo in repositories]
        
        return {
            "repositories": cleaned_repositories,
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
        
    except Exception as e:
        logger.error(f"Get repositories error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get repositories")


@router.get("/api/repositories/{repository_id}", tags=["Repositories"])
async def get_repository_detail(
    repository_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get repository details"""
    try:
        user_id = str(current_user["_id"])
        
        repository = await code_repositories_collection.find_one({"id": repository_id})
        if not repository:
            raise HTTPException(status_code=404, detail="Repository not found")
        
        # Check access
        if (not repository["is_public"] and 
            repository["owner_id"] != user_id and 
            user_id not in repository.get("collaborators", [])):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get recent commits
        recent_commits = await code_commits_collection.find({
            "repository_id": repository_id
        }).sort("timestamp", -1).limit(10).to_list(10)
        
        # Clean commits
        cleaned_commits = [clean_mongodb_document(commit) for commit in recent_commits]
        
        # Get contributors
        contributors = await code_commits_collection.aggregate([
            {"$match": {"repository_id": repository_id}},
            {"$group": {
                "_id": "$author_id",
                "commit_count": {"$sum": 1},
                "last_commit": {"$max": "$timestamp"}
            }},
            {"$lookup": {
                "from": "users",
                "localField": "_id",
                "foreignField": "_id",
                "as": "user"
            }},
            {"$unwind": "$user"},
            {"$project": {
                "user_id": {"$toString": "$_id"},  # Convert ObjectId to string
                "user_name": "$user.full_name",
                "profile_picture": "$user.profile_picture",
                "commit_count": 1,
                "last_commit": 1
            }}
        ]).to_list(10)
        
        # Get repository files
        files = await VersionControlService.get_repository_files(repository_id)
        
        # Clean the repository document
        cleaned_repository = clean_mongodb_document(repository)
        cleaned_repository["recent_commits"] = cleaned_commits
        cleaned_repository["contributors"] = contributors
        cleaned_repository["files"] = files
        cleaned_repository["can_edit"] = (cleaned_repository["owner_id"] == user_id or 
                                         user_id in cleaned_repository.get("collaborators", []))
        
        return cleaned_repository
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get repository detail error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get repository details")


@router.post("/api/repositories/{repository_id}/commits", tags=["Repositories"])
async def create_commit(
    repository_id: str,
    commit_data: CommitCreate,
    current_user: dict = Depends(verify_token)
):
    """Create a new commit"""
    try:
        user_id = str(current_user["_id"])
        
        commit = await VersionControlService.create_commit(
            repository_id=repository_id,
            user_id=user_id,
            message=commit_data.message,
            files=commit_data.files,
            branch=commit_data.branch
        )
        
        return {
            "message": "Commit created successfully",
            "commit": commit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create commit error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create commit")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.post("/api/repositories", tags=["Repositories"])
async def create_repository(
    repo_data: CodeRepositoryCreate,
    current_user: dict = Depends(verify_token)
):
    """Create a new code repository"""
    try:
        user_id = str(current_user["_id"])
        
        repository = await VersionControlService.create_repository(
            user_id=user_id,
            name=repo_data.name,
            description=repo_data.description,
            is_public=repo_data.is_public or False
        )
        
        # Clean the repository document
        cleaned_repository = clean_mongodb_document(repository)
        
        return {
            "message": "Repository created successfully",
            "repository": cleaned_repository
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create repository error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create repository")


