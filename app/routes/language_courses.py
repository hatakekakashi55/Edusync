"""
EduSync Backend - Language Courses Routes
Modularized and deduplicated.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends, status, Form, Query, Body

from app.dependencies import verify_token, convert_objectid_to_str
from app.database import *
from app.models.compiler import CodeSubmission, CodeExecution
from app.services.compiler_service import CompilerService
from app.services.ai_service import AIService
from app.utils.helpers import update_user_credits

logger = logging.getLogger("edusync")

router = APIRouter(prefix="/api/language-courses", tags=["Language Courses"])

@router.get("/progress", tags=["Language Courses"])
async def get_language_course_progress(current_user: dict = Depends(verify_token)):
    """Get user's language course progress"""
    try:
        user_id = str(current_user["_id"])
        
        # Get progress from database
        progress_doc = await language_course_progress_collection.find_one({"user_id": user_id})
        
        return {
            "success": True,
            "progress": progress_doc.get("progress", {}) if progress_doc else {}
        }
    except Exception as e:
        logger.error(f"Get language course progress error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get progress")

@router.post("/run-code", tags=["Language Courses"])
async def run_language_course_code(
    submission: CodeSubmission,
    current_user: dict = Depends(verify_token)
):
    """Run code with AI assistance and sandbox execution"""
    try:
        # Execute code using safe compiler service
        result = await CompilerService.execute_code_safely(
            code=submission.code,
            language=submission.language
        )
        
        # Add AI feedback for errors
        if not result["success"] and result["error"]:
            try:
                ai_hint = await AIService.code_help(
                    code=submission.code,
                    error=result["error"],
                    requirement="Fix the compilation/runtime error",
                    language=submission.language,
                    context=""
                )
                result["ai_hint"] = ai_hint
            except Exception as e:
                logger.debug(f"Could not get AI hint: {e}")
            
        return result
    except Exception as e:
        logger.error(f"Run code error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/submit-exercise", tags=["Language Courses"])
async def submit_language_course_exercise(
    submission: CodeSubmission,
    current_user: dict = Depends(verify_token)
):
    """Submit solution for AI-powered evaluation and scoring"""
    try:
        user_id = str(current_user["_id"])
        
        # 1. Execute
        exec_result = await CompilerService.execute_code_safely(
            code=submission.code,
            language=submission.language
        )
        
        # 2. AI Review
        review = await AIService.code_review(submission.code, submission.language)
        
        # 3. Score
        score = review.get("score", 0) if exec_result["success"] else 0
        passed = score >= 70
        
        if passed:
            # Award credits
            credits = score // 10
            await update_user_credits(
                user_id=user_id,
                amount=credits,
                source=f"language_course_{submission.language}",
                description=f"Completed {submission.language} exercise"
            )
            
            # Update progress
            await language_course_progress_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {f"progress.{submission.language}.completed_exercises": 1},
                    "$inc": {f"progress.{submission.language}.total_credits": credits}
                },
                upsert=True
            )
            
        return {
            "success": True,
            "passed": passed,
            "score": score,
            "ai_feedback": review.get("feedback"),
            "output": exec_result.get("output"),
            "error": exec_result.get("error")
        }
    except Exception as e:
        logger.error(f"Submit exercise error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
