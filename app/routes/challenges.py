"""
EduSync Backend - Challenges Routes
Modularized and deduplicated.
"""
import logging
import uuid
import os
import json
import base64
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query, Body, BackgroundTasks
from fastapi.responses import JSONResponse

from app.dependencies import get_current_user, verify_token, convert_objectid_to_str
from app.database import *
from app.models.challenge import *
from app.models.auth import *

from app.services.ai_service import AIService
from app.services.compiler_service import CompilerService
from app.services.speech_service import SpeechService
from app.services.notification_service import NotificationService
from app.utils.helpers import get_next_stage

logger = logging.getLogger("edusync")

router = APIRouter(prefix="/api/challenges", tags=["Challenges"])

@router.get("", tags=["Challenges"])
async def get_challenges(
    stage: Optional[str] = None,
    challenge_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    language: Optional[str] = None,
    tags: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get challenges with filters"""
    try:
        query = {"status": "active"}
        
        if stage:
            query["stage"] = stage
        elif current_user["user_type"] == UserType.STUDENT.value:
            query["stage"] = current_user.get("stage", "freshie")
        
        if challenge_type:
            query["challenge_type"] = challenge_type
        if difficulty:
            query["difficulty"] = difficulty
        if language:
            query["language"] = language
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            query["tags"] = {"$in": tag_list}
        
        total = await challenges_collection.count_documents(query)
        challenges = await challenges_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        # Add submission status for current user
        user_id = str(current_user["_id"])
        challenge_ids = [str(ch["_id"]) for ch in challenges]
        
        submissions = await submissions_collection.find({
            "user_id": user_id,
            "challenge_id": {"$in": challenge_ids}
        }).to_list(100)
        
        submission_map = {sub["challenge_id"]: sub for sub in submissions}
        
        formatted = []
        for ch in challenges:
            ch_id = str(ch["_id"])
            sub = submission_map.get(ch_id)
            ch_dict = convert_objectid_to_str(ch)
            if ch_dict:
                ch_dict.update({
                    "id": ch_id,
                    "user_status": {
                        "attempted": sub is not None,
                        "completed": sub.get("completed", False) if sub else False,
                        "score": sub.get("score", 0) if sub else 0
                    }
                })
                formatted.append(ch_dict)
            
        return {
            "success": True,
            "challenges": formatted,
            "total": total
        }
    except Exception as e:
        logger.error(f"Get challenges error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{challenge_id}", tags=["Challenges"])
async def get_challenge_detail(
    challenge_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get detailed challenge info"""
    try:
        challenge = await challenges_collection.find_one({"_id": ObjectId(challenge_id)})
        if not challenge:
            raise HTTPException(status_code=404, detail="Challenge not found")
            
        user_id = str(current_user["_id"])
        submissions = await submissions_collection.find({
            "user_id": user_id,
            "challenge_id": challenge_id
        }).sort("submitted_at", -1).to_list(10)
        
        return {
            "success": True,
            "challenge": convert_objectid_to_str(challenge),
            "user_submissions": convert_objectid_to_str(submissions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{challenge_id}/submit", tags=["Challenges"])
async def submit_challenge(
    challenge_id: str,
    submission_type: str = Form("text"), # "text", "code", "voice"
    code: Optional[str] = Form(None),
    audio_text: Optional[str] = Form(None),
    text_answer: Optional[str] = Form(None),
    audio_file: Optional[UploadFile] = File(None),
    current_user: dict = Depends(verify_token),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Submit a challenge solution"""
    try:
        user_id = str(current_user["_id"])
        challenge = await challenges_collection.find_one({"_id": ObjectId(challenge_id)})
        if not challenge:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        submission_data = {
            "user_id": user_id,
            "challenge_id": challenge_id,
            "challenge_title": challenge["title"],
            "submitted_at": datetime.now(timezone.utc),
            "completed": False,
            "score": 0,
            "credits_earned": 0
        }
        
        # Process based on type
        ch_type = challenge.get("challenge_type", "text")
        
        if ch_type == "voice":
            spoken_text = audio_text
            if audio_file:
                audio_bytes = await audio_file.read()
                spoken_text = await SpeechService.speech_to_text(audio_bytes)
            
            if not spoken_text:
                raise HTTPException(status_code=400, detail="No speech content")
                
            analysis = await AIService.analyze_english_with_gemini(
                spoken_text,
                challenge.get("correct_text", "")
            )
            submission_data.update({
                "spoken_text": spoken_text,
                "ai_feedback": analysis,
                "score": analysis.get("pronunciation_score", 0),
                "completed": analysis.get("pronunciation_score", 0) >= 70
            })
            
        elif ch_type == "coding":
            if not code:
                 raise HTTPException(status_code=400, detail="Code required")
            
            # Execute and Review
            exec_result = await CompilerService.execute_code_safely(
                code, challenge.get("language", "python"), 
                test_cases=challenge.get("test_cases", [])
            )
            review = await AIService.code_review(code, challenge.get("language", "python"))
            
            passed_tests = sum(1 for t in exec_result.get("test_results", []) if t["passed"])
            total_tests = len(exec_result.get("test_results", []))
            score = (passed_tests / total_tests * 100) if total_tests > 0 else 50
            
            submission_data.update({
                "code": code,
                "execution_result": exec_result,
                "ai_feedback": review,
                "score": score,
                "completed": score >= 70
            })
            
        else: # Basic text/quiz
            ans = text_answer or audio_text
            correct = challenge.get("correct_answer") or challenge.get("correct_text")
            is_correct = ans and correct and ans.strip().lower() == correct.strip().lower()
            submission_data.update({
                "answer": ans,
                "score": 100 if is_correct else 0,
                "completed": is_correct
            })
            
        # Reward credits
        if submission_data["completed"]:
            reward = challenge.get("credits_reward", 10)
            submission_data["credits_earned"] = reward
            await users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$inc": {"credits": reward, "completed_challenges": 1}}
            )
            
            # Update progress
            await users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$inc": {"current_stage_progress": 10}} # 10% per challenge
            )
        
        result = await submissions_collection.insert_one(submission_data)
        
        return {
            "success": True,
            "submission_id": str(result.inserted_id),
            "score": submission_data["score"],
            "completed": submission_data["completed"],
            "credits_earned": submission_data["credits_earned"]
        }
    except Exception as e:
        logger.error(f"Challenge submission error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
