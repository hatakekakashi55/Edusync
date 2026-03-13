
"""
EduSync Backend - Admin - Stage 1 Routes
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

router = APIRouter(tags=["Admin - Stage 1"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/admin/stage1/sentences", tags=["Admin", "Stage 1"])
async def get_all_sentences(current_user: dict = Depends(get_current_user)):
    """Admin: Get all voice/read challenge sentences"""
    try:
        if current_user.get("user_type") not in ["admin", "faculty"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        sentences = []
        async for sentence in voice_challenge_sentences_collection.find().sort("created_at", -1):
            sentence["_id"] = str(sentence["_id"])
            sentences.append(sentence)
        
        return {"success": True, "sentences": sentences}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching sentences: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/admin/stage1/sentences/{sentence_id}", tags=["Admin", "Stage 1"])
async def delete_sentence(sentence_id: str, current_user: dict = Depends(get_current_user)):
    """Admin: Delete a voice challenge sentence"""
    try:
        if current_user.get("user_type") not in ["admin", "faculty"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        result = await voice_challenge_sentences_collection.delete_one({"_id": ObjectId(sentence_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Sentence not found")
        
        return {"success": True, "message": "Sentence deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting sentence: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/admin/stage1/writing-challenges", tags=["Admin", "Stage 1"])
async def get_all_writing_challenges(current_user: dict = Depends(get_current_user)):
    """Admin: Get all writing challenges"""
    try:
        if current_user.get("user_type") not in ["admin", "faculty"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        challenges = []
        async for challenge in writing_challenges_collection.find().sort("created_at", -1):
            challenge["_id"] = str(challenge["_id"])
            challenges.append(challenge)
        
        return {"success": True, "challenges": challenges}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching writing challenges: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/admin/stage1/writing-challenges/{challenge_id}", tags=["Admin", "Stage 1"])
async def delete_writing_challenge(challenge_id: str, current_user: dict = Depends(get_current_user)):
    """Admin: Delete a writing challenge"""
    try:
        if current_user.get("user_type") not in ["admin", "faculty"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        result = await writing_challenges_collection.delete_one({"_id": ObjectId(challenge_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        return {"success": True, "message": "Writing challenge deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting writing challenge: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



# Note: Communication task routes (GET, POST, PUT, DELETE /api/admin/communication/tasks) 
# have been moved to app/routes/admin/communication.py to avoid duplication.

# ========== RECOVERED MISSING ENDPOINTS ==========


@router.post("/api/admin/stage1/sentences", tags=["Admin", "Stage 1"])
async def add_voice_challenge_sentence(
    sentence_data: VoiceChallengeSentence,
    current_user: dict = Depends(get_current_user)
):
    """Admin: Add a new voice/read challenge sentence"""
    try:
        if current_user.get("user_type") not in ["admin", "faculty"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        sentence_dict = sentence_data.model_dump()
        sentence_dict["created_by"] = str(current_user["_id"])
        sentence_dict["created_at"] = datetime.now(timezone.utc)
        
        result = await voice_challenge_sentences_collection.insert_one(sentence_dict)
        
        logger.info(f"✅ Voice challenge sentence added: {result.inserted_id}")
        return {
            "success": True,
            "message": "Sentence added successfully",
            "sentence_id": str(result.inserted_id)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error adding sentence: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/admin/stage1/writing-challenges", tags=["Admin", "Stage 1"])
async def add_writing_challenge(
    challenge_data: WritingChallenge,
    current_user: dict = Depends(get_current_user)
):
    """Admin: Add a new writing challenge"""
    try:
        if current_user.get("user_type") not in ["admin", "faculty"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        challenge_dict = challenge_data.model_dump()
        challenge_dict["created_by"] = str(current_user["_id"])
        challenge_dict["created_at"] = datetime.now(timezone.utc)
        
        result = await writing_challenges_collection.insert_one(challenge_dict)
        
        logger.info(f"✅ Writing challenge added: {result.inserted_id}")
        return {
            "success": True,
            "message": "Writing challenge added successfully",
            "challenge_id": str(result.inserted_id)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error adding writing challenge: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



# End of stage1 admin routes


