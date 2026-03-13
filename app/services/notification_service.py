"""
EduSync Backend - Notification Service
Auto-extracted from main.py
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from bson import ObjectId

from app.database import *
from app.config import *

logger = logging.getLogger("edusync")


# Lazy imports to avoid circular dependency
def _get_websocket_manager():
    from app.services.websocket_manager import WebSocketManager
    return WebSocketManager


async def _send_email(to_email, subject, body):
    """Wrapper that lazily imports send_email_async to avoid circular imports"""
    try:
        from app.utils.helpers import send_email_async
        await send_email_async(to_email, subject, body)
    except Exception as e:
        logger.error(f"Email send error: {e}")

class NotificationService:
    @staticmethod
    async def create_notification(user_id: str, title: str, message: str, 
                                 notification_type: str = "info", priority: str = "normal",
                                 action_url: str = None, data: Dict = None):
        try:
            notification = {
                "user_id": user_id,
                "title": title,
                "message": message,
                "type": notification_type,
                "priority": priority,
                "action_url": action_url,
                "data": data or {},
                "read": False,
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(days=30)
            }
            
            await notifications_collection.insert_one(notification)
            
            # Send real-time notification via WebSocket if user is connected
            try:
                WSManager = _get_websocket_manager()
                await WSManager.send_to_user(user_id, {
                    "type": "notification",
                    "notification": notification
                })
            except Exception as ws_err:
                logger.debug(f"WebSocket notification failed: {ws_err}")
            
            # Send email for high priority notifications
            if priority == "high":
                user = await users_collection.find_one({"_id": ObjectId(user_id)})
                if user and user.get("email"):
                    await _send_email(
                        user["email"],
                        f"Urgent: {title}",
                        f"{message}\n\nAction URL: {action_url or 'No action required'}"
                    )
            
            return notification
        except Exception as e:
            logger.error(f"Create notification error: {e}")
    
    @staticmethod
    async def create_broadcast(title: str, message: str, target_users: List[str] = None,
                              filters: Dict = None, notification_type: str = "announcement"):
        try:
            notification = {
                "broadcast": True,
                "title": title,
                "message": message,
                "type": notification_type,
                "target_users": target_users,
                "filters": filters,
                "created_at": datetime.now(timezone.utc)
            }
            
            await notifications_collection.insert_one(notification)
            
            # Send to all connected users
            try:
                WSManager = _get_websocket_manager()
                await WSManager.broadcast({
                    "type": "broadcast",
                    "notification": notification
                })
            except Exception as ws_err:
                logger.debug(f"WebSocket broadcast failed: {ws_err}")
            
            return notification
        except Exception as e:
            logger.error(f"Create broadcast error: {e}")

