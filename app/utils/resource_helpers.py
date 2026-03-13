"""
EduSync Backend - Resource Helpers
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


async def get_resources_by_location(department: str):
    """Get resource statistics by location"""
    pipeline = [
        {"$match": {"department": department}},
        {"$group": {
            "_id": "$location",
            "total": {"$sum": 1},
            "available": {"$sum": {"$cond": [{"$eq": ["$status", "available"]}, 1, 0]}},
            "in_use": {"$sum": {"$cond": [{"$eq": ["$status", "in-use"]}, 1, 0]}},
            "maintenance": {"$sum": {"$cond": [{"$eq": ["$status", "maintenance"]}, 1, 0]}}
        }},
        {"$sort": {"total": -1}}
    ]
    
    return list(await resources_collection.aggregate(pipeline).to_list(10))

async def get_distinct_values(field: str, department: str):
    """Get distinct values for a field"""
    return await resources_collection.distinct(field, {"department": department})

async def get_current_resource_usage(resource_id: str):
    """Get current usage information for a resource"""
    # This would check if resource is currently assigned to someone
    resource = await resources_collection.find_one({"_id": ObjectId(resource_id)})
    
    if resource.get("status") != ResourceStatus.IN_USE.value:
        return None
    
    return {
        "assigned_to": resource.get("assigned_to_name"),
        "assigned_date": resource.get("assigned_date"),
        "purpose": resource.get("purpose"),
        "expected_return": resource.get("expected_return_date")
    }

def calculate_resource_age(purchase_date: Optional[str]):
    """Calculate age of resource in years"""
    if not purchase_date:
        return "Unknown"
    
    try:
        purchase = datetime.fromisoformat(purchase_date.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        years = (now - purchase).days / 365.25
        return f"{years:.1f} years"
    except:
        return "Unknown"

def check_warranty_status(warranty_expiry: Optional[str]):
    """Check warranty status"""
    if not warranty_expiry:
        return {"status": "no_warranty", "message": "No warranty information"}
    
    try:
        expiry = datetime.fromisoformat(warranty_expiry.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        days_remaining = (expiry - now).days
        
        if days_remaining < 0:
            return {"status": "expired", "message": f"Expired {-days_remaining} days ago"}
        elif days_remaining < 30:
            return {"status": "expiring_soon", "message": f"Expires in {days_remaining} days"}
        else:
            return {"status": "active", "message": f"Active for {days_remaining} more days"}
    except:
        return {"status": "unknown", "message": "Invalid date format"}

async def get_resource_usage_stats(resource_id: str):
    """Get usage statistics for a resource"""
    pipeline = [
        {"$match": {"resource_id": resource_id, "action": "assigned"}},
        {"$group": {
            "_id": None,
            "total_assignments": {"$sum": 1},
            "last_assigned": {"$max": "$changed_at"},
            "first_assigned": {"$min": "$changed_at"}
        }}
    ]
    
    stats = list(await resource_history_collection.aggregate(pipeline).to_list(1))
    
    if stats:
        return {
            "total_assignments": stats[0]["total_assignments"],
            "last_assigned": stats[0]["last_assigned"],
            "first_assigned": stats[0]["first_assigned"]
        }
    
    return {"total_assignments": 0, "last_assigned": None, "first_assigned": None}

async def get_resource_availability_calendar(resource_id: str):
    """Get resource availability calendar for next 30 days"""
    # Get current and future assignments
    future_assignments = await resource_history_collection.find({
        "resource_id": resource_id,
        "action": "assigned",
        "changed_at": {"$gte": datetime.now(timezone.utc)}
    }).sort("changed_at", 1).limit(10).to_list(10)
    
    # Get maintenance schedule
    maintenance_schedule = await maintenance_collection.find({
        "resource_id": resource_id,
        "scheduled_date": {"$gte": datetime.now(timezone.utc).isoformat()},
        "status": {"$in": ["pending", "in_progress"]}
    }).sort("scheduled_date", 1).limit(10).to_list(10)
    
    calendar = []
    
    # Add assignments to calendar
    for assignment in future_assignments:
        calendar.append({
            "date": assignment["changed_at"],
            "type": "assignment",
            "title": f"Assigned to {assignment.get('assignee_name', 'Unknown')}",
            "status": "scheduled"
        })
    
    # Add maintenance to calendar
    for maintenance in maintenance_schedule:
        calendar.append({
            "date": maintenance["scheduled_date"],
            "type": "maintenance",
            "title": maintenance["title"],
            "status": maintenance["status"]
        })
    
    return calendar

async def create_maintenance_record(resource_id: str, description: str, current_user: dict):
    """Create an automatic maintenance record"""
    maintenance = {
        "resource_id": resource_id,
        "title": "Automatic Maintenance Request",
        "description": description,
        "scheduled_date": datetime.now(timezone.utc).isoformat(),
        "maintenance_type": "repair",
        "estimated_hours": 2,
        "assigned_to": None,
        "department": current_user["department"],
        "created_by": str(current_user["_id"]),
        "created_by_name": current_user["full_name"],
        "created_at": datetime.now(timezone.utc),
        "status": "pending",
        "priority": "medium"
    }
    
    await maintenance_collection.insert_one(maintenance)

async def get_overdue_maintenance_count(department: str):
    """Get count of overdue maintenance records"""
    now = datetime.now(timezone.utc).isoformat()
    
    return await maintenance_collection.count_documents({
        "department": department,
        "status": {"$in": ["pending", "in_progress"]},
        "scheduled_date": {"$lt": now}
    })
    
