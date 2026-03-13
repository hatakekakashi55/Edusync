"""
EduSync Backend - Faculty - Materials Routes
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

router = APIRouter(tags=["Faculty - Materials"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/faculty/classrooms/{classroom_id}/materials", tags=["Faculty"])
async def add_classroom_material(
    classroom_id: str,
    title: str = Form(...),
    description: str = Form(default=""),
    material_type: str = Form(...),  # "file" or "link"
    material_url: str = Form(default=""),
    topic: str = Form(default="General"),  # Topic for organization
    status: str = Form(default="published"),  # "published", "draft", "scheduled"
    scheduled_at: str = Form(default=""),  # ISO format datetime for scheduled materials
    visibility: str = Form(default="all"),  # "all" or specific student IDs
    files: List[UploadFile] = File(None),
    current_user: dict = Depends(verify_token)
):
    """Add a material/resource to classroom with topic, scheduling, and visibility options"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        # Validate classroom_id
        if not ObjectId.is_valid(classroom_id):
            logger.warning(f"Invalid classroom_id format: {classroom_id}")
            raise HTTPException(status_code=400, detail="Invalid classroom ID format")
        
        classroom_oid = ObjectId(classroom_id)
        
        # Verify classroom exists and faculty owns it
        classroom = await faculty_classrooms_collection.find_one({
            "_id": classroom_oid,
            "instructor_id": str(current_user["_id"])
        })
        
        if not classroom:
            logger.warning(f"Classroom {classroom_id} not found or not owned by {current_user['_id']}")
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        now = datetime.now(timezone.utc)
        
        material_doc = {
            "id": str(ObjectId()),
            "title": title,
            "description": description,
            "type": material_type,
            "topic": topic,
            "status": status,  # published, draft, scheduled
            "created_at": now,
            "scheduled_at": scheduled_at if scheduled_at else None,
            "created_by": str(current_user["_id"]),
            "files": [],
            "url": material_url,
            "visibility": visibility,  # "all" or list of student IDs
            "views": []  # Track who viewed this material
        }
        
        # Handle file uploads
        if material_type == "file" and files:
            for file in files:
                if file and file.filename:
                    try:
                        import os
                        import uuid
                        uploads_dir = "static/uploads"
                        os.makedirs(uploads_dir, exist_ok=True)
                        
                        # Generate unique filename
                        file_ext = os.path.splitext(file.filename)[1]
                        unique_filename = f"{uuid.uuid4()}{file_ext}"
                        file_path = os.path.join(uploads_dir, unique_filename)
                        
                        # Save file
                        content = await file.read()
                        with open(file_path, 'wb') as f:
                            f.write(content)
                        
                        material_doc["files"].append({
                            "filename": file.filename,
                            "filepath": "/" + file_path.replace("\\", "/"),
                            "size": len(content),
                            "uploaded_at": now.isoformat()
                        })
                        logger.info(f"✓ Material file uploaded: {file.filename}")
                    except Exception as e:
                        logger.error(f"Material file upload error: {e}")
                        raise HTTPException(status_code=500, detail=f"Failed to upload file {file.filename}")
        
        # Add material to classroom
        if "materials" not in classroom:
            classroom["materials"] = []
        
        # If there's no topics field, create one
        if "topics" not in classroom:
            classroom["topics"] = {}
        
        # Ensure topic exists in topics dictionary
        if topic not in classroom["topics"]:
            classroom["topics"][topic] = {
                "name": topic,
                "materials": [],
                "created_at": now.isoformat()
            }
        
        classroom["materials"].append(material_doc)
        classroom["topics"][topic]["materials"].append(material_doc["id"])
        
        # Update classroom
        await faculty_classrooms_collection.update_one(
            {"_id": classroom_oid},
            {
                "$set": {
                    "materials": classroom["materials"],
                    "topics": classroom["topics"]
                }
            }
        )
        
        # Also update in student classrooms_collection
        await classrooms_collection.update_one(
            {"_id": classroom_oid},
            {
                "$set": {
                    "materials": classroom["materials"],
                    "topics": classroom["topics"]
                }
            }
        )
        
        logger.info(f"✓ Material '{title}' added to classroom {classroom_id} under topic '{topic}'")
        
        return {
            "success": True,
            "material": material_doc,
            "message": "Material added successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add material error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add material: {str(e)}")


@router.delete("/api/faculty/classrooms/{classroom_id}/materials/{material_id}", tags=["Faculty"])
async def delete_classroom_material(
    classroom_id: str,
    material_id: str,
    current_user: dict = Depends(verify_token)
):
    """Delete a material/resource from classroom"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        # Validate classroom_id
        if not ObjectId.is_valid(classroom_id):
            logger.warning(f"Invalid classroom_id format: {classroom_id}")
            raise HTTPException(status_code=400, detail="Invalid classroom ID format")
        
        classroom_oid = ObjectId(classroom_id)
        
        # Verify classroom exists and faculty owns it
        classroom = await faculty_classrooms_collection.find_one({
            "_id": classroom_oid,
            "instructor_id": str(current_user["_id"])
        })
        
        if not classroom:
            logger.warning(f"Classroom {classroom_id} not found or not owned by {current_user['_id']}")
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Remove material
        materials = classroom.get("materials", [])
        updated_materials = [m for m in materials if m.get("id") != material_id]
        
        if len(updated_materials) == len(materials):
            raise HTTPException(status_code=404, detail="Material not found")
        
        # Update classroom
        await faculty_classrooms_collection.update_one(
            {"_id": classroom_oid},
            {"$set": {"materials": updated_materials}}
        )
        
        logger.info(f"✓ Material {material_id} deleted from classroom {classroom_id}")
        
        return {
            "success": True,
            "message": "Material deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete material error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete material: {str(e)}")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.get("/api/faculty/classrooms/{classroom_id}/materials", tags=["Faculty"])
async def get_classroom_materials(
    classroom_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get all materials/resources for a classroom"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        # Validate classroom_id
        if not ObjectId.is_valid(classroom_id):
            logger.warning(f"Invalid classroom_id format: {classroom_id}")
            raise HTTPException(status_code=400, detail="Invalid classroom ID format")
        
        classroom_oid = ObjectId(classroom_id)
        
        # Verify classroom exists and faculty owns it
        classroom = await faculty_classrooms_collection.find_one({
            "_id": classroom_oid,
            "instructor_id": str(current_user["_id"])
        })
        
        if not classroom:
            logger.warning(f"Classroom {classroom_id} not found or not owned by {current_user['_id']}")
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Get materials from classroom
        materials = classroom.get("materials", [])
        
        return {
            "success": True,
            "materials": materials
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get materials error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch materials: {str(e)}")


