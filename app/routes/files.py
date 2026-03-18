"""
EduSync Backend - Files Routes
Modularized and deduplicated.
"""
import logging
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import FileResponse

from app.dependencies import get_current_user, verify_token, convert_objectid_to_str
from app.database import *

logger = logging.getLogger("edusync")

router = APIRouter(prefix="/api/files", tags=["Files"])

@router.get("/{file_id}/view", tags=["Files"])
async def get_file_details(
    file_id: str,
    current_user: dict = Depends(verify_token)
):
    """View file details and access metadata"""
    try:
        query = {"$or": [{"file_id": file_id}]}
        try:
            if len(file_id) == 24:
                query["$or"].append({"_id": ObjectId(file_id)})
        except (ValueError, Exception):
            # Invalid ObjectId format, continue with file_id search
            pass
            
        file_record = await files_collection.find_one(query)
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
            
        return {
            "success": True,
            "file": convert_objectid_to_str(file_record)
        }
    except Exception as e:
        logger.error(f"View file detail error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{file_id}/content", tags=["Files"])
async def get_file_content(
    file_id: str,
    current_user: dict = Depends(verify_token)
):
    """Read file content from storage"""
    try:
        file_record = await files_collection.find_one({"_id": ObjectId(file_id)})
        if not file_record:
            raise HTTPException(status_code=404, detail="File record not found")
            
        path = file_record.get("path") or file_record.get("url", "").lstrip("/")
        if not os.path.exists(path):
            raise HTTPException(status_code=404, detail="Physical file missing")
            
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            
        return {
            "success": True,
            "content": content,
            "name": file_record.get("name")
        }
    except UnicodeDecodeError:
         return {"success": True, "content": "Binary file", "is_binary": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
