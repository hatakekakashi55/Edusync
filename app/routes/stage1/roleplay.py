"""
EduSync Backend - Stage 1 - AI Roleplay Routes
Endpoints for interactive roleplay scenarios (Interview, Sales, Team Lead, Customer Support).
"""
import logging
import os
import re
import json
import uuid
import io
import base64
import asyncio
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query, Body, Request
from fastapi.responses import JSONResponse

from app.dependencies import get_current_user, verify_token
from app.database import *
from app.services.ai_wrapper import get_gemini_model
from app.services.ai_service import AIService
from app.services.speech_service import SpeechService
from app.services.prompts import (
    get_scenario, get_all_scenarios, TONE_ANALYSIS_PROMPT,
    ROLEPLAY_SCENARIOS
)
from app.models.stage1 import (
    RoleplayStartRequest, RoleplayMessageRequest, RoleplayEndRequest,
    SpeechAnalysisRequest, ShadowPracticeRequest, ToneAnalysisRequest
)
from app.config import *

logger = logging.getLogger("edusync")

router = APIRouter(tags=["Stage 1 - Roleplay"])


# ==================== ROLEPLAY ENDPOINTS ====================

@router.get("/api/stage1/roleplay/scenarios")
async def get_roleplay_scenarios(current_user: dict = Depends(get_current_user)):
    """Get all available roleplay scenarios with difficulty levels."""
    try:
        scenarios = get_all_scenarios()
        return {
            "success": True,
            "scenarios": scenarios,
            "total": len(scenarios)
        }
    except Exception as e:
        logger.error(f"Error fetching scenarios: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/stage1/roleplay/start")
