"""
EduSync Backend - HOD - AI Routes
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

router = APIRouter(tags=["HOD - AI"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/hod/ai-command", tags=["HOD - AI Assistant"])
async def process_hod_ai_command(
    request: HODAICommand,
    current_user: dict = Depends(verify_token)
):
    """Process natural language commands from HOD AI assistant with full dashboard access"""
    try:
        logger.info(f"🎯 HOD AI Command received from user: {current_user.get('email')}")
        
        if current_user["user_type"] != UserType.HOD.value:
            logger.warning(f"❌ Access denied: User {current_user.get('email')} is not HOD (type: {current_user.get('user_type')})")
            raise HTTPException(status_code=403, detail="HOD access only")
        
        command = request.command.lower()
        department = current_user.get("department", "")
        user_name = current_user.get("full_name", "HOD")
        
        # Get Gemini model (use default key for HOD assistant)
        model = get_gemini_model("default")
        if model is None:
            logger.error("HOD AI: Model is None for 'default' feature type")
            return {
                "response": "AI service temporarily unavailable.",
                "action": "dashboard",
                "summary": {"pending_approvals": 0, "department": department}
            }
        
        logger.info(f"HOD AI: Model loaded successfully - {type(model)}")
        
        # Get relevant data for context
        try:
            pending_approvals = await hod_approvals_collection.count_documents({
                "department": department,
                "status": "pending"
            })
        except:
            pending_approvals = 0
        
        # Build HOD-specific system prompt with better instructions
        system_prompt = f"""You are a professional and friendly HOD AI Voice Assistant for EduSync.

YOUR ROLE:
You provide intelligent, concise, and professional assistance to the HOD with:
✓ Dashboard analytics and statistics
✓ Student and faculty approvals
✓ Course and curriculum management
✓ Resource allocation and tracking
✓ Department performance insights
✓ Administrative decisions

SYSTEM INFORMATION:
- HOD Name: {user_name}
- Department: {department}
- Pending Approvals: {pending_approvals}

VOICE ASSISTANT GUIDELINES:
1. The "response" field is what will be SPOKEN OUT LOUD to the HOD
2. Write the response as natural, conversational speech - NOT as robotic data reading
3. Never include JSON brackets, keys, or formatting symbols in the "response" text
4. When sharing dashboard metrics, talk like a human colleague
5. Explain numbers naturally in 1-2 sentences, not as raw data dumps
6. Be professional, concise, and actionable
7. Suggest next steps when appropriate

RESPONSE FORMAT (INTERNAL USE ONLY):
{{
    "response": "Natural spoken language ONLY - what the voice will say",
    "action": "dashboard|approvals|reports|analytics|none",
    "summary": {{
        "key_stat": "value"
    }}
}}

EXAMPLE RESPONSES:

When asked about dashboard:
"Welcome back! Your IT department is running smoothly with 583 active students and an 82.5% performance rating. No pending approvals at the moment."

When asked about approvals:
"You have 12 pending approvals in queue. The latest one is from Priya Kumar requesting course curriculum changes."

When asked for greeting:
"Hello! Ready to assist with your department operations."

