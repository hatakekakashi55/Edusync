"""
EduSync Backend - AI Routes
Modularized and deduplicated.
"""
import logging
import uuid
import os
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query, Body
from fastapi.responses import JSONResponse, StreamingResponse

from app.dependencies import get_current_user, verify_token, convert_objectid_to_str
from app.database import *
from app.services.ai_service import AIService, call_gemini_with_retry
from app.services.speech_service import SpeechService
from app.services.ai_wrapper import get_gemini_model
from app.utils.helpers import clean_markdown_formatting
from app.lifespan import get_redis_client

# Import models
from app.models.auth import *
from app.models.ai import *
from app.models.challenge import *


logger = logging.getLogger("edusync")

router = APIRouter(prefix="/api/ai", tags=["AI"])

@router.post("/public-assistant", tags=["AI"])
async def public_assistant(
    message: str = Body(..., embed=True),
    conversation_history: List[Dict[str, str]] = Body(default=[])
):
    """Public AI Chatbot for Landing Page - No authentication required"""
    try:
        active_message = message
        if not active_message or not active_message.strip():
            raise HTTPException(status_code=400, detail="Please type a message")
        
        model = get_gemini_model("default")
        if not model:
            raise HTTPException(status_code=503, detail="AI service unavailable")
        
        # Build conversation history context
        history_text = ""
        if conversation_history:
            for msg in conversation_history[-3:]: # Only take last 3 for public assistant
                role = msg.get("role", "user")
                content = msg.get("content", "")
                history_text += f"{role.capitalize()}: {content}\n"
        
        # STRICT SYSTEM PROMPT for EduSync
        system_prompt = f"""You are the EduSync 4.0 Assistant. Your role is ONLY to answer questions about EduSync 4.0.
        
EDU SYNC 4.0 INFORMATION:
EduSync is an AI-powered learning platform that revolutionizes campus education.
Key Features:
- AI-Powered Learning: Personalized learning paths guided by an intelligent AI tutor.
- Real-time Coding: Execute code in 7+ different languages instantly. Practice algorithms and build projects right in your browser.
- Collaborative Learning: Join study groups, engage in pair programming, and collaborate with peers seamlessly.
- Gamified Experience: Stay motivated with engaging challenges, earn badges, and climb the leaderboard.
- Academic ERP: Comprehensive tools for Faculty and HODs, including classrooms, assignments, materials, and attendance tracking.
- Career Prep: Mock interviews, portfolio building, resume builder, and job application tracking.
- Stage-Based Learning: Stage 1 (Communication), Stage 2 (Technical/Arcade), Stage 3 (Jobs/Placement).

RULES:
1. ONLY answer questions related to EduSync, its features, or education-related queries that EduSync can help with.
2. If a user asks about ANYTHING ELSE (sports, politics, general knowledge, jokes, personal stuff), politely decline and explain that you are specialized for EduSync questions.
3. Keep responses concise, professional, and helpful.
4. Response MUST be in plain text or simple markdown.

Previous conversation:
{history_text}
User Message: {active_message}
"""
        
        response = await model.generate_content_async(system_prompt)
        
        if not response or not response.text:
            raise HTTPException(status_code=500, detail="AI generated empty response")
        
        clean_response = clean_markdown_formatting(response.text)
        
        return {
            "success": True,
            "response": clean_response,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Public Assistant Error: {e}")
        raise HTTPException(status_code=500, detail=f"Assistant failed: {str(e)}")

@router.post("/chat", tags=["AI"])
async def ai_chat(
    message: str = Body(None),
    conversation_history: List[Dict[str, str]] = Body(default=[]),
    context: str = Body(default="general"),
    request: dict = Body(None), # For compatibility with Stage 3 request format
    current_user: dict = Depends(verify_token)
):
    """AI Chat endpoint - Provides intelligent responses to user queries"""
    try:
        # Handle different request formats
        active_message = message
        if not active_message and request:
            active_message = request.get("message")
        
        if not active_message or not active_message.strip():
            raise HTTPException(status_code=400, detail="Please type a message")
        
        # Determine context
        active_context = context
        if request and not active_context:
            active_context = request.get("context", "general")

        model = get_gemini_model("default")
        if not model:
            raise HTTPException(status_code=503, detail="AI service unavailable")
        
        # Build prompt context
        history_text = ""
        if conversation_history:
            for msg in conversation_history[-5:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                history_text += f"{role.capitalize()}: {content}\n"
        
        system_prompt = f"""You are EduSync AI, a professional academic and learning assistant.
Context: {active_context}

CRITICAL RESPONSE FORMAT RULES:
- Respond in plain, clean text.
- Use markdown sparingly for structure (headings, bold) but avoid heavy formatting.
- Be helpful, professional and encouraging.

Previous conversation:
{history_text}
Student's message: {active_message}
"""
        
        response = await model.generate_content_async(system_prompt)
        
        if not response or not response.text:
            raise HTTPException(status_code=500, detail="AI generated empty response")
        
        clean_response = clean_markdown_formatting(response.text)
        
        # Log to DB
        await ai_chats_collection.insert_one({
            "user_id": str(current_user["_id"]),
            "message": active_message,
            "response": clean_response,
            "context": active_context,
            "timestamp": datetime.now(timezone.utc)
        })
        
        return {
            "success": True,
            "response": clean_response,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"AI Chat Error: {e}")
        raise HTTPException(status_code=500, detail=f"AI chat failed: {str(e)}")

@router.get("/chats", tags=["AI"])
async def get_ai_chats(
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get AI chat history"""
    try:
        user_id = str(current_user["_id"])
        total = await ai_chats_collection.count_documents({"user_id": user_id})
        
        chats = await ai_chats_collection.find({"user_id": user_id}) \
            .sort("timestamp", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        return {
            "success": True,
            "chats": convert_objectid_to_str(chats),
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            }
        }
    except Exception as e:
        logger.error(f"Get AI chats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get chat history")

@router.post("/chat-stream", tags=["AI"])
async def ai_chat_stream(
    message: str = Body(..., embed=True),
    context: str = Body(default="general"),
    current_user: dict = Depends(verify_token)
):
    """Streaming AI Chat via Server-Sent Events"""
    async def event_generator():
        try:
            model = get_gemini_model("default")
            prompt = f"You are a helpful education assistant. Context: {context}. User says: {message}"
            
            response = await model.generate_content_async(prompt)
            full_text = clean_markdown_formatting(response.text)
            
            for char in full_text:
                yield f"data: {json.dumps({'token': char})}\n\n"
                await asyncio.sleep(0.01)
                
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/faculty-assistant", tags=["AI"])
async def faculty_voice_assistant(
    message: str = Form(...),
    context: str = Form(None),
    current_user: dict = Depends(verify_token)
):
    """Faculty-specific AI assistant with voice response"""
    if current_user["user_type"] != UserType.FACULTY.value:
        raise HTTPException(status_code=403, detail="Faculty only")
    
    try:
        # Simplified for robustness
        model = get_gemini_model("faculty")
        prompt = f"Faculty Assistant: {message}. Context: {context}"
        
        response = await model.generate_content_async(prompt)
        response_text = response.text
        
        # Audio generation
        audio_url = None
        try:
            audio_response = await SpeechService.text_to_speech(response_text, 'en')
            if audio_response:
                filename = f"faculty_{uuid.uuid4()}.mp3"
                file_path = f"static/audio_faculty/{filename}"
                os.makedirs("static/audio_faculty", exist_ok=True)
                with open(file_path, "wb") as f:
                    f.write(audio_response)
                audio_url = f"/static/audio_faculty/{filename}"
        except: pass
        
        return {
            "response": response_text,
            "audio_url": audio_url,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Faculty assistant error: {e}")
        raise HTTPException(status_code=500, detail="AI Assistant failure")

@router.post("/english-teacher", tags=["AI"])
async def english_teacher(
    text: str = Form(...),
    current_user: dict = Depends(verify_token)
):
    """English tutor feedback"""
    try:
        feedback = await AIService.english_teacher_feedback(text)
        return {"success": True, "feedback": feedback}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/code-help", tags=["AI"])
async def get_code_help(
    help_request: AICodeHelpRequest,
    current_user: dict = Depends(verify_token)
):
    """Coding help"""
    try:
        help_response = await AIService.code_help(
            code=help_request.code or "",
            error=help_request.error or "",
            requirement=help_request.requirement or "",
            language=help_request.language,
            context=help_request.context or ""
        )
        return {"success": True, "help": help_response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/code-review", tags=["AI"])
async def code_review_api(
    review_request: CodeReviewRequest,
    current_user: dict = Depends(verify_token)
):
    """Code review"""
    try:
        requirements = review_request.requirements or []
        review = await AIService.code_review(
            code=review_request.code,
            language=review_request.language,
            requirements=requirements
        )
        return {"success": True, "review": review}
    except Exception as e:
        raise HTTPException(status_code=429 if "429" in str(e) else 500, detail=str(e))

@router.get("/project-ideas", tags=["AI"])
async def get_project_ideas(current_user: dict = Depends(verify_token)):
    """Generate project ideas"""
    try:
        user_id = str(current_user["_id"])
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
            
        project_ideas = await AIService.generate_project_ideas({
            "stage": user.get("stage", "freshie"),
            "skills": user.get("skills", []),
            "interests": user.get("interests", []),
            "department": user.get("department", "Computer Science")
        })
        return {"success": True, "project_ideas": project_ideas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
