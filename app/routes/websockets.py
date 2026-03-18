"""
EduSync Backend - WebSocket Routes
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
import jwt
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict, Any
from pathlib import Path
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query, Body, BackgroundTasks, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, Response

from app.dependencies import get_current_user, verify_token, convert_objectid_to_str, create_access_token, create_refresh_token
from app.database import *
from app.services.ai_wrapper import gemini_model, get_gemini_model, get_faculty_gemini_model, hod_gemini_model, faculty_gemini_models, AIModelWrapper
from app.services.ai_service import AIService
from app.services.websocket_manager import WebSocketManager
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
from app.services.websocket_manager import WebSocketManager

logger = logging.getLogger("edusync")

router = APIRouter(tags=["WebSocket"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.websocket("/api/ws/{connection_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    connection_id: str,
    token: str = Query(...)
):
    """WebSocket endpoint for real-time communication"""
    try:
        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        if not user_id:
            await websocket.close(code=1008)
            return
        
        # Connect
        await WebSocketManager.connect(websocket, connection_id, user_id)
        
        try:
            while True:
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                message_type = message_data.get("type")
                
                if message_type == "ping":
                    # Respond to ping
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
                elif message_type == "group_message":
                    # Handle group message
                    group_id = message_data["group_id"]
                    content = message_data["content"]
                    message_type = message_data.get("message_type", "text")
                    
                    # Save message to database
                    message = {
                        "sender_id": user_id,
                        "sender_name": payload.get("full_name", "User"),
                        "content": content,
                        "message_type": message_type,
                        "timestamp": datetime.now(timezone.utc),
                        "read_by": [user_id]
                    }
                    
                    # Check for AI assistant
                    group = await groups_collection.find_one({"_id": ObjectId(group_id)})
                    if group and content.startswith("@assistant") and group.get("ai_assistant_enabled", False):
                        question = content.replace("@assistant", "").strip()
                        context = f"Group: {group['name']}, User: {payload.get('full_name')}"
                        ai_response = await AIService.chat_assistant(question, {"context": context})
                        
                        # Send AI response
                        ai_message = {
                            "sender_id": "ai_assistant",
                            "sender_name": "AI Assistant",
                            "content": ai_response,
                            "message_type": "ai",
                            "timestamp": datetime.now(timezone.utc)
                        }
                        
                        await groups_collection.update_one(
                            {"_id": ObjectId(group_id)},
                            {"$push": {"messages": {"$each": [message, ai_message]}}}
                        )
                        
                        # Broadcast both messages
                        await WebSocketManager.broadcast_to_group(
                            group_id,
                            {
                                "type": "new_message",
                                "message_id": str(uuid.uuid4()),
                                "group_id": group_id,
                                "sender_id": user_id,
                                "sender_name": payload.get("full_name", "User"),
                                "content": content,
                                "message_type": message_type,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            },
                            user_id
                        )
                        
                        await WebSocketManager.broadcast_to_group(
                            group_id,
                            {
                                "type": "new_message",
                                "message_id": str(uuid.uuid4()),
                                "group_id": group_id,
                                "sender_id": "ai_assistant",
                                "sender_name": "AI Assistant",
                                "content": ai_response,
                                "message_type": "ai",
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                        )
                    else:
                        result = await messages_collection.insert_one(message)
                        message_id = str(result.inserted_id)
                        
                        # Broadcast to group
                        await WebSocketManager.broadcast_to_group(
                            group_id,
                            {
                                "type": "new_message",
                                "message_id": message_id,
                                "group_id": group_id,
                                "sender_id": user_id,
                                "sender_name": payload.get("full_name", "User"),
                                "content": content,
                                "message_type": message_type,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            },
                            user_id
                        )
                    
                elif message_type == "typing":
                    # Handle typing indicator
                    group_id = message_data.get("group_id")
                    if group_id:
                        await WebSocketManager.broadcast_to_group(
                            group_id,
                            {
                                "type": "user_typing",
                                "user_id": user_id,
                                "user_name": payload.get("full_name", "User"),
                                "group_id": group_id
                            },
                            user_id
                        )
                
                elif message_type == "pair_programming":
                    # Handle pair programming updates
                    session_id = message_data.get("session_id")
                    code = message_data.get("code")
                    cursor_position = message_data.get("cursor_position")
                    
                    if session_id and code is not None:
                        # Update session code
                        await pair_programming_collection.update_one(
                            {"session_id": session_id},
                            {"$set": {
                                "code": code,
                                f"cursor_positions.{user_id}": cursor_position,
                                "updated_at": datetime.now(timezone.utc)
                            }}
                        )
                        
                        # Broadcast to other participant
                        session = await pair_programming_collection.find_one({"session_id": session_id})
                        if session:
                            other_user = session["user2_id"] if session["user1_id"] == user_id else session["user1_id"]
                            await WebSocketManager.send_to_user(other_user, {
                                "type": "pair_programming_update",
                                "session_id": session_id,
                                "code": code,
                                "cursor_position": cursor_position,
                                "user_id": user_id,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
                        
        except WebSocketDisconnect:
            WebSocketManager.disconnect(connection_id, user_id)
            
    except jwt.PyJWTError:
        await websocket.close(code=1008)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011)
        except:
            pass


@router.websocket("/ws/challenges")
async def websocket_challenges(websocket: WebSocket, token: str = Query(...)):
    """WebSocket endpoint for real-time challenge updates"""
    try:
        # Verify token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        if not user_id:
            await websocket.close(code=1008)
            return
        
        connection_id = f"challenge_{user_id}_{datetime.now(timezone.utc).timestamp()}"
        
        # Connect to WebSocket manager
        await WebSocketManager.connect(websocket, connection_id, user_id)
        
        try:
            while True:
                # Keep connection alive
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                msg_type = message_data.get("type")
                
                if msg_type == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                elif msg_type == "subscribe_to_stage":
                    stage = message_data.get("stage")
                    # Send existing challenges for the stage
                    challenges = await challenges_collection.find(
                        {"stage": stage, "status": "active"}
                    ).to_list(length=100)
                    
                    await websocket.send_json({
                        "type": "challenges_list",
                        "stage": stage,
                        "challenges": [
                            {
                                "id": str(c["_id"]),
                                "title": c.get("title"),
                                "description": c.get("description"),
                                "difficulty": c.get("difficulty"),
                                "credits_reward": c.get("credits_reward"),
                                "challenge_type": c.get("challenge_type")
                            }
                            for c in challenges
                        ]
                    })
        
        except WebSocketDisconnect:
            WebSocketManager.disconnect(connection_id, user_id)
        except Exception as e:
            logger.error(f"WebSocket challenge error: {e}")
            WebSocketManager.disconnect(connection_id, user_id)
    
    except Exception as e:
        logger.error(f"WebSocket challenge connection error: {e}")
        await websocket.close(code=1011)


@router.websocket("/ws/projects/{project_id}")
async def websocket_project_collaboration(websocket: WebSocket, project_id: str, token: str = Query(...)):
    """WebSocket endpoint for real-time project collaboration"""
    try:
        # Verify token and get user
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("sub")
            if not user_id:
                await websocket.close(code=1008, reason="Invalid token")
                return
        except jwt.ExpiredSignatureError:
            await websocket.close(code=1008, reason="Token expired")
            return
        except jwt.InvalidTokenError:
            await websocket.close(code=1008, reason="Invalid token")
            return
        
        # Get user details
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            await websocket.close(code=1008, reason="User not found")
            return
        
        # Verify project access - support both field names
        project = await projects_collection.find_one({"_id": ObjectId(project_id)})
        if not project:
            await websocket.close(code=1008, reason="Project not found")
            return
        
        members = project.get("members", project.get("team_members", []))
        owner = str(project.get("created_by", project.get("owner_id", "")))
        
        if user_id not in members and owner != user_id:
            await websocket.close(code=1008, reason="Not authorized")
            return
        
        # Connect user
        await WebSocketManager.connect(websocket, project_id, user_id)
        
        # Notify others that user joined
        await WebSocketManager.broadcast_to_project(
            project_id,
            {
                "type": "user_joined",
                "user_id": user_id,
                "user_name": user.get("full_name", "Unknown"),
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            exclude_user=user_id
        )
        
        try:
            while True:
                # Receive messages from client
                data = await websocket.receive_json()
                
                # Handle different message types
                message_type = data.get("type")
                
                if message_type == "cursor_position":
                    # Broadcast cursor position to other users
                    await WebSocketManager.broadcast_to_project(
                        project_id,
                        {
                            "type": "cursor_update",
                            "user_id": user_id,
                            "user_name": user.get("full_name", "Unknown"),
                            "file_id": data.get("file_id"),
                            "line": data.get("line"),
                            "column": data.get("column")
                        },
                        exclude_user=user_id
                    )
                
                elif message_type == "code_change":
                    # Broadcast code changes in real-time
                    await WebSocketManager.broadcast_to_project(
                        project_id,
                        {
                            "type": "code_update",
                            "user_id": user_id,
                            "user_name": user.get("full_name", "Unknown"),
                            "file_id": data.get("file_id"),
                            "changes": data.get("changes"),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        },
                        exclude_user=user_id
                    )
                
                elif message_type == "chat_message":
                    # Broadcast chat message to team
                    await WebSocketManager.broadcast_to_project(
                        project_id,
                        {
                            "type": "team_chat",
                            "user_id": user_id,
                            "user_name": user.get("full_name", "Unknown"),
                            "message": data.get("message"),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    )
                
        except WebSocketDisconnect:
            WebSocketManager.disconnect(websocket, project_id, user_id)
            # Notify others that user left
            await WebSocketManager.broadcast_to_project(
                project_id,
                {
                    "type": "user_left",
                    "user_id": user_id,
                    "user_name": user.get("full_name", "Unknown"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011)
        except:
            pass


@router.websocket("/api/ws/stage3")
async def websocket_stage3_ai_assistant(websocket: WebSocket):
    """WebSocket for Stage 3 AI Assistant with real-time typing animation"""
    await websocket.accept()
    user_id = None
    
    try:
        token = websocket.query_params.get("token")
        if not token:
            await websocket.send_json({"type": "error", "message": "Authentication required"})
            await websocket.close()
            return
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("email")
            user = await users_collection.find_one({"email": email})
            if not user:
                raise Exception("User not found")
        except Exception as e:
            await websocket.send_json({"type": "error", "message": "Invalid authentication"})
            await websocket.close()
            return
        
        user_id = str(user["_id"])
        logger.info(f"✅ Stage 3 AI Assistant connected: {user_id}")
        
        await websocket.send_json({
            "type": "connected",
            "message": "AI Assistant connected! Ask me anything about your project.",
            "user_id": user_id
        })
        
        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            
            if message_type == "chat":
                message = data.get("message", "").strip()
                
                if not message:
                    await websocket.send_json({"type": "error", "message": "Please type a message"})
                    continue
                
                await websocket.send_json({"type": "typing", "message": "AI is thinking..."})
                
                try:
                    model = get_gemini_model("default")
                    if not model:
                        await websocket.send_json({"type": "error", "message": "AI service unavailable"})
                        continue
                    
                    prompt = f"""You are an intelligent AI assistant helping students with projects and coding.
