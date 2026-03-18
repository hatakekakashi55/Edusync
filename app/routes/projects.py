"""
EduSync Backend - Projects & Team Collaboration Routes
Modularized and deduplicated.
"""
import logging
import os
import uuid
import re
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bson import ObjectId
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query, Body, Request
from fastapi.responses import JSONResponse, FileResponse

from app.dependencies import get_current_user, verify_token, convert_objectid_to_str
from app.database import *
from app.models.classroom import ProjectCompletionSubmission
from app.models.compiler import FileCreate
from app.services.ai_wrapper import get_gemini_model
from app.config import MAX_FILE_SIZE, ALLOWED_EXTENSIONS

logger = logging.getLogger("edusync")

router = APIRouter(prefix="/api/projects", tags=["Projects"])

@router.get("", tags=["Projects"])
async def list_projects(
    visibility: Optional[str] = None,
    current_user: dict = Depends(verify_token)
):
    """List projects accessible to the user"""
    try:
        user_id = str(current_user["_id"])
        query = {
            "$or": [
                {"visibility": "public"},
                {"creator_id": user_id},
                {"members": user_id}
            ]
        }
        if visibility:
            query["visibility"] = {"$in": [visibility]}
            
        projects = await projects_collection.find(query).sort("created_at", -1).to_list(100)
        return {
            "success": True,
            "projects": convert_objectid_to_str(projects)
        }
    except Exception as e:
        logger.error(f"List projects error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create", tags=["Projects"])
async def create_new_project(
    title: str = Form(...),
    description: str = Form(""),
    project_type: str = Form("personal"),
    tech_stack: str = Form(""),
    current_user: dict = Depends(verify_token)
):
    """Create a new personal or team project"""
    try:
        user_id = str(current_user["_id"])
        project = {
            "title": title,
            "description": description,
            "project_type": project_type,
            "creator_id": user_id,
            "creator_name": current_user["full_name"],
            "tech_stack": [t.strip() for t in tech_stack.split(",") if t.strip()],
            "members": [user_id],
            "status": "active",
            "visibility": "public",
            "created_at": datetime.now(timezone.utc)
        }
        
        result = await projects_collection.insert_one(project)
        return {
            "success": True, 
            "project_id": str(result.inserted_id),
            "message": "Project created"
        }
    except Exception as e:
        logger.error(f"Create project error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{project_id}", tags=["Projects"])
async def get_project_details(
    project_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get detailed project info"""
    try:
        project = await projects_collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
            
        return {
            "success": True,
            "project": convert_objectid_to_str(project)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Team Projects Extensions
@router.get("/team/group/{group_id}", tags=["Team Projects"])
async def list_group_projects(
    group_id: str,
    current_user: dict = Depends(verify_token)
):
    """List projects linked to a specific group"""
    try:
        projects = await projects_collection.find({"group_id": group_id}).to_list(100)
        return {
            "success": True,
            "projects": convert_objectid_to_str(projects)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{project_id}/files", tags=["Team Projects"])
async def list_project_files(
    project_id: str,
    current_user: dict = Depends(verify_token)
):
    """List all files in a project workspace"""
    try:
        files = await files_collection.find({"project_id": project_id}).to_list(100)
        return {
            "success": True,
            "files": convert_objectid_to_str(files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{project_id}/files/create", tags=["Team Projects"])
async def create_file(
    project_id: str,
    file_data: FileCreate,
    current_user: dict = Depends(verify_token)
):
    """Create a new file in project workspace"""
    try:
        new_file = {
            "project_id": project_id,
            "name": file_data.filename,
            "content": file_data.content,
            "language": file_data.language,
            "created_by": str(current_user["_id"]),
            "updated_at": datetime.now(timezone.utc)
        }
        result = await files_collection.insert_one(new_file)
        return {"success": True, "file_id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
