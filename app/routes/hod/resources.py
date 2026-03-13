"""
EduSync Backend - HOD - Resources Routes
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

router = APIRouter(tags=["HOD - Resources"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.get("/api/hod/resources/stats", tags=["HOD - Resources"])
async def get_resource_stats(
    current_user: dict = Depends(verify_token)
):
    """Get comprehensive resource statistics for HOD dashboard"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Get total resources count by category
        pipeline = [
            {"$match": {"department": department}},
            {"$group": {
                "_id": "$category",
                "count": {"$sum": 1},
                "available": {"$sum": {"$cond": [{"$eq": ["$status", "available"]}, 1, 0]}},
                "in_use": {"$sum": {"$cond": [{"$eq": ["$status", "in-use"]}, 1, 0]}},
                "maintenance": {"$sum": {"$cond": [{"$eq": ["$status", "maintenance"]}, 1, 0]}}
            }}
        ]
        
        category_stats = list(await resources_collection.aggregate(pipeline).to_list(20))
        
        # Get total counts
        total_resources = await resources_collection.count_documents({"department": department})
        available_resources = await resources_collection.count_documents({
            "department": department,
            "status": ResourceStatus.AVAILABLE.value
        })
        in_use_resources = await resources_collection.count_documents({
            "department": department,
            "status": ResourceStatus.IN_USE.value
        })
        
        # Get maintenance requests
        active_maintenance = await maintenance_collection.count_documents({
            "department": department,
            "status": "in_progress"
        })
        
        # Get pending resource requests
        pending_requests = await resource_requests_collection.count_documents({
            "department": department,
            "status": "pending"
        })
        
        # Calculate utilization rate
        utilization_rate = 0
        if total_resources > 0:
            utilization_rate = (in_use_resources / total_resources) * 100
        
        # Get software licenses summary
        license_stats = await software_licenses_collection.aggregate([
            {"$match": {"department": department}},
            {"$group": {
                "_id": None,
                "total_licenses": {"$sum": 1},
                "active_licenses": {"$sum": {"$cond": [{"$gt": ["$expiry_date", datetime.now(timezone.utc).isoformat()]}, 1, 0]}},
                "total_users": {"$sum": {"$ifNull": ["$max_users", 1]}}
            }}
        ]).to_list(1)
        
        # Get recent maintenance activities
        recent_maintenance = await maintenance_collection.find({
            "department": department
        }).sort("scheduled_date", -1).limit(5).to_list(5)
        
        return {
            "department": department,
            "summary": {
                "total_resources": total_resources,
                "available_resources": available_resources,
                "in_use_resources": in_use_resources,
                "utilization_rate": round(utilization_rate, 1),
                "active_maintenance": active_maintenance,
                "pending_requests": pending_requests
            },
            "category_breakdown": category_stats,
            "software_licenses": license_stats[0] if license_stats else {
                "total_licenses": 0,
                "active_licenses": 0,
                "total_users": 0
            },
            "recent_maintenance": convert_objectid_to_str(recent_maintenance),
            "stats_by_location": await get_resources_by_location(department)
        }
        
    except Exception as e:
        logger.error(f"Get resource stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resource statistics")


