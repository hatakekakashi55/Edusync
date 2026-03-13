"""
EduSync Backend - WebSocket Manager
Auto-extracted from main.py
"""
import logging
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List
from bson import ObjectId

from fastapi import WebSocket

from app.database import *
from app.config import *
from app.services.ai_wrapper import gemini_model, get_gemini_model, AIModelWrapper

logger = logging.getLogger("edusync")

class WebSocketManager:
    _connections: Dict[str, WebSocket] = {}
    _user_connections: Dict[str, List[str]] = defaultdict(list)
    
    @classmethod
    async def connect(cls, websocket: WebSocket, connection_id: str, user_id: str):
        await websocket.accept()
        cls._connections[connection_id] = websocket
        cls._user_connections[user_id].append(connection_id)
        
        # Send connection established message
        await websocket.send_json({
            "type": "connection_established",
            "connection_id": connection_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    @classmethod
    def disconnect(cls, connection_id: str, user_id: str):
        if connection_id in cls._connections:
            del cls._connections[connection_id]
        
        if user_id in cls._user_connections and connection_id in cls._user_connections[user_id]:
            cls._user_connections[user_id].remove(connection_id)
            if not cls._user_connections[user_id]:
                del cls._user_connections[user_id]
    
    @classmethod
    async def send_to_user(cls, user_id: str, message: Dict):
        if user_id in cls._user_connections:
            for connection_id in cls._user_connections[user_id]:
                if connection_id in cls._connections:
                    try:
                        await cls._connections[connection_id].send_json(message)
                    except Exception as e:
                        logger.error(f"WebSocket send error: {e}")
                        cls.disconnect(connection_id, user_id)
    
    @classmethod
    async def send_to_connection(cls, connection_id: str, message: Dict):
        if connection_id in cls._connections:
            try:
                await cls._connections[connection_id].send_json(message)
            except Exception as e:
                logger.error(f"WebSocket send error: {e}")
                # Find and remove this connection
                for uid, conns in cls._user_connections.items():
                    if connection_id in conns:
                        cls.disconnect(connection_id, uid)
                        break
    
    @classmethod
    async def broadcast(cls, message: Dict):
        disconnected = []
        for connection_id, websocket in cls._connections.items():
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"WebSocket broadcast error: {e}")
                disconnected.append(connection_id)
        
        # Clean up disconnected websockets
        for connection_id in disconnected:
            for uid, conns in cls._user_connections.items():
                if connection_id in conns:
                    cls.disconnect(connection_id, uid)
                    break
    
    @classmethod
    async def broadcast_to_group(cls, group_id: str, message: Dict, exclude_user: str = None):
        # Get group members
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
        if group:
            for member_id in group.get("members", []):
                if member_id != exclude_user:
                    await cls.send_to_user(member_id, message)

