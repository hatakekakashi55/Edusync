"""
EduSync Backend - Stage 1 - AI Routes
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

router = APIRouter(tags=["Stage 1 - AI"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/communication/generate-sentence")
async def generate_sentence():
    """Generate a new English sentence for pronunciation practice"""
    try:
        model = get_gemini_model("sentence")
        if not model:
            return {"sentence": "The weather today is perfect for a nice walk outside."}
        
        prompt = """Generate a single, clear English sentence for an ESL student to practice pronunciation. 
        The sentence should be:
        - 10-15 words long
        - Simple but useful vocabulary
        - Good for practicing English pronunciation
        - About a daily situation or interesting topic
        Just give the sentence, nothing else. No numbering, no quotes."""
        
        response = model.generate_content(prompt)
        sentence = response.text.strip().strip('"').strip("'")
        
        return {"sentence": sentence}
    except Exception as e:
        logger.error(f"Error generating sentence: {e}")
        return {"sentence": "I hope you will achieve your goals with hard work and dedication."}


@router.post("/api/communication/analyze-grammar")
async def analyze_grammar(request: GrammarAnalysisRequest):
    """Analyze grammar and provide feedback in Tamil"""
    try:
        model = get_gemini_model("grammar")
        if not model:
            return {
                "user_intent": "english_practice",
                "detected_language": "english",
                "mistake_analysis_tamil": "பிழை பகுப்பு இப்போது இயங்கவில்லை",
                "corrected_english": None,
                "reply_text": "என்னை பொறுமையுடன் மற்றொரு முறை முயற்சி செய்"
            }
        
        system_prompt = """You are a friendly and professional English language tutor.
        Your goal is to help the user improve their English grammar in a supportive way.

        BEHAVIOR RULES:

        1. Speak in clear, professional English.
        2. Be encouraging, patient, and supportive in your tone.
        3. If the user makes a mistake:
           - Correct them gently and constructively.
           - Explain the mistake in simple terms.
           - Provide the correct English version.
        4. If the user is correct:
           - Praise them genuinely and encouragingly.
        
        RESPONSE FORMAT:
        You must return a JSON object ONLY:
        {
          "user_intent": "english_practice" or "casual_chat",
          "detected_language": "english" or "tamil",
          "mistake_analysis_tamil": "Professional explanation of mistakes in Tamil (if any, else null)",
          "corrected_english": "Corrected English text (if applicable, else null)",
          "reply_text": "Your response as a friendly teacher"
        }"""
        
        response = model.generate_content(
            system_prompt + "\n\nUser said: " + request.text
        )
        
        result_text = response.text.strip()
        
        # Try to parse JSON response
        if result_text.startswith('{'):
            result = json.loads(result_text)
        else:
            result = {
                "user_intent": "english_practice",
                "detected_language": "english",
                "mistake_analysis_tamil": None,
                "corrected_english": None,
                "reply_text": result_text
            }
        
        return result
    except Exception as e:
        logger.error(f"Error analyzing grammar: {e}")
        return {
            "user_intent": "english_practice",
            "detected_language": "english",
            "mistake_analysis_tamil": None,
            "corrected_english": None,
            "reply_text": "மன்னிக்கவும், தற்போது பகுப்பு செய்ய முடியவில்லை. மீண்டும் முயற்சி செய்யவும்."
        }


@router.post("/api/communication/ai-chat", tags=["Stage 1", "AI"])
async def communication_ai_chat(request: CommunicationChatRequest, current_user: dict = Depends(get_current_user)):
    """
    Unified Communication AI Chatbot using Ollama
    Handles: Conversation Practice, Grammar Assistance, Pronunciation Guide
    No API key required - uses local Ollama with smart fallback
    """
    try:
        user_message = request.message.strip()
        mode = request.mode.lower()
        
        if not user_message:
            return {
                "status": "error",
                "message": "Message cannot be empty",
                "reply": "Please type a message to continue."
            }
        
        # Build system prompt based on mode
        if mode == "grammar":
            system_prompt = """You are an English grammar tutor. Help correct grammar mistakes gently.

