"""
EduSync Backend - Speech Routes
Modularized and deduplicated.
"""
import logging
import io
from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query, Body, Request
from fastapi.responses import StreamingResponse

from app.dependencies import verify_token
from app.database import *
from app.models.speech import SpeechRequest
from app.services.speech_service import SpeechService

logger = logging.getLogger("edusync")

router = APIRouter(prefix="/api/speech", tags=["Speech"])

@router.post("/generate", tags=["Speech"])
async def generate_speech(
    request: Request,
    speech_data: Optional[SpeechRequest] = None,
    current_user: dict = Depends(verify_token)
):
    """Generate audio from text (TTS) supporting both JSON and model formats"""
    try:
        text = ""
        lang = "en"
        
        if speech_data:
            text = speech_data.text
            lang = speech_data.lang or speech_data.language or "en"
        elif request:
            try:
                data = await request.json()
                text = data.get("text", "")
                lang = data.get("lang") or data.get("language") or "en"
            except:
                pass
                
        if not text:
             raise HTTPException(status_code=400, detail="Text is required")
             
        audio_bytes = await SpeechService.text_to_speech(text, lang)
        
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/mpeg"
        )
    except Exception as e:
        logger.error(f"Generate speech error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/text-to-speech", tags=["Speech"])
async def tts_classic(
    text: str = Form(...),
    language: str = Form("en"),
    speed: float = Form(1.0),
    current_user: dict = Depends(verify_token)
):
    """Form-based TTS for legacy support"""
    try:
        audio_bytes = await SpeechService.text_to_speech(text, language, speed)
        return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/speech-to-text", tags=["Speech"])
async def stt(
    audio_file: UploadFile = File(...),
    language: str = Form("en-US"),
    current_user: dict = Depends(verify_token)
):
    """Convert audio to text"""
    try:
        audio_bytes = await audio_file.read()
        text = await SpeechService.speech_to_text(audio_bytes, language)
        return {"success": True, "text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