Be helpful, detailed, and encouraging.

User: {message}

Provide a comprehensive response:"""
                    
                    response = await model.generate_content_async(prompt)
                    
                    if not response or not response.text:
                        await websocket.send_json({"type": "error", "message": "AI generated empty response"})
                        continue
                    
                    full_text = response.text
                    
                    await websocket.send_json({"type": "response_start", "total_length": len(full_text)})
                    
                    # Stream character by character (Claude-like typing)
                    for i, char in enumerate(full_text):
                        await websocket.send_json({"type": "token", "token": char, "index": i})
                        await asyncio.sleep(0.02)
                    
                    await websocket.send_json({
                        "type": "response_complete",
                        "full_text": full_text,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
                    await ai_chats_collection.insert_one({
                        "user_id": user_id,
                        "message": message,
                        "response": full_text,
                        "context": "stage3_assistant",
                        "timestamp": datetime.now(timezone.utc)
                    })
                    
                except Exception as e:
                    logger.error(f"AI Assistant Error: {e}")
                    await websocket.send_json({"type": "error", "message": f"AI error: {str(e)}"})
            
    except WebSocketDisconnect:
        logger.info(f"✅ Stage 3 AI disconnected: {user_id}")
    except Exception as e:
        logger.error(f"❌ WebSocket Error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close()
        except:
            pass


@router.websocket("/api/ws/stage1/roleplay")
async def websocket_stage1_roleplay(websocket: WebSocket):
    """
    WebSocket for Stage 1 Roleplay - Real-time AI conversation with streaming responses.
    Also pushes evaluation results and speech analysis in real-time.
    """
    await websocket.accept()
    user_id = None
    
    try:
        token = websocket.query_params.get("token")
        if not token:
            await websocket.send_json({"type": "error", "message": "Authentication required"})
            await websocket.close()
            return
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("email")
            user = await users_collection.find_one({"email": email})
            if not user:
                raise Exception("User not found")
        except Exception as e:
            await websocket.send_json({"type": "error", "message": "Invalid authentication"})
            await websocket.close()
            return
        
        user_id = str(user["_id"])
        logger.info(f"✅ Stage 1 Roleplay WebSocket connected: {user_id}")
        
        await websocket.send_json({
            "type": "connected",
            "message": "Roleplay WebSocket connected!",
            "user_id": user_id
        })
        
        # Import here to avoid circular imports
        from app.services.ai_service import AIService
        from app.services.prompts import get_scenario, ROLEPLAY_SCENARIOS
        from app.services.speech_service import SpeechService
        
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            
            elif msg_type == "roleplay_message":
                # Handle roleplay message with streaming response
                session_id = data.get("session_id")
                message = data.get("message", "").strip()
                
                if not session_id or not message:
                    await websocket.send_json({"type": "error", "message": "session_id and message required"})
                    continue
                
                # Find session
                from app.database import roleplay_sessions_collection
                session = await roleplay_sessions_collection.find_one({
                    "session_id": session_id,
                    "user_id": user_id,
                    "status": "active"
                })
                
                if not session:
                    await websocket.send_json({"type": "error", "message": "Session not found"})
                    continue
                
                await websocket.send_json({"type": "typing", "message": "AI is responding..."})
                
                try:
                    # Build conversation context
                    conversation_text = ""
                    for msg in session.get("messages", []):
                        role = "Character" if msg["role"] == "assistant" else "Student"
                        conversation_text += f"{role}: {msg['content']}\n\n"
                    
                    full_prompt = f"""{session['system_prompt']}

