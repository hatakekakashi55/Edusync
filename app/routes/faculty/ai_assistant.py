"""
EduSync Backend - Faculty - AI Routes
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

router = APIRouter(tags=["Faculty - AI"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/faculty/ai-command", tags=["Faculty - AI Assistant"])
async def process_faculty_ai_command(
    request: FacultyAICommand,
    current_user: dict = Depends(verify_token)
):
    """Process natural language commands from Faculty AI assistant with classroom management"""
    try:
        logger.info(f"🎯 Faculty AI Command received from user: {current_user.get('email')}")
        
        if current_user["user_type"] != UserType.FACULTY.value:
            logger.warning(f"❌ Access denied: User {current_user.get('email')} is not Faculty (type: {current_user.get('user_type')})")
            raise HTTPException(status_code=403, detail="Faculty access only")
        
        command = request.command.lower()
        department = current_user.get("department", "")
        user_name = current_user.get("full_name", "Professor")
        faculty_id = str(current_user.get("_id", ""))
        
        # Get Gemini model using helper function (uses feature-specific key with fallback to default)
        model = get_faculty_gemini_model("default")
        if model is None:
            logger.error("❌ Faculty AI: No Gemini model available (all API keys exhausted or invalid)")
            return {
                "response": "AI service temporarily unavailable. Please try again later.",
                "action": "dashboard",
                "summary": {"classrooms": 0, "department": department}
            }
        
        logger.info(f"✅ Faculty AI: Model loaded successfully - Using feature-specific API key with fallback support")
        
        # Get relevant data for context
        try:
            classrooms = await classrooms_collection.count_documents({
                "faculty_id": ObjectId(faculty_id)
            })
        except:
            classrooms = 0
        
        try:
            students_taught = await classrooms_collection.count_documents({
                "faculty_id": ObjectId(faculty_id),
                "students": {"$exists": True}
            })
        except:
            students_taught = 0
        
        # Build Faculty-specific system prompt
        system_prompt = f"""You are a professional and friendly Faculty AI Voice Assistant for EduSync.

YOUR ROLE:
You provide intelligent, concise, and professional assistance to Faculty with:
✓ Classroom management and student monitoring
✓ Assignment creation and grading
✓ Attendance tracking
✓ Student performance insights
✓ Course scheduling and planning
✓ Teaching resource management
✓ Student communication

SYSTEM INFORMATION:
- Faculty Name: {user_name}
- Department: {department}
- Active Classrooms: {classrooms}
- Students Under Instruction: {students_taught}

VOICE ASSISTANT GUIDELINES:
1. The "response" field is what will be SPOKEN OUT LOUD to the Faculty
2. Write the response as natural, conversational speech - NOT as robotic data reading
3. Never include JSON brackets, keys, or formatting symbols in the "response" text
4. When sharing classroom metrics, talk like a human colleague
5. Explain numbers naturally in 1-2 sentences, not as raw data dumps
6. Be professional, concise, and actionable
7. Suggest next steps when appropriate

RESPONSE FORMAT (INTERNAL USE ONLY):
{{
    "response": "Natural spoken language ONLY - what the voice will say",
    "action": "dashboard|assignments|grades|students|attendance|none",
    "summary": {{
        "key_stat": "value"
    }}
}}

EXAMPLE RESPONSES:

When asked about dashboard:
"Welcome back! You have 4 active classrooms with 128 students. All assignments are up to date, and attendance is looking good at 94%."

When asked about assignments:
"You have 3 pending assignments to review from your Data Structures class. The deadline was yesterday, so you might want to follow up with students."

When asked for greeting:
"Hello Professor! Ready to help you manage your classrooms and students."

IMPORTANT REMINDERS:
- Do NOT echo the user's input
- Do NOT say "I hear you" or "How can I assist"
- Speak naturally like a colleague, not a machine
- Include relevant metrics but explain them conversationally
- Keep responses to 1-3 sentences for voice clarity
"""
        
        # Analyze command with Gemini
        try:
            logger.info(f"Faculty AI: Using model for command: {command[:50]}...")
            full_prompt = f"{system_prompt}\n\nFaculty's Command: {command}\n\nRespond ONLY with valid JSON:"
            response = model.generate_content(full_prompt)
            response_text = response.text.strip()
            logger.info(f"Faculty AI Response: {response_text[:100]}...")
            
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
                        
                        logger.info(f"🎤 Faculty AI Voice Output: {result['response'][:80]}...")
                        
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
                    "response": "I'm ready to assist you with your classroom management. What do you need?",
                    "action": "none",
                    "summary": {}
                }
            
            logger.info(f"Faculty AI Command processed: {command[:50]}...")
            logger.debug(f"Returning response: {json.dumps(result)[:200]}")
            return result
            
        except Exception as e:
            logger.error(f"Gemini error in Faculty AI: {str(e)}", exc_info=True)
            # Fallback response
            return {
                "response": "I'm processing your request. Let me help you manage your classroom.",
                "action": "dashboard",
                "summary": {
                    "classrooms": classrooms,
                    "department": department
                }
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Faculty AI command error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process Faculty command")