IMPORTANT REMINDERS:
- Do NOT echo the user's input
- Do NOT say "I hear you" or "How can I assist"
- Speak naturally like a colleague, not a machine
- Include relevant metrics but explain them conversationally
- Keep responses to 1-3 sentences for voice clarity
"""
        
        # Analyze command with Gemini
        try:
            logger.info(f"HOD AI: Using model for command: {command[:50]}...")
            full_prompt = f"{system_prompt}\n\nHOD's Command: {command}\n\nRespond ONLY with valid JSON:"
            response = model.generate_content(full_prompt)
            response_text = response.text.strip()
            logger.info(f"HOD AI Response: {response_text[:100]}...")
            
            # Parse JSON response from Gemini
            result = None
            
            if response_text.startswith('{'):
                try:
                    result = json.loads(response_text)
                    logger.info(f"✅ JSON parsed successfully")
                    
                    # Validate and clean the response field
                    if "response" not in result or not result.get("response"):
                        logger.warning("⚠️ JSON missing 'response' field, using full text")
                        result = {
                            "response": response_text,
                            "action": result.get("action", "none"),
                            "summary": result.get("summary", {})
                        }
                    else:
                        # Clean up the response field
                        result["response"] = result["response"].strip()
                        # Ensure action field exists
                        if "action" not in result:
                            result["action"] = "none"
                        if "summary" not in result:
                            result["summary"] = {}
                        
                        logger.info(f"🎤 HOD AI Voice Output: {result['response'][:80]}...")
                        
                except json.JSONDecodeError as parse_error:
                    logger.warning(f"❌ JSON parse error: {parse_error}")
                    logger.warning(f"Attempted to parse: {response_text[:200]}")
                    result = {
                        "response": response_text,
                        "action": "none",
                        "summary": {}
                    }
            else:
                # Response is not JSON, treat as plain text
                logger.warning(f"⚠️ Response not JSON format, treating as plain text")
                result = {
                    "response": response_text,
                    "action": "none",
                    "summary": {}
                }
            
            # Final validation before returning
            if result is None:
                logger.error("❌ Result is None, returning fallback")
                result = {
                    "response": "I'm ready to assist you. What do you need?",
                    "action": "none",
                    "summary": {}
                }
            
            logger.info(f"HOD AI Command processed: {command[:50]}...")
            logger.debug(f"Returning response: {json.dumps(result)[:200]}")
            return result
            
        except Exception as e:
            logger.error(f"Gemini error in HOD AI: {str(e)}", exc_info=True)
            # Fallback response
            return {
                "response": "I'm processing your request. Let me help you navigate the dashboard.",
                "action": "dashboard",
                "summary": {
                    "pending_approvals": pending_approvals,
                    "department": department
                }
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HOD AI command error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process HOD command")


@router.get("/api/hod/ai/status", tags=["HOD - AI Assistant"])
async def get_hod_ai_status(current_user: dict = Depends(get_current_user)):
    """Check HOD AI Assistant configuration status"""
    try:
        return {
            "status": "operational" if hod_gemini_model else "not_configured",
            "api_keys_configured": {
                "gemini": bool(HOD_API_KEYS.get("gemini")),
                "openai": bool(HOD_API_KEYS.get("openai")),
                "speech": bool(HOD_API_KEYS.get("speech")),
                "custom": bool(HOD_API_KEYS.get("custom")),
            },
            "model_available": hod_gemini_model is not None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        logger.error(f"Error checking HOD AI status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/hod/ai/configure-api-keys", tags=["HOD - AI Assistant"])
async def configure_hod_api_keys(
    api_keys: Dict[str, str] = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """Configure HOD AI Assistant API keys (only for HOD users)"""
    try:
        # Verify user is HOD
        if current_user.get("user_type") != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="Only HOD can configure API keys")
        
        # Update API keys in memory (for this session)
        updated_keys = {}
        for key_type in ["gemini", "openai", "speech", "custom"]:
            if key_type in api_keys and api_keys[key_type]:
                HOD_API_KEYS[key_type] = api_keys[key_type]
                updated_keys[key_type] = "configured"
                
                # If Gemini key was updated, reinitialize the model
                if key_type == "gemini":
                    global hod_gemini_model
                    try:
                        hod_genai_client = genai.Client(api_key=api_keys[key_type])
                        # Try to initialize with first available model
                        for model_name in ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-1.5-pro']:
                            try:
                                hod_genai_client.models.get(name=model_name)
                                hod_gemini_model = {"client": hod_genai_client, "model": model_name}
                                logger.info(f"✅ HOD Gemini AI reconfigured with {model_name}")
                                break
                            except:
                                continue
                    except Exception as e:
                        logger.error(f"Failed to reconfigure HOD Gemini: {e}")
            else:
                updated_keys[key_type] = "not_provided"
        
        return {
            "success": True,
            "message": "HOD API keys configured successfully",
            "updated_keys": updated_keys,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error configuring HOD API keys: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/hod/ai/gemini-api-keys", tags=["HOD - AI Assistant"])
async def get_hod_gemini_api_keys(current_user: dict = Depends(get_current_user)):
    """Get available Gemini API key types for HOD assistant"""
    try:
        # Verify user is HOD
        if current_user.get("user_type") != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="Only HOD can access this endpoint")
        
        return {
            "available_api_types": {
                "gemini": "Google Gemini API - for AI text generation",
                "openai": "OpenAI API - for advanced analysis",
                "speech": "Speech API - for voice recognition",
                "custom": "Custom API - for additional integrations"
            },
            "gemini_models": [
                "gemini-2.5-flash",
                "gemini-1.5-flash",
                "gemini-1.5-pro"
            ],
            "current_status": {
                "model_active": hod_gemini_model is not None,
                "keys_count": sum(1 for k, v in HOD_API_KEYS.items() if v)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving API key info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