@router.post("/api/hod/resources", tags=["HOD - Resources"])
async def create_resource(
    resource_data: ResourceCreate,
    current_user: dict = Depends(verify_token)
):
    """Create a new resource"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Check for duplicate serial number
        if resource_data.serial_number:
            existing = await resources_collection.find_one({
                "serial_number": resource_data.serial_number,
                "department": department
            })
            if existing:
                raise HTTPException(status_code=400, detail="Serial number already exists")
        
        resource = {
            "name": resource_data.name,
            "category": resource_data.category.value,
            "model": resource_data.model,
            "serial_number": resource_data.serial_number,
            "location": resource_data.location.value,
            "status": resource_data.status.value,
            "description": resource_data.description,
            "purchase_date": resource_data.purchase_date,
            "warranty_expiry": resource_data.warranty_expiry,
            "purchase_cost": resource_data.purchase_cost,
            "vendor": resource_data.vendor,
            "notes": resource_data.notes,
            "department": department,
            "created_by": str(current_user["_id"]),
            "created_by_name": current_user["full_name"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "assigned_to": None,
            "assigned_date": None,
            "last_maintenance": None,
            "usage_count": 0,
            "condition": "new" if resource_data.status == ResourceStatus.AVAILABLE else "used"
        }
        
        result = await resources_collection.insert_one(resource)
        resource_id = str(result.inserted_id)
        
        # Log to resource history
        await resource_history_collection.insert_one({
            "resource_id": resource_id,
            "action": "created",
            "details": "Resource created",
            "changed_by": str(current_user["_id"]),
            "changed_by_name": current_user["full_name"],
            "changed_at": datetime.now(timezone.utc),
            "previous_state": None,
            "new_state": resource
        })
        
        # Send notification
        await NotificationService.create_notification(
            user_id=str(current_user["_id"]),
            title="✅ Resource Created",
            message=f"Resource '{resource_data.name}' has been created successfully",
            notification_type="resource",
            priority="medium"
        )
        
        return {
            "success": True,
            "message": "Resource created successfully",
            "resource_id": resource_id,
            "resource": convert_objectid_to_str(resource)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create resource error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create resource")


@router.delete("/api/hod/resources/{resource_id}", tags=["HOD - Resources"])
async def delete_resource(
    resource_id: str,
    current_user: dict = Depends(verify_token)
):
    """Delete a resource (soft delete)"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Check if resource exists and is not in use
        resource = await resources_collection.find_one({
            "_id": ObjectId(resource_id),
            "department": department
        })
        
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        if resource.get("status") == ResourceStatus.IN_USE.value:
            raise HTTPException(status_code=400, detail="Cannot delete resource currently in use")
        
        # Soft delete by marking as archived
        await resources_collection.update_one(
            {"_id": ObjectId(resource_id)},
            {"$set": {
                "status": "archived",
                "archived_at": datetime.now(timezone.utc),
                "archived_by": str(current_user["_id"]),
                "archived_by_name": current_user["full_name"],
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        # Log to history
        await resource_history_collection.insert_one({
            "resource_id": resource_id,
            "action": "archived",
            "details": "Resource archived (soft delete)",
            "changed_by": str(current_user["_id"]),
            "changed_by_name": current_user["full_name"],
            "changed_at": datetime.now(timezone.utc),
            "previous_state": resource
        })
        
        return {
            "success": True,
            "message": "Resource archived successfully",
            "resource_id": resource_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete resource error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete resource")


@router.post("/api/hod/resources/{resource_id}/assign", tags=["HOD - Resources"])
async def assign_resource(
    resource_id: str,
    assign_to: str = Form(...),
    purpose: str = Form(...),
    expected_return_date: Optional[str] = Form(None),
    current_user: dict = Depends(verify_token)
):
    """Assign a resource to a user"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Check resource availability
        resource = await resources_collection.find_one({
            "_id": ObjectId(resource_id),
            "department": department,
            "status": ResourceStatus.AVAILABLE.value
        })
        
        if not resource:
            raise HTTPException(status_code=400, detail="Resource not available for assignment")
        
        # Verify assignee exists
        assignee = await users_collection.find_one({
            "_id": ObjectId(assign_to),
            "department": department
        })
        
        if not assignee:
            raise HTTPException(status_code=404, detail="Assignee not found")
        
        # Update resource
        update_data = {
            "status": ResourceStatus.IN_USE.value,
            "assigned_to": assign_to,
            "assigned_to_name": assignee["full_name"],
            "assigned_date": datetime.now(timezone.utc),
            "assigned_by": str(current_user["_id"]),
            "assigned_by_name": current_user["full_name"],
            "purpose": purpose,
            "expected_return_date": expected_return_date,
            "updated_at": datetime.now(timezone.utc)
        }
        
        await resources_collection.update_one(
            {"_id": ObjectId(resource_id)},
            {"$set": update_data}
        )
        
        # Log to history
        await resource_history_collection.insert_one({
            "resource_id": resource_id,
            "action": "assigned",
            "details": f"Assigned to {assignee['full_name']} for {purpose}",
            "changed_by": str(current_user["_id"]),
            "changed_by_name": current_user["full_name"],
            "changed_at": datetime.now(timezone.utc),
            "previous_state": resource,
            "new_state": update_data,
            "assignee_id": assign_to,
            "assignee_name": assignee["full_name"]
        })
        
        # Send notification to assignee
        await NotificationService.create_notification(
            user_id=assign_to,
            title="📦 Resource Assigned",
            message=f"You have been assigned '{resource['name']}' for {purpose}",
            notification_type="resource_assignment",
            priority="high",
            action_url=f"/resources/{resource_id}"
        )
        
        return {
            "success": True,
            "message": "Resource assigned successfully",
            "resource_id": resource_id,
            "assignee": {
                "id": assign_to,
                "name": assignee["full_name"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Assign resource error: {e}")
        raise HTTPException(status_code=500, detail="Failed to assign resource")


@router.post("/api/hod/resources/{resource_id}/return", tags=["HOD - Resources"])
async def return_resource(
    resource_id: str,
    condition: str = Form("good", pattern="^(good|damaged|needs_maintenance)$"),
    notes: Optional[str] = Form(None),
    current_user: dict = Depends(verify_token)
):
    """Return a resource that was in use"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Check resource is currently assigned
        resource = await resources_collection.find_one({
            "_id": ObjectId(resource_id),
            "department": department,
            "status": ResourceStatus.IN_USE.value
        })
        
        if not resource:
            raise HTTPException(status_code=400, detail="Resource is not currently assigned")
        
        # Save assignment info before clearing
        assignment_info = {
            "assigned_to": resource.get("assigned_to"),
            "assigned_to_name": resource.get("assigned_to_name"),
            "assigned_date": resource.get("assigned_date"),
            "purpose": resource.get("purpose")
        }
        
        # Determine new status based on condition
        new_status = ResourceStatus.AVAILABLE.value
        if condition == "damaged":
            new_status = ResourceStatus.DAMAGED.value
        elif condition == "needs_maintenance":
            new_status = ResourceStatus.MAINTENANCE.value
        
        # Update resource
        update_data = {
            "status": new_status,
            "condition": condition,
            "returned_at": datetime.now(timezone.utc),
            "returned_by": str(current_user["_id"]),
            "returned_by_name": current_user["full_name"],
            "return_notes": notes,
            "last_used": datetime.now(timezone.utc),
            "usage_count": (resource.get("usage_count", 0) + 1),
            "assigned_to": None,
            "assigned_to_name": None,
            "assigned_date": None,
            "purpose": None,
            "expected_return_date": None,
            "updated_at": datetime.now(timezone.utc)
        }
        
        await resources_collection.update_one(
            {"_id": ObjectId(resource_id)},
            {"$set": update_data}
        )
        
        # Log to history
        await resource_history_collection.insert_one({
            "resource_id": resource_id,
            "action": "returned",
            "details": f"Returned by {assignment_info['assigned_to_name']}. Condition: {condition}. Notes: {notes}",
            "changed_by": str(current_user["_id"]),
            "changed_by_name": current_user["full_name"],
            "changed_at": datetime.now(timezone.utc),
            "previous_state": resource,
            "new_state": update_data,
            "assignee_id": assignment_info["assigned_to"],
            "assignee_name": assignment_info["assigned_to_name"]
        })
        
        # If damaged or needs maintenance, create maintenance request
        if condition in ["damaged", "needs_maintenance"]:
            await create_maintenance_record(
                resource_id,
                f"Automatic maintenance after return. Condition: {condition}. Notes: {notes}",
                current_user
            )
        
        # Send notification to original assignee
        if assignment_info["assigned_to"]:
            await NotificationService.create_notification(
                user_id=assignment_info["assigned_to"],
                title="✅ Resource Returned",
                message=f"Resource '{resource['name']}' has been returned",
                notification_type="resource_return",
                priority="medium"
            )
        
        return {
            "success": True,
            "message": "Resource returned successfully",
            "resource_id": resource_id,
            "condition": condition,
            "new_status": new_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Return resource error: {e}")
        raise HTTPException(status_code=500, detail="Failed to return resource")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.get("/api/hod/resources", tags=["HOD - Resources"])
async def get_resources(
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    location: Optional[str] = Query(None, description="Filter by location"),
    search: Optional[str] = Query(None, description="Search by name or model"),
    sort_by: str = Query("name", description="Sort field"),
    sort_order: str = Query("asc", description="Sort order"),
    limit: int = Query(100, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get resources with filtering and pagination"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Build query
        query = {"department": department}
        
        if resource_type:
            query["category"] = resource_type
        
        if status:
            query["status"] = status
        
        if location:
            query["location"] = location
        
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"model": {"$regex": search, "$options": "i"}},
                {"serial_number": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}}
            ]
        
        # Get total count
        total = await resources_collection.count_documents(query)
        
        # Determine sort direction
        sort_direction = 1 if sort_order == "asc" else -1
        
        # Get resources with pagination
        resources = await resources_collection.find(query) \
            .sort(sort_by, sort_direction) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        # Get additional info for each resource
        enriched_resources = []
        for resource in resources:
            # Get maintenance history
            maintenance_history = await maintenance_collection.find({
                "resource_id": str(resource["_id"])
            }).sort("scheduled_date", -1).limit(3).to_list(3)
            
            # Get current usage if in use
            current_usage = None
            if resource.get("status") == ResourceStatus.IN_USE.value:
                current_usage = await get_current_resource_usage(str(resource["_id"]))
            
            enriched_resource = {
                **convert_objectid_to_str(resource),
                "maintenance_history": convert_objectid_to_str(maintenance_history),
                "current_usage": current_usage,
                "age_years": calculate_resource_age(resource.get("purchase_date")),
                "warranty_status": check_warranty_status(resource.get("warranty_expiry"))
            }
            enriched_resources.append(enriched_resource)
        
        # Get filter options for frontend
        filter_options = {
            "categories": await get_distinct_values("category", department),
            "statuses": await get_distinct_values("status", department),
            "locations": await get_distinct_values("location", department)
        }
        
        return {
            "resources": enriched_resources,
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            },
            "filter_options": filter_options,
            "summary": {
                "total": total,
                "available": await resources_collection.count_documents({**query, "status": "available"}),
                "in_use": await resources_collection.count_documents({**query, "status": "in-use"}),
                "maintenance": await resources_collection.count_documents({**query, "status": "maintenance"})
            }
        }
        
    except Exception as e:
        logger.error(f"Get resources error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resources")


@router.get("/api/hod/resources/{resource_id}", tags=["HOD - Resources"])
async def get_resource_details(
    resource_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get detailed information about a specific resource"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        resource = await resources_collection.find_one({
            "_id": ObjectId(resource_id),
            "department": current_user["department"]
        })
        
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        # Get maintenance history
        maintenance_history = await maintenance_collection.find({
            "resource_id": resource_id
        }).sort("scheduled_date", -1).to_list(20)
        
        # Get assignment history
        assignment_history = await resource_history_collection.find({
            "resource_id": resource_id,
            "action": {"$in": ["assigned", "returned", "reserved"]}
        }).sort("changed_at", -1).to_list(20)
        
        # Get usage statistics
        usage_stats = await get_resource_usage_stats(resource_id)
        
        # Get related requests
        related_requests = await resource_requests_collection.find({
            "requested_resource": resource.get("name"),
            "department": current_user["department"]
        }).sort("created_at", -1).limit(5).to_list(5)
        
        # Get warranty information
        warranty_info = {}
        if resource.get("warranty_expiry"):
            expiry_date = datetime.fromisoformat(resource["warranty_expiry"].replace('Z', '+00:00'))
            days_remaining = (expiry_date - datetime.now(timezone.utc)).days
            warranty_info = {
                "expiry_date": resource["warranty_expiry"],
                "days_remaining": max(0, days_remaining),
                "status": "active" if days_remaining > 0 else "expired",
                "vendor": resource.get("vendor")
            }
        
        result = {
            **convert_objectid_to_str(resource),
            "maintenance_history": convert_objectid_to_str(maintenance_history),
            "assignment_history": convert_objectid_to_str(assignment_history),
            "usage_stats": usage_stats,
            "related_requests": convert_objectid_to_str(related_requests),
            "warranty_info": warranty_info,
            "total_maintenance_cost": sum(m.get("cost", 0) for m in maintenance_history if m.get("cost")),
            "availability_calendar": await get_resource_availability_calendar(resource_id)
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Get resource details error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resource details")


@router.put("/api/hod/resources/{resource_id}", tags=["HOD - Resources"])
async def update_resource(
    resource_id: str,
    resource_data: dict,
    current_user: dict = Depends(verify_token)
):
    """Update resource information"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Get current resource
        current_resource = await resources_collection.find_one({
            "_id": ObjectId(resource_id),
            "department": department
        })
        
        if not current_resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        # Validate status transitions
        if "status" in resource_data:
            current_status = current_resource.get("status")
            new_status = resource_data["status"]
            
            # Validate status transition
            valid_transitions = {
                "available": ["in-use", "maintenance", "reserved"],
                "in-use": ["available", "maintenance"],
                "maintenance": ["available", "damaged"],
                "reserved": ["available", "in-use"],
                "damaged": ["maintenance"]
            }
            
            if current_status in valid_transitions:
                if new_status not in valid_transitions[current_status]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Cannot change status from {current_status} to {new_status}"
                    )
        
        # Prepare update data
        update_data = {
            **resource_data,
            "updated_at": datetime.now(timezone.utc),
            "updated_by": str(current_user["_id"]),
            "updated_by_name": current_user["full_name"]
        }
        
        # Save old state for history
        old_state = {k: v for k, v in current_resource.items() if k not in ["_id", "created_at", "updated_at"]}
        
        # Update resource
        await resources_collection.update_one(
            {"_id": ObjectId(resource_id)},
            {"$set": update_data}
        )
        
        # Log to history
        await resource_history_collection.insert_one({
            "resource_id": resource_id,
            "action": "updated",
            "details": "Resource information updated",
            "changed_by": str(current_user["_id"]),
            "changed_by_name": current_user["full_name"],
            "changed_at": datetime.now(timezone.utc),
            "previous_state": old_state,
            "new_state": {**current_resource, **update_data}
        })
        
        # If status changed to maintenance, create maintenance record
        if "status" in resource_data and resource_data["status"] == "maintenance":
            await create_maintenance_record(resource_id, "Automatic maintenance", current_user)
        
        # Get updated resource
        updated_resource = await resources_collection.find_one({"_id": ObjectId(resource_id)})
        
        return {
            "success": True,
            "message": "Resource updated successfully",
            "resource_id": resource_id,
            "resource": convert_objectid_to_str(updated_resource)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update resource error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update resource")


