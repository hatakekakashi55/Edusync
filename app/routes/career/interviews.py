"""
EduSync Backend - Career - Interviews Routes
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

router = APIRouter(tags=["Career - Interviews"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/interviews/stats")
async def get_interview_stats(current_user: dict = Depends(verify_token)):
    """Get user's interview statistics"""
    try:
        user_id = current_user["_id"]
        
        interviews = await interviews_collection.find({
            "user_id": user_id,
            "status": "completed"
        }).to_list(length=100)
        
        total_interviews = len(interviews)
        
        if total_interviews == 0:
            return {
                "total_interviews": 0,
                "average_score": 0,
                "confidence_rating": 0,
                "practice_hours": 0
            }
        
        # Calculate average score from all answers
        all_scores = []
        for interview in interviews:
            for answer in interview.get("answers", []):
                if "score" in answer:
                    all_scores.append(answer["score"])
        
        avg_score = int(sum(all_scores) / len(all_scores)) if all_scores else 0
        
        return {
            "total_interviews": total_interviews,
            "average_score": avg_score,
            "confidence_rating": min(total_interviews * 2, 10),
            "practice_hours": total_interviews * 0.5
        }
    except Exception as e:
        logger.error(f"Interview stats error: {e}")
        return {
            "total_interviews": 0,
            "average_score": 0,
            "confidence_rating": 0,
            "practice_hours": 0
        }


@router.get("/api/interviews/questions", tags=["Career"])
async def get_interview_questions(
    interview_type: str = Query("technical", description="Type of interview"),
    difficulty: str = Query("medium", description="Difficulty level"),
    count: int = Query(5, description="Number of questions"),
    current_user: dict = Depends(verify_token)
):
    """Get interview questions for practice"""
    try:
        user_id = str(current_user["_id"])
        
        # Get questions based on type - using default questions
        default_questions = [
            {"id": 1, "question": "Tell us about yourself."},
            {"id": 2, "question": "What are your strengths?"},
            {"id": 3, "question": "What are your weaknesses?"},
            {"id": 4, "question": "Why do you want this job?"},
            {"id": 5, "question": "Where do you see yourself in 5 years?"}
        ]
        questions = default_questions
        
        # Shuffle and select requested number
        import random
        random.shuffle(questions)
        selected_questions = questions[:count]
        
        # Create interview session
        interview_session = {
            "user_id": user_id,
            "interview_type": interview_type,
            "difficulty": difficulty,
            "questions": selected_questions,
            "created_at": datetime.now(timezone.utc),
            "status": "started"
        }
        
        result = await interviews_collection.insert_one(interview_session)
        session_id = str(result.inserted_id)
        
        return {
            "success": True,
            "session_id": session_id,
            "questions": selected_questions,
            "interview_type": interview_type,
            "difficulty": difficulty
        }
        
    except Exception as e:
        logger.error(f"Get interview questions error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get interview questions")


@router.post("/api/interviews/analyze", tags=["Career"])
async def analyze_interview_answer(
    audio: UploadFile = File(...),
    question: str = Form(...),
    session_id: str = Form(None),
    current_user: dict = Depends(verify_token)
):
    """Analyze interview answer using AI"""
    try:
        user_id = str(current_user["_id"])
        
        # Save audio file
        audio_content = await audio.read()
        
        # For now, we'll simulate analysis since Gemini/other AI services might need setup
        # In production, you would send this to Whisper API for transcription
        # and then analyze with Gemini
        
        # Simulated analysis
        analysis = {
            "score": random.randint(70, 95),
            "fluency": random.choice(["Good", "Excellent", "Average"]),
            "confidence": random.randint(7, 10),
            "strengths": [
                "Clear articulation",
                "Good structure in answer",
                "Relevant examples provided"
            ],
            "improvements": [
                "Could provide more specific details",
                "Try to reduce filler words",
                "Consider elaborating on technical aspects"
            ],
            "transcription": "This is a simulated transcription of the answer.",
            "keywords_found": ["project", "challenge", "solution", "learning"],
            "speech_rate": random.randint(140, 180),
            "filler_words": random.randint(2, 8)
        }
        
        # Update interview session
        if session_id:
            await interviews_collection.update_one(
                {"_id": ObjectId(session_id)},
                {
                    "$push": {
                        "answers": {
                            "question": question,
                            "analysis": analysis,
                            "timestamp": datetime.now(timezone.utc)
                        }
                    },
                    "$inc": {"questions_answered": 1},
                    "$set": {"last_activity": datetime.now(timezone.utc)}
                }
            )
        
        return {
            "success": True,
            "analysis": analysis,
            "recommendations": [
                "Practice speaking slower for technical explanations",
                "Include more specific metrics in your examples",
                "Structure your answers using STAR method"
            ]
        }
        
    except Exception as e:
        logger.error(f"Analyze interview error: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze interview answer")