Continue this roleplay conversation. Stay in character. 2-3 sentences only.

{conversation_text}
Student: {message}

Your response (stay in character):"""
                    
                    response = await AIService.call_ollama(full_prompt, session["system_prompt"])
                    ai_reply = response.strip() if response else "Could you elaborate on that?"
                    
                    # Clean
                    import re
                    ai_reply = re.sub(r'^(assistant|character|ai|response):\s*', '', ai_reply, flags=re.IGNORECASE)
                    ai_reply = ai_reply.strip('"').strip("'").strip()
                    
                    # Stream response token by token
                    await websocket.send_json({"type": "response_start", "total_length": len(ai_reply)})
                    
                    for i, char in enumerate(ai_reply):
                        await websocket.send_json({"type": "token", "token": char, "index": i})
                        await asyncio.sleep(0.015)  # Slightly faster than Stage 3
                    
                    new_turn = session["current_turn"] + 1
                    
                    # Save messages
                    user_msg = {"role": "user", "content": message, "timestamp": datetime.now(timezone.utc).isoformat()}
                    ai_msg = {"role": "assistant", "content": ai_reply, "timestamp": datetime.now(timezone.utc).isoformat()}
                    
                    await roleplay_sessions_collection.update_one(
                        {"session_id": session_id},
                        {
                            "$push": {"messages": {"$each": [user_msg, ai_msg]}},
                            "$set": {"current_turn": new_turn}
                        }
                    )
                    
                    await websocket.send_json({
                        "type": "response_complete",
                        "full_text": ai_reply,
                        "current_turn": new_turn,
                        "max_turns": session["max_turns"],
                        "turns_remaining": session["max_turns"] - new_turn,
                        "should_end": new_turn >= session["max_turns"],
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
                except Exception as e:
                    logger.error(f"Roleplay WS AI error: {e}")
                    await websocket.send_json({
                        "type": "response_complete",
                        "full_text": "That's an interesting point. Could you tell me more?",
                        "error": str(e)
                    })
            
            elif msg_type == "speech_analysis":
                # Handle real-time speech analysis results push
                transcript = data.get("transcript", "")
                duration = data.get("duration", 30.0)
                
                if transcript:
                    filler_data = SpeechService.detect_filler_words(transcript)
                    pace_data = SpeechService.calculate_wpm(len(transcript.split()), duration)
                    
                    await websocket.send_json({
                        "type": "speech_analysis_result",
                        "transcript": transcript,
                        **filler_data,
                        **pace_data,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
    
    except WebSocketDisconnect:
        logger.info(f"✅ Stage 1 Roleplay WS disconnected: {user_id}")
    except Exception as e:
        logger.error(f"❌ Roleplay WebSocket Error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close()
        except:
            pass