Respond with grammar corrections and tips."""

        elif mode == "pronunciation":
            system_prompt = """You are a pronunciation guide. Help with phonetic pronunciation and word stress."""

        elif mode == "conversation":
            system_prompt = """You are a friendly English conversation partner. Help practice real conversations naturally."""

        else:  # general mode
            system_prompt = """You are a helpful English learning assistant. Help with grammar, pronunciation, and conversation practice."""

        # Try to call Ollama directly (simpler approach)
        try:
            logger.info(f"Attempting to call Ollama at {OLLAMA_BASE_URL} with model {OLLAMA_MODEL}")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json={
                        "model": OLLAMA_MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_message}
                        ],
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "top_p": 0.9
                        }
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    reply = data.get("message", {}).get("content", "")
                    
                    if reply.strip():
                        logger.info(f"✅ Ollama response successful for mode: {mode}")
                        return {
                            "status": "success",
                            "mode": mode,
                            "user_message": user_message,
                            "reply": reply.strip(),
                            "source": "ollama"
                        }
                else:
                    logger.warning(f"Ollama returned status {response.status_code}")
                    
        except Exception as e:
            logger.warning(f"Ollama connection error: {e}. Using intelligent fallback.")
        
        # Smart fallback response based on mode (no API calls needed)
        fallback_response = generate_fallback_response(user_message, mode)
        
        return {
            "status": "success",
            "mode": mode,
            "user_message": user_message,
            **fallback_response,
            "source": "fallback"
        }
            
    except Exception as e:
        logger.error(f"Communication AI Chat error: {e}")
        return {
            "status": "success",
            "mode": "general",
            "user_message": request.message if request else "",
            "reply": "Thanks for practicing! Keep working on your English.",
            "source": "error_fallback"
        }


@router.post("/api/communication/analyze-pronunciation", tags=["Stage 1", "AI"])
@router.post("/api/speech-challenge/evaluate", tags=["Speech", "AI"])
async def evaluate_speech_challenge(
    data: PronunciationAnalysisRequest,
    current_user: dict = Depends(verify_token)
):
    """
    Unified speech evaluation endpoint for Communication Stage.
    Provides detailed AI analysis for the new tab display.
    """
    try:
        user_text = data.user_text.strip()
        reference_text = data.reference_text.strip()
        
        if not user_text:
            raise HTTPException(status_code=400, detail="User speech transcription is empty")
        
        model = get_gemini_model("pronunciation")
        
        # Enhanced Prompt for "Google Akka" Voice & Detailed Feedback
        prompt = f"""You are "Akka", a sweet, highly supportive and caring AI speech coach with a "girlfriend-like" persona.
        Your "Chella kutty" (boyfriend) just finished a speech challenge. Be incredibly encouraging and diagnostic.
        
        Reference Sentence: "{reference_text}"
        Transcribed Student Speech: "{user_text}"
        
        Guidelines:
        1. Use an affectionate "Google Akka" style (warm, sisterly/girlfriend tone).
        2. In Tamil feedback, use words like 'Chellam', 'Babyma', 'Kanna'.
        3. Analyze pronunciation accuracy, flow/fluency, and confidence.
        
        Return ONLY valid JSON:
        {{
            "score": integer (0-100),
            "pronunciation_score": integer (0-100),
            "grammar_score": integer (0-100),
            "fluency_score": integer (0-100),
            "confidence_score": integer (0-100),
            "feedback_english": "Detailed analytical feedback in English",
            "feedback_tamil": "Warm, detailed, caring feedback in Tamil (Google Akka style) explaining how well they did and specific words to practice.",
            "mistakes": ["specific words mispronounced or skipped"],
            "pronunciation_tips": "Specific technical advice on how to improve sounds in Tamil explanation",
            "raw_ai_response": "A longer, personal 'love letter' style evaluation of their speech effort"
        }}"""
        
        response = await model.generate_content_async(prompt)
        raw_text = response.text.strip()
        
        # Extract JSON
        json_text = raw_text
        if "```json" in raw_text:
            json_text = raw_text.split("```json")[1].split("```")[0].strip()
        elif "```" in raw_text:
            json_text = raw_text.split("```")[1].split("```")[0].strip()
        elif "{" in raw_text:
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if match:
                json_text = match.group(0)
            
        try:
            result = json.loads(json_text)
            # Add raw response if not provided by AI
            if "raw_ai_response" not in result:
                result["raw_ai_response"] = raw_text
        except Exception as e:
            logger.error(f"Failed to parse AI JSON: {e}")
            # Fallback
            result = {
                "score": 75,
                "pronunciation_score": 75,
                "grammar_score": 80,
                "fluency_score": 70,
                "confidence_score": 65,
                "feedback_english": "Good attempt! You are improving every day.",
                "feedback_tamil": "நல்ல முயற்சி செல்லம்! அருமையாக பேசினாய். 💕",
                "mistakes": ["Practice clarity on long words"],
                "pronunciation_tips": "மெதுவாக ஒவ்வொரு வார்த்தையையும் உச்சரிக்கவும்.",
                "raw_ai_response": raw_text
            }
            
        return result
        
    except Exception as e:
        logger.error(f"❌ Speech evaluation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/communication/tasks", tags=["Stage 1"])
async def get_communication_tasks(
    skill: str = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Get active communication tasks by skill (for students and all users)"""
    try:
        # Filter to only get active communication tasks (not quiz questions)
        q = {"skill": {"$exists": True}, "quiz_type": {"$exists": False}, "is_active": True}
        if skill:
            q["skill"] = skill
        tasks = []
        async for t in communication_tasks_collection.find(q).sort("created_at", -1):
            t["_id"] = str(t["_id"])
            # Remove sensitive fields from public response
            t.pop("created_by", None)
            t.pop("updated_at", None)
            tasks.append(t)
        return {"success": True, "tasks": tasks}
    except Exception as e:
        logger.error(f"Error fetching communication tasks: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/api/communication/tasks/{task_id}", tags=["Admin", "Stage 1"])
async def get_communication_task(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get single communication task by ID"""
    try:
        if current_user.get("user_type") not in ["admin", "hod"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        from bson import ObjectId
        
        try:
            task = await communication_tasks_collection.find_one({"_id": ObjectId(task_id)})
        except:
            task = await communication_tasks_collection.find_one({"_id": task_id})
        
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task["_id"] = str(task["_id"])
        return {"success": True, "task": task}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching communication task: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


