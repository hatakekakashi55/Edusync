"""
EduSync Backend - Stage 1 - Writing Routes
Auto-extracted from main.py via AST parser.
"""
import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path to allow direct execution
root_path = Path(__file__).resolve().parent.parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.append(str(root_path))

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
from app.services.ai_service import AIService
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

router = APIRouter(tags=["Stage 1 - Writing"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/stage1/write-challenge/admin", tags=["Stage 1", "Student"])
async def get_admin_write_challenge(current_user: dict = Depends(get_current_user)):
    """Get a random admin-created writing challenge"""
    try:
        pipeline = [
            {"$match": {"is_active": True, "source": "admin"}},
            {"$sample": {"size": 1}}
        ]
        
        cursor = writing_challenges_collection.aggregate(pipeline)
        challenges = await cursor.to_list(length=1)
        
        if not challenges:
            raise HTTPException(status_code=404, detail="No admin writing challenges available")
        
        challenge = challenges[0]
        challenge["_id"] = str(challenge["_id"])
        
        return {"success": True, "challenge": challenge}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching admin writing challenge: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/stage1/write-challenge/ai", tags=["Stage 1", "Student"])
async def get_ai_write_challenge(current_user: dict = Depends(get_current_user)):
    """Generate an AI writing challenge using Ollama"""
    # Fallback writing challenges when API fails
    fallback_challenges = [
        {
            "topic": "My Favorite Hobby",
            "description": "Write about your favorite hobby and why you enjoy it so much. Include specific examples."
        },
        {
            "topic": "A Memorable Day",
            "description": "Describe a day that was memorable for you. What happened? Why was it special?"
        },
        {
            "topic": "Future Dreams",
            "description": "Write about your dreams and goals for the future. What do you want to achieve?"
        },
        {
            "topic": "Family Traditions",
            "description": "Describe a family tradition or custom that is important to you."
        },
        {
            "topic": "Travel Experience",
            "description": "Write about a place you have visited or would like to visit. Describe its attractions."
        },
        {
            "topic": "Technology Impact",
            "description": "Discuss how technology has changed your daily life. Is it positive or negative?"
        },
        {
            "topic": "Environmental Concerns",
            "description": "Write about an environmental issue and what you think can be done to help."
        },
        {
            "topic": "Cultural Exchange",
            "description": "Describe an interesting custom or tradition from a culture different from your own."
        }
    ]
    
    try:
        # Use Ollama directly for generating topics
        prompt = """Generate a writing challenge topic for ESL students.
        
        CRITICAL: Your response must follow this EXACT format:
        TOPIC: [Short engaging topic - 2-5 words]
        DESCRIPTION: [2-3 sentences explaining what the student should write about]
        
        Example:
        TOPIC: My Favorite Memory
        DESCRIPTION: Write about a special memory from your childhood. Explain why it is important to you and how it makes you feel when you think about it.
        
        Make it interesting and relevant to students."""
        
        text = await AIService.call_kimi(prompt)
        if not text:
            raise Exception("Gemini model response was empty")
        
        # Robust Parsing
        topic = "Write about your day"
        description = "Describe your typical daily routine and the things you enjoy doing the most."
        
        # Try to extract TOPIC: and DESCRIPTION: using regex for robustness
        import re
        topic_match = re.search(r'(?i)(?:TOPIC|Topic):\s*(.*)', text)
        desc_match = re.search(r'(?i)(?:DESCRIPTION|Description):\s*([\s\S]*)', text)
        
        if topic_match:
            topic = topic_match.group(1).strip().strip('*').strip('"')
            # If description is inside topic match (due to lack of newline), clean it up
            if "DESCRIPTION" in topic.upper():
                topic = topic[:topic.upper().find("DESCRIPTION")].strip()
        
        if desc_match:
            description = desc_match.group(1).strip().strip('*').strip('"')
            # Clean up trailing content if any
            if "TOPIC" in description.upper() and description.upper().find("TOPIC") > 0:
                 description = description[:description.upper().find("TOPIC")].strip()
        
        # Fallback to line splitting if regex fails or looks weird
        if len(topic) < 2 or len(description) < 10:
            lines = text.split('\n')
            for line in lines:
                if line.upper().startswith("TOPIC:"):
                    topic = line.split(":", 1)[1].strip()
                elif line.upper().startswith("DESCRIPTION:"):
                    description = line.split(":", 1)[1].strip()
        
        # Create AI challenge with matching frontend fields (title and instructions)
        challenge_data = {
            "title": topic,
            "instructions": description,
            "content": description,
            "topic": topic,
            "description": description,
            "difficulty": "medium",
            "time_limit": 600,
            "min_words": 100,
            "credits": 25,
            "duration": 10,
            "source": "ollama",
            "is_active": True,
            "created_at": datetime.now(timezone.utc)
        }
        
        result = await writing_challenges_collection.insert_one(challenge_data)
        challenge_data["_id"] = str(result.inserted_id)
        
        logger.info(f"✅ AI writing challenge generated via Ollama: {topic}")
        return {"success": True, "challenge": challenge_data}
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Error generating AI writing challenge: {error_msg}")
        
        # Use random fallback challenge
        fallback = random.choice(fallback_challenges)
        challenge_data = {
            "title": fallback["topic"],
            "instructions": fallback["description"],
            "content": fallback["description"],
            "topic": fallback["topic"],
            "description": fallback["description"],
            "difficulty": "medium",
            "time_limit": 600,
            "min_words": 100,
            "credits": 20,
            "duration": 10,
            "source": "fallback",
            "is_active": True,
            "created_at": datetime.now(timezone.utc)
        }
        
        result = await writing_challenges_collection.insert_one(challenge_data)
        challenge_data["_id"] = str(result.inserted_id)
        
        logger.warning("⚠️ Ollama unavailable - using fallback writing challenge")
        return {"success": True, "challenge": challenge_data, "warning": "Using fallback challenge due to service unavailability"}


@router.post("/api/stage1/write-challenge/submit", tags=["Stage 1", "Student"])
async def submit_write_challenge(
    payload: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Submit a writing challenge and get AI feedback"""
    try:
        challenge_id = payload.get("challenge_id")
        written_text = payload.get("written_text", "")
        time_taken = payload.get("time_taken", 0)
        
        if not challenge_id:
            raise HTTPException(status_code=400, detail="Challenge ID is required")
        
        if not written_text:
            raise HTTPException(status_code=400, detail="Essay text is required")
        # Validate challenge_id is a valid ObjectId
        try:
            challenge_oid = ObjectId(challenge_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid challenge ID format")
        
        # Get challenge - Check both writing_challenges and communication_tasks collections
        challenge = await writing_challenges_collection.find_one({"_id": challenge_oid})
        if not challenge:
            # Try searching in communication_tasks collection as fallback (for admin tasks)
            challenge = await communication_tasks_collection.find_one({"_id": challenge_oid})
            
        if not challenge:
            raise HTTPException(status_code=404, detail="Challenge not found")
        
        # Count words
        word_count = len(written_text.split())
        min_words = challenge.get("min_words", 50)
        
        # AI Analysis with Advanced Error Handling and Retry Logic
        ai_success = False
        max_retries = 3
        retry_count = 0
        
        # Initialize evaluation variables to avoid UnboundLocalError
        score = 0
        feedback = "Submission evaluated by system."
        tamil_feedback = "நல்ல முயற்சி! உங்கள் எழுத்துப்பணி அருமை."
        mistakes = []
        praise = "Keep writing!"
        suggestions = ["Focus on flow and structure."]
        corrected_text = "" # New: Suggested revision
        raw_ai_response = "AI Evaluation Failed"
        
        while not ai_success and retry_count < max_retries:
            try:
                system_prompt = "You are a professional, friendly, and supportive AI writing coach and teacher."
                prompt = f"""Evaluate the student's writing on the topic: "{challenge.get('topic')}"
                
                Student's English:
                "{written_text}"
                
                Provide constructive feedback and identify specific improvements.
                
                Your response must be a valid JSON object ONLY:
                {{
                    "score": integer (0-100),
                    "grammar_score": integer (0-100),
                    "vocabulary_score": integer (0-100),
                    "coherence_score": integer (0-100),
                    "feedback": "Two sentences of constructive feedback in English",
                    "tamil_feedback": "A professional and encouraging explanation in Tamil about their mistakes and how they can improve. Maintain a respectful teacher-student tone.",
                    "mistakes": ["specific errors in English"],
                    "suggestions": ["how to specifically improve next time"],
                    "corrected_text": "The corrected version of their writing in English",
                    "praise": "Exactly what they did well in their effort"
                }}"""
                
                json_str = await AIService.call_kimi(prompt, system_prompt, json_mode=True)
                if not json_str:
                    raise Exception("Empty AI response")
                
                logger.debug(f"🤖 Raw AI Eval Response: {json_str[:500]}...")
                
                # Robust JSON extraction
                if "{" in json_str:
                    start_idx = json_str.find("{")
                    end_idx = json_str.rfind("}")
                    if start_idx != -1 and end_idx != -1:
                        json_str = json_str[start_idx : end_idx + 1]
                
                result = json.loads(json_str)
                
                # Validate required fields
                if "score" not in result:
                    raise Exception("Missing score in AI response")
                    
                score = result.get("score", 70)
                feedback = result.get("feedback", "Good effort!")
                tamil_feedback = result.get("tamil_feedback", "சிறந்த முயற்சி! உங்கள் எழுத்துத் திறன் நன்றாக உள்ளது.")
                mistakes = result.get("mistakes", [])
                suggestions = result.get("suggestions", [])
                corrected_text = result.get("corrected_text", "")
                praise = result.get("praise", "Keep writing!")
                
                ai_success = True
                raw_ai_response = json_str
                logger.info(f"✅ AI evaluation successful on attempt {retry_count + 1}")
                
            except json.JSONDecodeError as e:
                retry_count += 1
                logger.error(f"❌ JSON parsing failed (attempt {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    await asyncio.sleep(0.5)  # Brief delay before retry
                    
            except Exception as e:
                retry_count += 1
                logger.error(f"❌ AI evaluation failed (attempt {retry_count}/{max_retries}): {e}")
                if retry_count < max_retries:
                    await asyncio.sleep(0.5)  # Brief delay before retry
        
        # Fallback if AI failed after all retries
        if not ai_success:
            logger.warning("⚠️ Using fallback evaluation after AI failures")
            score = min(100, (word_count / min_words) * 80)
            suggestions = ["Keep practicing your writing skills"]
            praise = "You completed the challenge!"
        
        # Generate voice feedback
        audio_filename = None
        try:
            # Use Tamil feedback for "Google Akka" voice if available
            voice_text = tamil_feedback or feedback
            tts_lang = 'ta' if tamil_feedback else 'en'
            # Use co.in for Indian accent/Google Akka feel
            tts = gTTS(text=voice_text, lang=tts_lang, slow=False, tld='co.in')
            
            audio_filename = f"write_feedback_{current_user['_id']}_{int(datetime.now().timestamp())}.mp3"
            audio_path = f"static/uploads/{audio_filename}"
            tts.save(audio_path)

            
            logger.info(f"✅ Voice feedback generated: {audio_filename}")
        except Exception as e:
            logger.error(f"❌ Voice generation failed: {e}")
        
        # Calculate credits
        passed = score >= 60 and word_count >= min_words
        credits_earned = 0
        
        if passed:
            already_completed = await communication_submissions_collection.find_one({
                "user_id": str(current_user["_id"]),
                "challenge_id": challenge_id,
                "challenge_type": "write",
                "score": {"$gte": 60}
            })
            
            if not already_completed:
                credits_earned = challenge.get("credits", 20)
                await update_user_credits(
                    str(current_user["_id"]),
                    credits_earned,
                    "write_challenge",
                    f"Completed writing challenge"
                )
        
        # Save submission
        submission_data = {
            "user_id": str(current_user["_id"]),
            "challenge_type": "write",
            "challenge_id": challenge_id,
            "submission_text": written_text,
            "time_taken": time_taken,
            "word_count": word_count,
            "score": score,
            "passed": passed,
            "feedback": feedback,
            "tamil_feedback": tamil_feedback,
            "mistakes": mistakes,
            "suggestions": suggestions,
            "corrected_text": corrected_text,
            "praise": praise,
            "credits_earned": credits_earned,
            "submitted_at": datetime.now(timezone.utc)
        }
        
        await communication_submissions_collection.insert_one(submission_data)
        
        return {
            "success": True,
            "passed": passed,
            "score": score,
            "word_count": word_count,
            "feedback": feedback,
            "tamil_feedback": tamil_feedback,
            "mistakes": mistakes,
            "suggestions": suggestions,
            "corrected_text": corrected_text,
            "praise": praise,
            "credits_earned": credits_earned,
            "audio_url": f"/static/uploads/{audio_filename}" if audio_filename else None,
            "raw_ai_response": raw_ai_response if ai_success else "AI Evaluation Failed"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error submitting write challenge: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/stage1/generate-writing-challenge")
async def generate_writing_challenge(
    request_data: dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Generate a writing challenge using Ollama"""
    try:
        difficulty = request_data.get("difficulty", "intermediate")
        topic = request_data.get("topic", "general")
        
        # Create prompt for Ollama
        prompt = f"""Generate a writing prompt for ESL students at {difficulty} level.

The prompt should:
1. Be clear and engaging
2. Encourage 100-150 word response
3. Be about {topic if topic != 'general' else 'an interesting topic'}

Format your response as:
TOPIC: [Short writing topic - 2-3 words]
DESCRIPTION: [Full prompt description - 2-3 sentences explaining what to write]"""
        
        text = await AIService.call_kimi(prompt)
        if not text:
            raise Exception("Gemini model response was empty")
        
        # Robust Parsing
        topic_text = "Daily Life"
        description = "Write about your daily routines and how you spend your time."
        
        # Try to extract TOPIC: and DESCRIPTION: using regex for robustness
        import re
        topic_match = re.search(r'(?i)(?:TOPIC|Topic):\s*(.*)', text)
        desc_match = re.search(r'(?i)(?:DESCRIPTION|Description):\s*([\s\S]*)', text)
        
        if topic_match:
            topic_text = topic_match.group(1).strip().strip('*').strip('"')
            if "DESCRIPTION" in topic_text.upper():
                topic_text = topic_text[:topic_text.upper().find("DESCRIPTION")].strip()
        
        if desc_match:
            description = desc_match.group(1).strip().strip('*').strip('"')
            if "TOPIC" in description.upper() and description.upper().find("TOPIC") > 0:
                 description = description[:description.upper().find("TOPIC")].strip()
        
        # Fallback to line splitting if regex fails or looks weird
        if len(topic_text) < 2 or len(description) < 10:
            lines = text.split('\n')
            for line in lines:
                if line.upper().startswith("TOPIC:"):
                    topic_text = line.split(":", 1)[1].strip()
                elif line.upper().startswith("DESCRIPTION:"):
                    description = line.split(":", 1)[1].strip()
        
        # Create challenge data with matching frontend fields
        challenge_data = {
            "title": topic_text,
            "instructions": description,
            "content": description,
            "topic": topic_text,
            "description": description,
            "difficulty": difficulty,
            "time_limit": 600,  # 10 minutes
            "min_words": 100,
            "credits": 25,
            "skill": "writing",
            "source": "ollama",
            "is_active": True,
            "duration": 10,  # minutes
            "created_at": datetime.now(timezone.utc)
        }
        
        # Store the generated challenge in the database
        result = await writing_challenges_collection.insert_one(challenge_data)
        challenge_data["_id"] = str(result.inserted_id)
        
        logger.info(f"✅ Writing challenge generated and saved via Ollama: {topic_text}")
        return {"success": True, "challenge": challenge_data}
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Error generating writing challenge: {error_msg}")
        
        # Use fallback challenge
        challenge_data = {
            "topic": "My Best Friend",
            "description": "Write about a close friend and explain what makes them special. Include specific examples of why you value their friendship.",
            "difficulty": "intermediate",
            "time_limit": 600,
            "min_words": 100,
            "credits": 20,
            "skill": "writing",
            "source": "fallback",
            "is_active": True,
            "duration": 10,
            "created_at": datetime.now(timezone.utc)
        }
        
        # Store the fallback challenge in the database
        result = await writing_challenges_collection.insert_one(challenge_data)
        challenge_data["_id"] = str(result.inserted_id)
        
        logger.warning("⚠️ Ollama unavailable - using fallback writing challenge")
        return {"success": True, "challenge": challenge_data}