async def start_roleplay(
    request: RoleplayStartRequest,
    current_user: dict = Depends(get_current_user)
):
    """Start a new AI roleplay session."""
    try:
        user_id = str(current_user.get("_id", current_user.get("user_id", "")))
        
        # Get scenario config
        scenario_config = get_scenario(request.scenario_type, request.difficulty)
        if not scenario_config:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid scenario type '{request.scenario_type}' or difficulty '{request.difficulty}'"
            )
        
        # Check for existing active session
        existing = await roleplay_sessions_collection.find_one({
            "user_id": user_id,
            "status": "active"
        })
        
        if existing:
            # Auto-abandon the old session
            await roleplay_sessions_collection.update_one(
                {"_id": existing["_id"]},
                {"$set": {"status": "abandoned", "ended_at": datetime.now(timezone.utc)}}
            )
        
        # Create new session
        session_id = str(uuid.uuid4())
        
        # AI opening message
        opening_message = scenario_config["opening"]
        
        session_doc = {
            "session_id": session_id,
            "user_id": user_id,
            "scenario_type": request.scenario_type,
            "difficulty": request.difficulty,
            "scenario_name": scenario_config["name"],
            "system_prompt": scenario_config["system_prompt"],
            "evaluation_prompt": scenario_config["evaluation_prompt"],
            "messages": [
                {
                    "role": "assistant",
                    "content": opening_message,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            ],
            "current_turn": 0,
            "max_turns": scenario_config["max_turns"],
            "credits_possible": scenario_config["credits"],
            "status": "active",
            "started_at": datetime.now(timezone.utc),
            "ended_at": None,
            "evaluation": None,
            "credits_earned": 0
        }
        
        await roleplay_sessions_collection.insert_one(session_doc)
        
        logger.info(f"✅ Roleplay started: {scenario_config['name']} ({request.difficulty}) for user {user_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "scenario": {
                "name": scenario_config["name"],
                "icon": scenario_config.get("icon", "🎭"),
                "description": scenario_config.get("description", ""),
                "difficulty": request.difficulty,
                "max_turns": scenario_config["max_turns"],
                "credits_possible": scenario_config["credits"]
            },
            "opening_message": opening_message,
            "current_turn": 0,
            "max_turns": scenario_config["max_turns"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting roleplay: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/stage1/roleplay/message")
async def send_roleplay_message(
    request: RoleplayMessageRequest,
    current_user: dict = Depends(get_current_user)
):
    """Send a message in an active roleplay session and get AI response."""
    try:
        user_id = str(current_user.get("_id", current_user.get("user_id", "")))
        
        # Find session
        session = await roleplay_sessions_collection.find_one({
            "session_id": request.session_id,
            "user_id": user_id,
            "status": "active"
        })
        
        if not session:
            raise HTTPException(status_code=404, detail="Active session not found")
        
        # Check turn limit
        if session["current_turn"] >= session["max_turns"]:
            return {
                "success": True,
                "session_ended": True,
                "message": "Maximum turns reached. The session will now end.",
                "should_end": True
            }
        
        # Add user message
        user_msg = {
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Build conversation context for AI
        messages_for_ai = [
            {"role": "system", "content": session["system_prompt"]}
        ]
        for msg in session["messages"]:
            messages_for_ai.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        messages_for_ai.append({"role": "user", "content": request.message})
        
        # Get AI response
        ai_reply = ""
        try:
            # Build a single prompt from the conversation
            conversation_text = ""
            for msg in messages_for_ai:
                role_label = msg["role"].capitalize()
                conversation_text += f"{role_label}: {msg['content']}\n\n"
            
            full_prompt = f"""{session['system_prompt']}

Continue this roleplay conversation. Stay completely in character.
Respond naturally as the character would — keep it to 2-3 sentences.

{conversation_text}

Your response as the character (stay in character, 2-3 sentences only):"""
            
            # Use Gemini service
            ai_reply = await AIService.call_kimi(full_prompt, session["system_prompt"])
            
            if not ai_reply:
                ai_reply = "That's an interesting point. Could you elaborate more on that?"
            
            # Clean AI response
            ai_reply = re.sub(r'^(assistant|character|ai|response):\s*', '', ai_reply, flags=re.IGNORECASE)
            ai_reply = ai_reply.strip('"').strip("'").strip()
            
        except Exception as ai_error:
            logger.error(f"AI roleplay response error: {ai_error}")
            ai_reply = "That's an interesting point. Could you elaborate more on that?"
        
        if not ai_reply:
            ai_reply = "I appreciate your response. Let me think about that. Could you tell me more?"
        
        # Create AI message
        ai_msg = {
            "role": "assistant",
            "content": ai_reply,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        new_turn = session["current_turn"] + 1
        should_end = new_turn >= session["max_turns"]
        
        # Quick tone analysis on user message (async, non-blocking)
        tone_data = None
        try:
            tone_data = await _quick_tone_check(request.message)
        except:
            pass
        
        # Update session in DB
        await roleplay_sessions_collection.update_one(
            {"session_id": request.session_id},
            {
                "$push": {"messages": {"$each": [user_msg, ai_msg]}},
                "$set": {"current_turn": new_turn}
            }
        )
        
        logger.info(f"💬 Roleplay turn {new_turn}/{session['max_turns']} for session {request.session_id}")
        
        result = {
            "success": True,
            "ai_response": ai_reply,
            "current_turn": new_turn,
            "max_turns": session["max_turns"],
            "turns_remaining": session["max_turns"] - new_turn,
            "should_end": should_end,
            "session_ended": False
        }
        
        if tone_data:
            result["tone_analysis"] = tone_data
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Roleplay message error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/stage1/roleplay/end")
async def end_roleplay(
    request: RoleplayEndRequest,
    current_user: dict = Depends(get_current_user)
):
    """End a roleplay session and get detailed AI evaluation report."""
    try:
        user_id = str(current_user.get("_id", current_user.get("user_id", "")))
        
        # Find session
        session = await roleplay_sessions_collection.find_one({
            "session_id": request.session_id,
            "user_id": user_id
        })
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if session["status"] == "completed" and session.get("evaluation"):
            # Return existing evaluation
            return {
                "success": True,
                "evaluation": session["evaluation"],
                "credits_earned": session.get("credits_earned", 0),
                "already_evaluated": True
            }
        
        # Build conversation history for evaluation
        conversation_history = ""
        for msg in session.get("messages", []):
            role = "AI Character" if msg["role"] == "assistant" else "Student"
            conversation_history += f"{role}: {msg['content']}\n\n"
        
        # Get evaluation prompt
        eval_prompt_template = session.get("evaluation_prompt", "")
        if not eval_prompt_template:
            scenario = ROLEPLAY_SCENARIOS.get(session.get("scenario_type", ""))
            if scenario:
                eval_prompt_template = scenario.get("evaluation_prompt", "")
        
        eval_prompt = eval_prompt_template.format(conversation_history=conversation_history)
        
        # Get AI evaluation
        evaluation = {}
        try:
            system_prompt = (
                "You are an expert communication coach evaluating a student's performance in a roleplay scenario. "
                "Be constructive, encouraging, and specific. Return ONLY valid JSON."
            )
            
            response = await AIService.call_kimi(eval_prompt, system_prompt, json_mode=True)
            
            try:
                if response:
                    if isinstance(response, str):
                        json_match = re.search(r'\{.*\}', response, re.DOTALL)
                        if json_match:
                            evaluation = json.loads(json_match.group(0))
                        else:
                            raise ValueError("No JSON found")
                    else:
                        evaluation = response
            except Exception as parse_err:
                logger.warning(f"Failed to parse evaluation JSON: {parse_err}")
                
        except Exception as eval_error:
            logger.error(f"AI evaluation error: {eval_error}")
        
        # Ensure minimum evaluation structure
        if not evaluation or "overall_score" not in evaluation:
            evaluation = {
                "overall_score": 65,
                "communication_score": 70,
                "confidence_score": 60,
                "content_quality_score": 65,
                "strengths": ["Good attempt at the exercise"],
                "weaknesses": ["Could be more detailed"],
                "improvement_tips": ["Practice speaking naturally", "Use more specific examples"],
                "overall_feedback": "Good effort! Keep practicing to improve your communication skills.",
                "feedback_tamil": "நல்ல முயற்சி! தொடர்ந்து பயிற்சி செய்யுங்கள்."
            }
        
        # Calculate credits (based on overall score and difficulty)
        overall_score = evaluation.get("overall_score", 50)
        max_credits = session.get("credits_possible", 15)
        credits_earned = int(round(max_credits * (overall_score / 100)))
        credits_earned = max(5, min(max_credits, credits_earned))  # At least 5 credits
        
        # Update session
        await roleplay_sessions_collection.update_one(
            {"session_id": request.session_id},
            {"$set": {
                "status": "completed",
                "ended_at": datetime.now(timezone.utc),
                "evaluation": evaluation,
                "credits_earned": credits_earned
            }}
        )
        
        # Award credits to user
        try:
            await users_collection.update_one(
                {"_id": ObjectId(user_id) if ObjectId.is_valid(user_id) else user_id},
                {"$inc": {"credits": credits_earned}}
            )
        except Exception as credit_err:
            logger.error(f"Failed to award credits: {credit_err}")
        
        logger.info(f"✅ Roleplay completed: {session['scenario_name']} | Score: {overall_score} | Credits: {credits_earned}")
        
        return {
            "success": True,
            "evaluation": evaluation,
            "credits_earned": credits_earned,
            "session_summary": {
                "scenario": session["scenario_name"],
                "difficulty": session["difficulty"],
                "total_turns": session["current_turn"],
                "duration_seconds": (
                    (datetime.now(timezone.utc) - session["started_at"]).total_seconds()
                    if session.get("started_at") else 0
                )
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"End roleplay error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/stage1/roleplay/history")
async def get_roleplay_history(
    limit: int = Query(default=10, le=50),
    current_user: dict = Depends(get_current_user)
):
    """Get user's roleplay session history."""
    try:
        user_id = str(current_user.get("_id", current_user.get("user_id", "")))
        
        sessions = []
        cursor = roleplay_sessions_collection.find(
            {"user_id": user_id, "status": {"$in": ["completed", "abandoned"]}}
        ).sort("started_at", -1).limit(limit)
        
        async for session in cursor:
            sessions.append({
                "session_id": session["session_id"],
                "scenario_name": session.get("scenario_name", "Unknown"),
                "scenario_type": session.get("scenario_type", ""),
                "difficulty": session.get("difficulty", "easy"),
                "status": session.get("status", ""),
                "overall_score": session.get("evaluation", {}).get("overall_score", 0) if session.get("evaluation") else 0,
                "credits_earned": session.get("credits_earned", 0),
                "total_turns": session.get("current_turn", 0),
                "started_at": session.get("started_at", "").isoformat() if session.get("started_at") else "",
                "ended_at": session.get("ended_at", "").isoformat() if session.get("ended_at") else ""
            })
        
        return {
            "success": True,
            "sessions": sessions,
            "total": len(sessions)
        }
        
    except Exception as e:
        logger.error(f"Error fetching roleplay history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SPEECH ANALYSIS ENDPOINTS ====================

@router.post("/api/stage1/analyze-speech")
async def analyze_speech_audio(
    audio: UploadFile = File(...),
    audio_duration: float = Form(default=0),
    current_user: dict = Depends(get_current_user)
):
    """
    Full speech analysis from audio:
    - Transcription (Whisper/Deepgram/Fallback)
    - Filler word detection
    - WPM & Pace analysis
    - Clarity score
    """
    try:
        audio_content = await audio.read()
        
        if len(audio_content) < 100:
            raise HTTPException(status_code=400, detail="Audio file too small")
        
        # Convert audio to wav if needed
        try:
            from pydub import AudioSegment
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_content))
            wav_buffer = io.BytesIO()
            audio_segment.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
            audio_content = wav_buffer.read()
            
            # Get accurate duration
            if audio_duration <= 0:
                audio_duration = len(audio_segment) / 1000.0
        except ImportError:
            logger.warning("pydub not installed; using raw audio")
        except Exception as e:
            logger.warning(f"Audio conversion warning: {e}")
        
        # Run full analysis
        result = await SpeechService.full_speech_analysis(
            audio_content,
            language='en',
            audio_duration=audio_duration if audio_duration > 0 else None
        )
        
        # Store analysis result
        user_id = str(current_user.get("_id", current_user.get("user_id", "")))
        try:
            await speech_analyses_collection.insert_one({
                "user_id": user_id,
                "analysis": result,
                "created_at": datetime.now(timezone.utc)
            })
        except Exception:
            pass  # Non-critical
        
        logger.info(f"✅ Speech analysis complete: {result.get('total_words', 0)} words, {result.get('wpm', 0)} WPM")
        return {"success": True, **result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Speech analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/stage1/analyze-text-speech")
async def analyze_text_speech(
    request: SpeechAnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze speech from text transcript (when audio is already transcribed on frontend).
    Returns filler word detection and WPM analysis.
    """
    try:
        if not request.transcript:
            raise HTTPException(status_code=400, detail="Transcript is required")
        
        # Filler word analysis
        filler_data = SpeechService.detect_filler_words(request.transcript)
        
        # WPM analysis
        total_words = len(request.transcript.split())
        duration = request.audio_duration_seconds or 30.0  # Default to 30s if not provided
        pace_data = SpeechService.calculate_wpm(total_words, duration)
        
        # Clarity score
        filler_pct = filler_data.get("filler_percentage", 0)
        clarity = max(30, 100 - int(filler_pct * 3))
        
        # Overall fluency
        pace_score = 100 if pace_data["pace_rating"] == "good" else (
            80 if pace_data["pace_rating"] in ["slow", "fast"] else 50
        )
        filler_score = max(0, 100 - int(filler_pct * 5))
        overall = int(round(clarity * 0.4 + pace_score * 0.3 + filler_score * 0.3))
        
        return {
            "success": True,
            "transcript": request.transcript,
            "total_words": total_words,
            "audio_duration_seconds": round(duration, 2),
            **pace_data,
            **filler_data,
            "clarity_score": clarity,
            "overall_fluency_score": overall
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Text speech analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== SHADOWING ENDPOINTS ====================

@router.post("/api/stage1/shadow-practice")
async def shadow_practice(
    audio: UploadFile = File(None),
    reference_text: str = Form(...),
    user_text: str = Form(default=None),
    current_user: dict = Depends(get_current_user)
):
    """
    Shadowing practice: Compare user's speech against reference text.
    Uses Levenshtein distance for similarity scoring.
    Accepts either audio file or pre-transcribed text.
    """
    try:
        spoken_text = user_text
        
        # If audio provided, transcribe it
        if audio and not spoken_text:
            audio_content = await audio.read()
            if len(audio_content) > 100:
                # Convert if needed
                try:
                    from pydub import AudioSegment
                    audio_segment = AudioSegment.from_file(io.BytesIO(audio_content))
                    wav_buffer = io.BytesIO()
                    audio_segment.export(wav_buffer, format="wav")
                    wav_buffer.seek(0)
                    audio_content = wav_buffer.read()
                except:
                    pass
                
                stt_result = await SpeechService.speech_to_text_whisper(audio_content)
                spoken_text = stt_result.get("transcript", "")
        
        if not spoken_text:
            raise HTTPException(status_code=400, detail="No speech detected. Please speak clearly.")
        
        # Compare with reference
        result = SpeechService.analyze_shadowing(reference_text, spoken_text)
        
        # Store result
        user_id = str(current_user.get("_id", current_user.get("user_id", "")))
        try:
            await speech_analyses_collection.insert_one({
                "user_id": user_id,
                "type": "shadowing",
                "reference_text": reference_text,
                "user_text": spoken_text,
                "result": result,
                "created_at": datetime.now(timezone.utc)
            })
        except:
            pass
        
        logger.info(f"✅ Shadow practice: {result.get('overall_score', 0)}% match")
        return {
            "success": True,
            "user_text": spoken_text,
            **result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Shadow practice error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/stage1/shadow-practice-text")
async def shadow_practice_text(
    request: ShadowPracticeRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Shadowing practice from pre-transcribed text (no audio upload required).
    """
    try:
        if not request.user_text:
            raise HTTPException(status_code=400, detail="User text is required")
        
        result = SpeechService.analyze_shadowing(request.reference_text, request.user_text)
        
        return {
            "success": True,
            "user_text": request.user_text,
            **result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Shadow practice text error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== TONE ANALYSIS ENDPOINT ====================

@router.post("/api/stage1/analyze-tone")
async def analyze_tone(
    request: ToneAnalysisRequest,
    current_user: dict = Depends(get_current_user)
):
    """Analyze the tone and communication style of a text message."""
    try:
        prompt = TONE_ANALYSIS_PROMPT.format(message=request.text)
        
        response = await AIService.call_kimi(prompt, json_mode=True)
        
        try:
            if response:
                if isinstance(response, str):
                    json_match = re.search(r'\{.*\}', response, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group(0))
                    else:
                        raise ValueError("No JSON")
                else:
                    result = response
        except:
            result = {
                "tone": "neutral",
                "formality_level": "semi-formal",
                "confidence_level": 60,
                "politeness_score": 70,
                "clarity_score": 65,
                "assertiveness_score": 55,
                "suggestions": ["Try being more specific"],
                "improved_version": request.text
            }
        
        return {"success": True, **result}
        
    except Exception as e:
        logger.error(f"Tone analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== HELPER FUNCTIONS ====================

async def _quick_tone_check(message: str) -> Optional[Dict]:
    """Quick, non-blocking tone analysis for roleplay messages."""
    try:
        text_lower = message.lower()
        words = text_lower.split()
        
        # Simple heuristic tone analysis (no AI call - fast)
        confidence_indicators = ["i believe", "definitely", "certainly", "i'm sure", "clearly", "absolutely"]
        hesitation_indicators = ["i think", "maybe", "perhaps", "i guess", "not sure", "probably", "kind of"]
        polite_indicators = ["please", "thank you", "thanks", "appreciate", "would you", "could you"]
        
        confidence = 50
        politeness = 50
        
        for indicator in confidence_indicators:
            if indicator in text_lower:
                confidence += 10
        for indicator in hesitation_indicators:
            if indicator in text_lower:
                confidence -= 8
        for indicator in polite_indicators:
            if indicator in text_lower:
                politeness += 12
        
        confidence = max(10, min(100, confidence))
        politeness = max(10, min(100, politeness))
        
        if confidence >= 70:
            tone = "confident"
        elif confidence <= 35:
            tone = "hesitant"
        else:
            tone = "neutral"
        
        return {
            "tone": tone,
            "confidence_level": confidence,
            "politeness_score": politeness,
            "word_count": len(words)
        }
    except:
        return None