@router.post("/api/interviews/complete", tags=["Career"])
async def complete_interview_session(
    session_id: str = Form(...),
    total_duration: int = Form(...),
    current_user: dict = Depends(verify_token)
):
    """Complete an interview session and get final feedback"""
    try:
        user_id = str(current_user["_id"])
        
        # Get session
        session = await interviews_collection.find_one({
            "_id": ObjectId(session_id),
            "user_id": user_id
        })
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Calculate final score
        answers = session.get("answers", [])
        if answers:
            total_score = sum(a.get("analysis", {}).get("score", 0) for a in answers)
            avg_score = round(total_score / len(answers), 1)
            
            # Update session
            await interviews_collection.update_one(
                {"_id": ObjectId(session_id)},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.now(timezone.utc),
                        "score": avg_score,
                        "duration_minutes": total_duration,
                        "confidence_score": random.randint(7, 9)
                    }
                }
            )
            
            # Award credits for completion
            credits_earned = 50
            await update_user_credits(
                user_id=user_id,
                amount=credits_earned,
                source="mock_interview",
                description=f"Completed {session['interview_type']} interview practice"
            )
            
            return {
                "success": True,
                "score": avg_score,
                "credits_earned": credits_earned,
                "duration_minutes": total_duration,
                "questions_answered": len(answers),
                "feedback": {
                    "overall_performance": "Good" if avg_score >= 70 else "Needs Improvement",
                    "strengths": [
                        "Good technical knowledge",
                        "Clear communication style",
                        "Relevant examples"
                    ],
                    "areas_to_improve": [
                        "Time management during answers",
                        "Depth of technical explanations"
                    ],
                    "next_steps": [
                        "Practice more behavioral questions",
                        "Work on concise answers",
                        "Record yourself and review"
                    ]
                }
            }
        
        raise HTTPException(status_code=400, detail="No answers found in session")
        
    except Exception as e:
        logger.error(f"Complete interview error: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete interview session")


@router.post("/api/interviews/session/start")
async def start_interview_session(request: InterviewRequest, current_user: dict = Depends(verify_token)):
    # Create a new interview session
    session_id = ObjectId()
    
    # Generate questions based on role (simple logic for now)
    base_questions = [
        "Tell me about yourself.",
        f"Why do you want to work as a {request.role} at {request.company}?",
        "What are your greatest strengths and weaknesses?",
        "Describe a challenging project you worked on."
    ]
    
    if request.role.lower() in ["developer", "engineer", "programmer"]:
        base_questions.append("Explain a complex technical concept to a non-technical person.")
    
    session = {
        "_id": session_id,
        "user_id": current_user["_id"],
        "company": request.company,
        "role": request.role,
        "status": "in_progress",
        "started_at": datetime.now(timezone.utc),
        "questions": base_questions,
        "current_question_index": 0,
        "answers": []
    }
    await interviews_collection.insert_one(session)
    return {
        "session_id": str(session_id), 
        "first_question": session["questions"][0],
        "total_questions": len(base_questions)
    }


@router.post("/api/interviews/session/{session_id}/answer")
async def submit_interview_answer(
    session_id: str, 
    text_answer: str = Form(...),
    current_user: dict = Depends(verify_token)
):
    if not ObjectId.is_valid(session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID")

    session = await interviews_collection.find_one({"_id": ObjectId(session_id)})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    current_idx = session.get("current_question_index", 0)
    questions = session.get("questions", [])
    
    # Handle completion case if called mistakenly
    if current_idx >= len(questions):
        return {
            "feedback": "Interview already completed.",
            "score": 0,
            "next_question": None,
            "is_completed": True
        }
        
    current_question = questions[current_idx]
    
    # Generate AI Feedback
    feedback = "Good effort!"
    score = 75
    
    if gemini_model:
        try:
            prompt = f"""
            You are an expert technical interviewer.
            Question: "{current_question}"
            Candidate Answer: "{text_answer}"
            
            Provide:
            1. A score (0-100)
            2. Concise text feedback (max 3 sentences) highlighting what was good and what could be improved.
            
            Return ONLY a valid JSON object in this format: {{"score": 85, "feedback": "Your text here..."}}
            """
            response = await asyncio.to_thread(gemini_model.generate_content, prompt)
            
            # Clean up response text to ensure it's valid JSON
            response_text = response.text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith("```"):
                 response_text = response_text[3:-3].strip()
                 
            ai_data = json.loads(response_text)
            feedback = ai_data.get("feedback", feedback)
            score = ai_data.get("score", score)
        except Exception as e:
            logger.error(f"AI Feedback generation failed: {e}")
            feedback = "AI analysis temporary unavailable. Your answer has been recorded."
            score = 80
    
    await interviews_collection.update_one(
        {"_id": ObjectId(session_id)},
        {"$push": {
            "answers": {
                "question": current_question,
                "text": text_answer,
                "feedback": feedback,
                "score": score,
                "timestamp": datetime.now(timezone.utc)
            }
        },
        "$inc": {"current_question_index": 1}
        }
    )
    
    # Get next question logic
    updated_session = await interviews_collection.find_one({"_id": ObjectId(session_id)})
    
    if not updated_session:
        raise HTTPException(status_code=404, detail="Interview session not found")
    
    next_idx = updated_session.get("current_question_index", 0)
    
    next_q = None
    is_completed = False
    
    if next_idx < len(questions):
        next_q = questions[next_idx]
    else:
        is_completed = True
        await interviews_collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc)}}
        )
        
    return {
        "feedback": feedback,
        "score": score,
        "next_question": next_q,
        "is_completed": is_completed
    }


@router.get("/api/interviews/history")
async def get_interview_history(current_user: dict = Depends(verify_token)):
    history = await interviews_collection.find({"user_id": current_user["_id"]}).sort("started_at", -1).to_list(20)
    for h in history:
        h["_id"] = str(h["_id"])
        h["user_id"] = str(h["user_id"])
        h["started_at"] = h["started_at"].isoformat() if h.get("started_at") else None
        h["completed_at"] = h["completed_at"].isoformat() if h.get("completed_at") else None
    return history


