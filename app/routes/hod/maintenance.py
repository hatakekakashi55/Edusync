"""
EduSync Backend - HOD - Maintenance Routes
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

router = APIRouter(tags=["HOD - Maintenance"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/hod/maintenance", tags=["HOD - Resources"])
async def create_maintenance(
    maintenance_data: MaintenanceCreate,
    current_user: dict = Depends(verify_token)
):
    """Create a new maintenance record"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Verify resource exists
        resource = await resources_collection.find_one({
            "_id": ObjectId(maintenance_data.resource_id),
            "department": department
        })
        
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        # Create maintenance record
        maintenance = {
            "resource_id": maintenance_data.resource_id,
            "resource_name": resource["name"],
            "title": maintenance_data.title,
            "description": maintenance_data.description,
            "scheduled_date": maintenance_data.scheduled_date,
            "maintenance_type": maintenance_data.maintenance_type,
            "estimated_hours": maintenance_data.estimated_hours,
            "assigned_to": maintenance_data.assigned_to,
            "department": department,
            "created_by": str(current_user["_id"]),
            "created_by_name": current_user["full_name"],
            "created_at": datetime.now(timezone.utc),
            "status": "pending",
            "actual_hours": None,
            "cost": None,
            "completed_at": None,
            "notes": None,
            "priority": "medium" if maintenance_data.maintenance_type == "routine" else "high"
        }
        
        result = await maintenance_collection.insert_one(maintenance)
        maintenance_id = str(result.inserted_id)
        
        # Update resource status if not already in maintenance
        if resource.get("status") != ResourceStatus.MAINTENANCE.value:
            await resources_collection.update_one(
                {"_id": ObjectId(maintenance_data.resource_id)},
                {"$set": {
                    "status": ResourceStatus.MAINTENANCE.value,
                    "last_maintenance": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
        
        # Send notification if assigned to someone
        if maintenance_data.assigned_to:
            await NotificationService.create_notification(
                user_id=maintenance_data.assigned_to,
                title="🔧 Maintenance Assigned",
                message=f"You have been assigned maintenance for '{resource['name']}'",
                notification_type="maintenance",
                priority=maintenance["priority"],
                action_url=f"/maintenance/{maintenance_id}"
            )
        
        return {
            "success": True,
            "message": "Maintenance record created successfully",
            "maintenance_id": maintenance_id,
            "maintenance": convert_objectid_to_str(maintenance)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create maintenance error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create maintenance record")


@router.post("/api/hod/maintenance/{maintenance_id}/complete", tags=["HOD - Resources"])
async def complete_maintenance(
    maintenance_id: str,
    actual_hours: float = Form(...),
    cost: Optional[float] = Form(None),
    notes: Optional[str] = Form(None),
    condition: str = Form("good", pattern="^(good|fair|poor|replaced)$"),
    current_user: dict = Depends(verify_token)
):
    """Mark maintenance as completed"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        # Get maintenance record
        maintenance = await maintenance_collection.find_one({"_id": ObjectId(maintenance_id)})
        
        if not maintenance:
            raise HTTPException(status_code=404, detail="Maintenance record not found")
        
        if maintenance.get("status") == "completed":
            raise HTTPException(status_code=400, detail="Maintenance already completed")
        
        # Update maintenance record
        update_data = {
            "status": "completed",
            "actual_hours": actual_hours,
            "cost": cost,
            "notes": notes,
            "condition_after": condition,
            "completed_at": datetime.now(timezone.utc),
            "completed_by": str(current_user["_id"]),
            "completed_by_name": current_user["full_name"],
            "updated_at": datetime.now(timezone.utc)
        }
        
        await maintenance_collection.update_one(
            {"_id": ObjectId(maintenance_id)},
            {"$set": update_data}
        )
        
        # Update resource status based on condition
        resource_status = ResourceStatus.AVAILABLE.value
        if condition == "poor":
            resource_status = ResourceStatus.DAMAGED.value
        
        await resources_collection.update_one(
            {"_id": ObjectId(maintenance["resource_id"])},
            {"$set": {
                "status": resource_status,
                "condition": condition,
                "last_maintenance": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        # Log to resource history
        await resource_history_collection.insert_one({
            "resource_id": maintenance["resource_id"],
            "action": "maintenance_completed",
            "details": f"Maintenance completed: {maintenance['title']}. Condition: {condition}",
            "changed_by": str(current_user["_id"]),
            "changed_by_name": current_user["full_name"],
            "changed_at": datetime.now(timezone.utc),
            "maintenance_id": maintenance_id
        })
        
        return {
            "success": True,
            "message": "Maintenance marked as completed",
            "maintenance_id": maintenance_id,
            "resource_status": resource_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Complete maintenance error: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete maintenance")


@router.get("/api/hod/resource-maintenance", tags=["HOD - Resources"])
async def get_resource_maintenance(
    status: Optional[str] = Query(None, description="Filter by status"),
    maintenance_type: Optional[str] = Query(None, description="Filter by type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    search: Optional[str] = Query(None, description="Search by title or description"),
    sort_by: str = Query("scheduled_date", description="Sort field"),
    sort_order: str = Query("desc", description="Sort order"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get resource maintenance records (frontend compatible endpoint)"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        query = {"department": department}
        
        if status:
            query["status"] = status
        
        if maintenance_type:
            query["maintenance_type"] = maintenance_type
        
        if resource_id:
            query["resource_id"] = resource_id
        
        if priority:
            query["priority"] = priority
        
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
                {"resource_name": {"$regex": search, "$options": "i"}}
            ]
        
        # Get total count
        total = await maintenance_collection.count_documents(query)
        
        # Determine sort direction
        sort_direction = -1 if sort_order == "desc" else 1
        
        # Get maintenance records
        records = await maintenance_collection.find(query) \
            .sort(sort_by, sort_direction) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        # Enrich records
        enriched_records = []
        now = datetime.now(timezone.utc)
        
        for record in records:
            # Get resource details
            resource = None
            if record.get("resource_id"):
                resource = await resources_collection.find_one({
                    "_id": ObjectId(record["resource_id"])
                })
            
            # Get assigned user details
            assigned_to = None
            if record.get("assigned_to"):
                user = await users_collection.find_one({
                    "_id": ObjectId(record["assigned_to"])
                })
                if user:
                    assigned_to = {
                        "id": str(user["_id"]),
                        "name": user["full_name"],
                        "email": user["email"]
                    }
            
            # Check if overdue
            is_overdue = False
            if record.get("scheduled_date") and record.get("status") in ["pending", "in_progress"]:
                try:
                    scheduled_date = datetime.fromisoformat(record["scheduled_date"].replace('Z', '+00:00'))
                    if scheduled_date < now:
                        is_overdue = True
                except:
                    pass
            
            # Calculate completion percentage for in_progress
            completion_percentage = 0
            if record.get("status") == "in_progress" and record.get("estimated_hours") and record.get("actual_hours"):
                if record["estimated_hours"] > 0:
                    completion_percentage = min(100, (record["actual_hours"] / record["estimated_hours"]) * 100)
            
            enriched_records.append({
                **convert_objectid_to_str(record),
                "resource_details": convert_objectid_to_str(resource) if resource else None,
                "assigned_to_details": assigned_to,
                "is_overdue": is_overdue,
                "completion_percentage": completion_percentage,
                "days_since_scheduled": calculate_days_difference(record.get("scheduled_date"), now)
            })
        
        # Get statistics
        stats = {
            "total": total,
            "pending": await maintenance_collection.count_documents({**query, "status": "pending"}),
            "in_progress": await maintenance_collection.count_documents({**query, "status": "in_progress"}),
            "completed": await maintenance_collection.count_documents({**query, "status": "completed"}),
            "overdue": await count_overdue_maintenance(department),
            "by_type": await get_maintenance_by_type(department),
            "by_priority": await get_maintenance_by_priority(department)
        }
        
        # Get upcoming maintenance (next 7 days)
        upcoming_cutoff = (now + timedelta(days=7)).isoformat()
        upcoming_maintenance = await maintenance_collection.find({
            "department": department,
            "status": {"$in": ["pending", "in_progress"]},
            "scheduled_date": {"$lte": upcoming_cutoff}
        }).sort("scheduled_date", 1).limit(5).to_list(5)
        
        return {
            "maintenance_records": enriched_records,
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            },
            "statistics": stats,
            "upcoming_maintenance": convert_objectid_to_str(upcoming_maintenance),
            "filter_options": {
                "statuses": ["pending", "in_progress", "completed", "cancelled"],
                "types": await maintenance_collection.distinct("maintenance_type", {"department": department}),
                "priorities": await maintenance_collection.distinct("priority", {"department": department})
            }
        }
        
    except Exception as e:
        logger.error(f"Get resource maintenance error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get maintenance records")


@router.get("/api/hod/resource-maintenance/stats", tags=["HOD - Resources"])
async def get_resource_maintenance_stats(
    period: str = Query("month", description="Time period: week, month, quarter"),
    current_user: dict = Depends(verify_token)
):
    """Get maintenance statistics for dashboard"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Calculate date range
        now = datetime.now(timezone.utc)
        if period == "week":
            start_date = now - timedelta(days=7)
        elif period == "month":
            start_date = now - timedelta(days=30)
        elif period == "quarter":
            start_date = now - timedelta(days=90)
        else:
            start_date = now - timedelta(days=30)  # Default to month
        
        # Get maintenance statistics
        pipeline = [
            {"$match": {
                "department": department,
                "created_at": {"$gte": start_date}
            }},
            {"$facet": {
                "completion_rate": [
                    {"$group": {
                        "_id": None,
                        "total": {"$sum": 1},
                        "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
                        "on_time": {"$sum": {"$cond": [
                            {"$and": [
                                {"$eq": ["$status", "completed"]},
                                {"$lte": ["$completed_at", "$scheduled_date"]}
                            ]},
                            1,
                            0
                        ]}}
                    }}
                ],
                "by_type": [
                    {"$group": {
                        "_id": "$maintenance_type",
                        "count": {"$sum": 1},
                        "avg_hours": {"$avg": "$actual_hours"},
                        "avg_cost": {"$avg": "$cost"}
                    }}
                ],
                "by_resource": [
                    {"$group": {
                        "_id": "$resource_id",
                        "count": {"$sum": 1},
                        "total_cost": {"$sum": "$cost"},
                        "resource_name": {"$first": "$resource_name"}
                    }},
                    {"$sort": {"count": -1}},
                    {"$limit": 5}
                ],
                "monthly_trend": [
                    {"$group": {
                        "_id": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}},
                        "count": {"$sum": 1},
                        "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}}
                    }},
                    {"$sort": {"_id": 1}}
                ],
                "cost_analysis": [
                    {"$match": {"cost": {"$ne": None}}},
                    {"$group": {
                        "_id": None,
                        "total_cost": {"$sum": "$cost"},
                        "avg_cost": {"$avg": "$cost"},
                        "max_cost": {"$max": "$cost"}
                    }}
                ]
            }}
        ]
        
        result = list(await maintenance_collection.aggregate(pipeline).to_list(1))
        
        if not result or not result[0]["completion_rate"]:
            return {
                "period": period,
                "summary": {
                    "total": 0,
                    "completed": 0,
                    "completion_rate": 0,
                    "on_time_rate": 0,
                    "total_cost": 0
                },
                "trends": []
            }
        
        stats = result[0]
        completion_data = stats["completion_rate"][0]
        
        # Calculate rates
        completion_rate = 0
        on_time_rate = 0
        
        if completion_data["total"] > 0:
            completion_rate = (completion_data["completed"] / completion_data["total"]) * 100
            on_time_rate = (completion_data["on_time"] / completion_data["completed"]) * 100 if completion_data["completed"] > 0 else 0
        
        # Cost analysis
        cost_data = stats["cost_analysis"][0] if stats["cost_analysis"] else {
            "total_cost": 0,
            "avg_cost": 0,
            "max_cost": 0
        }
        
        # Get current pending and overdue
        pending_count = await maintenance_collection.count_documents({
            "department": department,
            "status": "pending"
        })
        
        overdue_count = await count_overdue_maintenance(department)
        
        return {
            "period": period,
            "summary": {
                "total": completion_data["total"],
                "completed": completion_data["completed"],
                "pending": pending_count,
                "overdue": overdue_count,
                "completion_rate": round(completion_rate, 1),
                "on_time_rate": round(on_time_rate, 1),
                "total_cost": cost_data["total_cost"],
                "avg_cost": round(cost_data["avg_cost"], 2),
                "max_cost": cost_data["max_cost"]
            },
            "by_type": stats["by_type"],
            "by_resource": stats["by_resource"],
            "monthly_trend": stats["monthly_trend"],
            "cost_analysis": cost_data,
            "priority_distribution": await get_maintenance_priority_distribution(department)
        }
        
    except Exception as e:
        logger.error(f"Get resource maintenance stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get maintenance statistics")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.get("/api/hod/maintenance", tags=["HOD - Resources"])
async def get_maintenance_records(
    status: Optional[str] = Query(None, description="Filter by status"),
    resource_id: Optional[str] = Query(None, description="Filter by resource"),
    maintenance_type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get maintenance records"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        query = {"department": department}
        
        if status:
            query["status"] = status
        
        if resource_id:
            query["resource_id"] = resource_id
        
        if maintenance_type:
            query["maintenance_type"] = maintenance_type
        
        total = await maintenance_collection.count_documents(query)
        
        records = await maintenance_collection.find(query) \
            .sort("scheduled_date", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        # Enrich with resource details
        enriched_records = []
        for record in records:
            resource = None
            if record.get("resource_id"):
                resource = await resources_collection.find_one({
                    "_id": ObjectId(record["resource_id"])
                })
            
            assigned_to = None
            if record.get("assigned_to"):
                user = await users_collection.find_one({
                    "_id": ObjectId(record["assigned_to"])
                })
                if user:
                    assigned_to = user["full_name"]
            
            enriched_records.append({
                **convert_objectid_to_str(record),
                "resource_details": convert_objectid_to_str(resource) if resource else None,
                "assigned_to_name": assigned_to
            })
        
        return {
            "maintenance_records": enriched_records,
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            },
            "summary": {
                "pending": await maintenance_collection.count_documents({**query, "status": "pending"}),
                "in_progress": await maintenance_collection.count_documents({**query, "status": "in_progress"}),
                "completed": await maintenance_collection.count_documents({**query, "status": "completed"}),
                "overdue": await get_overdue_maintenance_count(department)
            }
        }
        
    except Exception as e:
        logger.error(f"Get maintenance records error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get maintenance records")


