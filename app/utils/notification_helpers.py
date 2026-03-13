"""
EduSync Backend - Notification Helpers
Auto-extracted from main.py
"""
import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.database import *
from app.config import *
from app.models.auth import UserType

logger = logging.getLogger("edusync")


async def get_pending_by_type_counts(department: str):
    """Get counts of pending approvals by type"""
    pipeline = [
        {"$match": {
            "department": department,
            "status": ApprovalStatus.PENDING.value
        }},
        {"$group": {
            "_id": "$approval_type",
            "count": {"$sum": 1},
            "urgent": {"$sum": {"$cond": [{"$eq": ["$priority", "urgent"]}, 1, 0]}},
            "high": {"$sum": {"$cond": [{"$eq": ["$priority", "high"]}, 1, 0]}}
        }}
    ]
    
    result = list(await approvals_collection.aggregate(pipeline).to_list(10))
    return {item["_id"]: item for item in result}

async def create_approval_request_internal(approval_data: dict, current_user: dict):
    """Internal function to create approval request"""
    approval = {
        **approval_data,
        "requested_by_email": current_user["email"],
        "requested_by_role": current_user["user_type"],
        "status": ApprovalStatus.PENDING.value,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "history": [{
            "action": "created",
            "by": approval_data["requested_by"],
            "by_name": approval_data["requested_by_name"],
            "timestamp": datetime.now(timezone.utc),
            "notes": "Request submitted"
        }]
    }
    
    result = await approvals_collection.insert_one(approval)
    approval_id = str(result.inserted_id)
    
    return {"approval_id": approval_id, "approval": approval}

async def execute_approved_action(approval: dict, current_user: dict):
    """Execute action after approval"""
    try:
        approval_type = approval["approval_type"]
        
        if approval_type == ApprovalType.FACULTY_COMMUNITY.value:
            # Create faculty community
            community_data = approval.get("metadata", {}).get("community_data", {})
            if community_data:
                # Add HOD to members
                members = community_data.get("members", [])
                members.append(str(current_user["_id"]))
                
                community = {
                    "name": community_data["community_name"],
                    "description": community_data["description"],
                    "type": community_data["community_type"],
                    "privacy": community_data["privacy"],
                    "members": members,
                    "created_by": approval["requested_by"],
                    "created_by_name": approval["requested_by_name"],
                    "created_at": datetime.now(timezone.utc),
                    "approved_by": str(current_user["_id"]),
                    "approved_at": datetime.now(timezone.utc),
                    "approval_id": str(approval["_id"]),
                    "status": "active",
                    "duration_days": community_data.get("duration_days", 30)
                }
                
                await faculty_communities_collection.insert_one(community)
                
                # Notify all members
                for member_id in members:
                    await NotificationService.create_notification(
                        user_id=member_id,
                        title=f"New Community: {community_data['community_name']}",
                        message=f"You've been added to {community_data['community_type']} community '{community_data['community_name']}'",
                        notification_type="community",
                        action_url=f"/communities/{str(community['_id'])}"
                    )
        
        elif approval_type == ApprovalType.FACULTY_LEAVE.value:
            # Update faculty leave status
            leave_data = approval.get("metadata", {}).get("leave_data", {})
            
            # Create leave record
            leave_record = {
                "faculty_id": approval["requested_by"],
                "faculty_name": approval["requested_by_name"],
                "leave_type": leave_data.get("leave_type"),
                "start_date": leave_data.get("start_date"),
                "end_date": leave_data.get("end_date"),
                "reason": leave_data.get("reason"),
                "status": "approved",
                "approved_by": str(current_user["_id"]),
                "approved_at": datetime.now(timezone.utc),
                "approval_id": str(approval["_id"])
            }
            
            await db.faculty_leaves.insert_one(leave_record)
            
            # Update faculty status
            await users_collection.update_one(
                {"_id": ObjectId(approval["requested_by"])},
                {"$set": {"status": "on_leave", "leave_start": leave_data.get("start_date"), "leave_end": leave_data.get("end_date")}}
            )
        
        elif approval_type == ApprovalType.RESOURCE_REQUEST.value:
            # Process resource request
            resource_data = approval.get("metadata", {}).get("resource_data", {})
            
            # Create resource allocation record
            resource_record = {
                "item_name": resource_data.get("item_name"),
                "resource_type": resource_data.get("resource_type"),
                "quantity": resource_data.get("quantity"),
                "requested_by": approval["requested_by"],
                "requested_by_name": approval["requested_by_name"],
                "purpose": resource_data.get("purpose"),
                "status": "allocated",
                "approved_by": str(current_user["_id"]),
                "approved_at": datetime.now(timezone.utc),
                "approval_id": str(approval["_id"]),
                "estimated_cost": resource_data.get("estimated_cost")
            }
            
            await db.resource_allocations.insert_one(resource_record)
            
        logger.info(f"Executed approved action for {approval_type}")
        
    except Exception as e:
        logger.error(f"Execute approved action error: {e}")

async def get_approval_statistics(hod_id: str, period: str = "month"):
    """Get approval statistics"""
    try:
        # Calculate date range based on period
        now = datetime.now(timezone.utc)
        if period == "day":
            start_date = now - timedelta(days=1)
        elif period == "week":
            start_date = now - timedelta(days=7)
        elif period == "month":
            start_date = now - timedelta(days=30)
        elif period == "quarter":
            start_date = now - timedelta(days=90)
        else:  # year
            start_date = now - timedelta(days=365)
        
        # Get counts
        pipeline = [
            {"$match": {
                "approvers": hod_id,
                "created_at": {"$gte": start_date}
            }},
            {"$facet": {
                "total": [{"$count": "count"}],
                "by_status": [{"$group": {"_id": "$status", "count": {"$sum": 1}}}],
                "by_type": [{"$group": {"_id": "$approval_type", "count": {"$sum": 1}}}],
                "by_priority": [{"$group": {"_id": "$priority", "count": {"$sum": 1}}}],
                "pending_urgent": [
                    {"$match": {"status": "pending", "priority": "urgent"}},
                    {"$count": "count"}
                ],
                "pending_high": [
                    {"$match": {"status": "pending", "priority": "high"}},
                    {"$count": "count"}
                ],
                "recent_actions": [
                    {"$match": {"status": {"$ne": "pending"}}},
                    {"$sort": {"updated_at": -1}},
                    {"$limit": 5},
                    {"$project": {
                        "title": 1,
                        "status": 1,
                        "updated_at": 1,
                        "requested_by_name": 1,
                        "approval_type": 1
                    }}
                ]
            }}
        ]
        
        result = list(await approvals_collection.aggregate(pipeline).to_list(1))
        if not result:
            return {}
        
        stats = result[0]
        
        # Calculate average processing time for completed approvals
        processing_pipeline = [
            {"$match": {
                "approvers": hod_id,
                "status": {"$in": ["approved", "rejected"]},
                "created_at": {"$gte": start_date},
                "updated_at": {"$exists": True}
            }},
            {"$project": {
                "processing_hours": {
                    "$divide": [
                        {"$subtract": ["$updated_at", "$created_at"]},
                        3600000  # Convert to hours
                    ]
                }
            }},
            {"$group": {
                "_id": None,
                "avg_hours": {"$avg": "$processing_hours"},
                "min_hours": {"$min": "$processing_hours"},
                "max_hours": {"$max": "$processing_hours"}
            }}
        ]
        
        processing_stats = list(await approvals_collection.aggregate(processing_pipeline).to_list(1))
        
        return {
            "total": stats["total"][0]["count"] if stats["total"] else 0,
            "by_status": {item["_id"]: item["count"] for item in stats["by_status"]},
            "by_type": {item["_id"]: item["count"] for item in stats["by_type"]},
            "by_priority": {item["_id"]: item["count"] for item in stats["by_priority"]},
            "pending_urgent": stats["pending_urgent"][0]["count"] if stats["pending_urgent"] else 0,
            "pending_high": stats["pending_high"][0]["count"] if stats["pending_high"] else 0,
            "processing_stats": processing_stats[0] if processing_stats else {},
            "recent_actions": stats["recent_actions"]
        }
        
    except Exception as e:
        logger.error(f"Get approval statistics error: {e}")
        return {}

async def update_approval_statistics(department: str):
    """Update department approval statistics"""
    try:
        # This would update department-wide statistics
        # Implementation depends on your requirements
        pass
    except Exception as e:
        logger.error(f"Update approval statistics error: {e}")
        
        
# Add this class if you don't have it already
class NotificationService:
    @staticmethod
    async def create_notification(user_id: str, title: str, message: str, 
                                  notification_type: str, priority: str = "medium", 
                                  action_url: str = None, data: dict = None):
        """Create a notification in the database"""
        notification = {
            "user_id": user_id,
            "title": title,
            "message": message,
            "notification_type": notification_type,
            "priority": priority,
            "action_url": action_url,
            "data": data or {},
            "read": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }
        
        await notifications_collection.insert_one(notification)
        return notification
    
