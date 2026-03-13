"""
EduSync Backend - HOD - Resource Requests Routes
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

router = APIRouter(tags=["HOD - Resource Requests"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/hod/resource-requests", tags=["HOD - Resources"])
async def create_resource_request(
    request_data: ResourceRequestCreate,
    current_user: dict = Depends(verify_token)
):
    """Create a new resource request"""
    try:
        user_id = str(current_user["_id"])
        
        # Check if user can make requests
        if current_user["user_type"] not in [UserType.FACULTY.value, UserType.STUDENT.value, UserType.HOD.value]:
            raise HTTPException(status_code=403, detail="Not authorized to create resource requests")
        
        # Get HOD for approval if not HOD
        hod_id = None
        if current_user["user_type"] != UserType.HOD.value:
            hod = await users_collection.find_one({
                "user_type": UserType.HOD.value,
                "department": current_user["department"]
            })
            if hod:
                hod_id = str(hod["_id"])
        
        resource_request = {
            "title": request_data.title,
            "description": request_data.description,
            "resource_type": request_data.requested_resource,
            "item_name": request_data.requested_resource,  # For compatibility
            "priority": request_data.priority,
            "duration": request_data.duration,
            "purpose": request_data.purpose,
            "department": current_user["department"],
            "requested_by": user_id,
            "requested_by_name": current_user["full_name"],
            "requested_by_email": current_user["email"],
            "requested_by_role": current_user["user_type"],
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "approver_id": hod_id,
            "approval_status": "pending" if hod_id else "auto_approved",
            "attachments": [],
            "comments": [],
            "estimated_cost": None,
            "vendor_details": None,
            "quantity": 1,
            "urgency": request_data.priority
        }
        
        result = await resource_requests_collection.insert_one(resource_request)
        request_id = str(result.inserted_id)
        
        # If HOD is making request, auto-approve
        if current_user["user_type"] == UserType.HOD.value:
            await resource_requests_collection.update_one(
                {"_id": ObjectId(request_id)},
                {"$set": {
                    "status": "approved",
                    "approval_status": "approved",
                    "approved_at": datetime.now(timezone.utc),
                    "approved_by": user_id,
                    "approved_by_name": current_user["full_name"],
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
        else:
            # Create approval request for HOD
            approval_data = {
                "title": f"Resource Request: {request_data.title}",
                "description": f"Resource Type: {request_data.requested_resource}\n\nPriority: {request_data.priority}\n\nPurpose: {request_data.purpose}\n\nDuration: {request_data.duration or 'Not specified'}",
                "approval_type": "resource_request",
                "priority": request_data.priority,
                "department": current_user["department"],
                "requested_by": user_id,
                "requested_by_name": current_user["full_name"],
                "metadata": {
                    "resource_request_id": request_id,
                    "resource_type": request_data.requested_resource,
                    "purpose": request_data.purpose
                },
                "attachments": [],
                "approvers": [hod_id] if hod_id else []
            }
            
            approval_result = await create_approval_request_internal(approval_data, current_user)
            
            # Link approval to resource request
            await resource_requests_collection.update_one(
                {"_id": ObjectId(request_id)},
                {"$set": {"approval_id": approval_result["approval_id"]}}
            )
        
        # Send notification
        notification_target = hod_id if hod_id else user_id
        await NotificationService.create_notification(
            user_id=notification_target,
            title="📋 New Resource Request",
            message=f"Resource request '{request_data.title}' has been submitted",
            notification_type="resource_request",
            priority=request_data.priority,
            action_url=f"/hod/resource-requests/{request_id}"
        )
        
        return {
            "success": True,
            "message": "Resource request submitted successfully",
            "request_id": request_id,
            "requires_approval": current_user["user_type"] != UserType.HOD.value,
            "approver": hod_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create resource request error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create resource request")


@router.get("/api/hod/resource-requests/stats", tags=["HOD - Resources"])
async def get_resource_requests_stats(
    period: str = Query("month", description="Time period: day, week, month, quarter, year"),
    current_user: dict = Depends(verify_token)
):
    """Get resource requests statistics"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Calculate date range
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
        
        # Get request statistics
        pipeline = [
            {"$match": {
                "department": department,
                "created_at": {"$gte": start_date}
            }},
            {"$facet": {
                "by_status": [
                    {"$group": {
                        "_id": "$status",
                        "count": {"$sum": 1},
                        "urgent": {"$sum": {"$cond": [{"$eq": ["$priority", "urgent"]}, 1, 0]}}
                    }}
                ],
                "by_type": [
                    {"$group": {
                        "_id": "$resource_type",
                        "count": {"$sum": 1},
                        "avg_days": {"$avg": {"$divide": [
                            {"$subtract": [{"$ifNull": ["$resolved_at", now]}, "$created_at"]},
                            86400000  # milliseconds in a day
                        ]}}
                    }}
                ],
                "by_priority": [
                    {"$group": {
                        "_id": "$priority",
                        "count": {"$sum": 1},
                        "avg_resolution_days": {"$avg": {"$cond": [
                            {"$ne": ["$resolved_at", None]},
                            {"$divide": [
                                {"$subtract": ["$resolved_at", "$created_at"]},
                                86400000
                            ]},
                            None
                        ]}}
                    }}
                ],
                "daily_trend": [
                    {"$group": {
                        "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                        "count": {"$sum": 1},
                        "approved": {"$sum": {"$cond": [{"$eq": ["$status", "approved"]}, 1, 0]}}
                    }},
                    {"$sort": {"_id": 1}},
                    {"$limit": 30}
                ]
            }}
        ]
        
        result = list(await resource_requests_collection.aggregate(pipeline).to_list(1))
        
        if not result:
            return {
                "period": period,
                "summary": {
                    "total": 0,
                    "pending": 0,
                    "approved": 0,
                    "rejected": 0,
                    "avg_resolution_days": 0
                },
                "trends": []
            }
        
        stats = result[0]
        
        # Calculate summary
        by_status = {item["_id"]: item["count"] for item in stats["by_status"]}
        
        summary = {
            "total": sum(by_status.values()),
            "pending": by_status.get("pending", 0),
            "approved": by_status.get("approved", 0),
            "rejected": by_status.get("rejected", 0),
            "in_progress": by_status.get("in_progress", 0),
            "urgent_pending": sum(item.get("urgent", 0) for item in stats["by_status"] if item["_id"] == "pending")
        }
        
        # Calculate average resolution days
        total_resolution_days = 0
        resolved_count = 0
        for item in stats["by_priority"]:
            if item.get("avg_resolution_days"):
                total_resolution_days += item["avg_resolution_days"] * item["count"]
                resolved_count += item["count"]
        
        if resolved_count > 0:
            summary["avg_resolution_days"] = round(total_resolution_days / resolved_count, 1)
        else:
            summary["avg_resolution_days"] = 0
        
        return {
            "period": period,
            "summary": summary,
            "by_type": stats["by_type"],
            "by_priority": stats["by_priority"],
            "daily_trend": stats["daily_trend"],
            "pending_by_urgency": {
                "urgent": await resource_requests_collection.count_documents({
                    "department": department,
                    "status": "pending",
                    "priority": "urgent"
                }),
                "high": await resource_requests_collection.count_documents({
                    "department": department,
                    "status": "pending",
                    "priority": "high"
                }),
                "medium": await resource_requests_collection.count_documents({
                    "department": department,
                    "status": "pending",
                    "priority": "medium"
                }),
                "low": await resource_requests_collection.count_documents({
                    "department": department,
                    "status": "pending",
                    "priority": "low"
                })
            }
        }
        
    except Exception as e:
        logger.error(f"Get resource requests stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resource requests statistics")


@router.get("/api/hod/resource-requests/{request_id}", tags=["HOD - Resources"])
async def get_resource_request_details(
    request_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get detailed resource request information"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        request = await resource_requests_collection.find_one({
            "_id": ObjectId(request_id),
            "department": department
        })
        
        if not request:
            raise HTTPException(status_code=404, detail="Resource request not found")
        
        # Get requester details
        requester = await users_collection.find_one({"_id": ObjectId(request["requested_by"])})
        
        # Get approval details if exists
        approval = None
        if request.get("approval_id"):
            approval = await approvals_collection.find_one({"_id": ObjectId(request["approval_id"])})
        
        # Get similar requests
        similar_requests = await resource_requests_collection.find({
            "department": department,
            "resource_type": request.get("resource_type"),
            "_id": {"$ne": ObjectId(request_id)}
        }).sort("created_at", -1).limit(5).to_list(5)
        
        # Get available resources of same type
        available_resources = []
        if request.get("resource_type"):
            available_resources = await resources_collection.find({
                "department": department,
                "category": request["resource_type"],
                "status": "available"
            }).limit(5).to_list(5)
        
        result = {
            **convert_objectid_to_str(request),
            "requester_details": {
                "name": request["requested_by_name"],
                "email": request.get("requested_by_email"),
                "role": request.get("requested_by_role"),
                "department": requester.get("department") if requester else department,
                "phone": requester.get("phone") if requester else None,
                "designation": requester.get("designation") if requester else None
            },
            "approval_details": convert_objectid_to_str(approval) if approval else None,
            "similar_requests": convert_objectid_to_str(similar_requests),
            "available_resources": convert_objectid_to_str(available_resources),
            "can_approve": request.get("status") == "pending",
            "can_reject": request.get("status") == "pending",
            "days_open": (datetime.now(timezone.utc) - request["created_at"]).days,
            "is_urgent": request.get("priority") in ["urgent", "high"]
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Get resource request details error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resource request details")


@router.post("/api/hod/resource-requests/{request_id}/approve", tags=["HOD - Resources"])
async def approve_resource_request(
    request_id: str,
    comments: Optional[str] = Form(None),
    allocate_resource_id: Optional[str] = Form(None),
    estimated_cost: Optional[float] = Form(None),
    vendor_details: Optional[str] = Form(None),
    current_user: dict = Depends(verify_token)
):
    """Approve a resource request"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Get request
        request = await resource_requests_collection.find_one({
            "_id": ObjectId(request_id),
            "department": department
        })
        
        if not request:
            raise HTTPException(status_code=404, detail="Resource request not found")
        
        if request.get("status") != "pending":
            raise HTTPException(status_code=400, detail=f"Request is already {request.get('status')}")
        
        update_data = {
            "status": "approved",
            "approval_status": "approved",
            "approved_at": datetime.now(timezone.utc),
            "approved_by": str(current_user["_id"]),
            "approved_by_name": current_user["full_name"],
            "approver_comments": comments,
            "estimated_cost": estimated_cost,
            "vendor_details": json.loads(vendor_details) if vendor_details else None,
            "updated_at": datetime.now(timezone.utc)
        }
        
        # Allocate resource if specified
        if allocate_resource_id:
            # Check resource availability
            resource = await resources_collection.find_one({
                "_id": ObjectId(allocate_resource_id),
                "department": department,
                "status": "available"
            })
            
            if not resource:
                raise HTTPException(status_code=400, detail="Selected resource is not available")
            
            # Allocate resource
            await resources_collection.update_one(
                {"_id": ObjectId(allocate_resource_id)},
                {"$set": {
                    "status": "in-use",
                    "assigned_to": request["requested_by"],
                    "assigned_to_name": request["requested_by_name"],
                    "assigned_date": datetime.now(timezone.utc),
                    "assigned_by": str(current_user["_id"]),
                    "assigned_by_name": current_user["full_name"],
                    "purpose": request.get("purpose", "Resource request"),
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            
            update_data["allocated_resource_id"] = allocate_resource_id
            update_data["allocation_date"] = datetime.now(timezone.utc)
            
            # Log to resource history
            await resource_history_collection.insert_one({
                "resource_id": allocate_resource_id,
                "action": "allocated_for_request",
                "details": f"Allocated for resource request: {request['title']}",
                "changed_by": str(current_user["_id"]),
                "changed_by_name": current_user["full_name"],
                "changed_at": datetime.now(timezone.utc),
                "resource_request_id": request_id,
                "assignee_id": request["requested_by"],
                "assignee_name": request["requested_by_name"]
            })
        
        # Update request
        await resource_requests_collection.update_one(
            {"_id": ObjectId(request_id)},
            {"$set": update_data}
        )
        
        # Add comment
        if comments:
            comment = {
                "user_id": str(current_user["_id"]),
                "user_name": current_user["full_name"],
                "comment": f"Approved: {comments}",
                "timestamp": datetime.now(timezone.utc),
                "action": "approved"
            }
            
            await resource_requests_collection.update_one(
                {"_id": ObjectId(request_id)},
                {"$push": {"comments": comment}}
            )
        
        # Update linked approval if exists
        if request.get("approval_id"):
            await approvals_collection.update_one(
                {"_id": ObjectId(request["approval_id"])},
                {"$set": {
                    "status": "approved",
                    "action_taken_by": str(current_user["_id"]),
                    "action_taken_by_name": current_user["full_name"],
                    "action_taken_at": datetime.now(timezone.utc),
                    "action_comments": comments or "Request approved",
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
        
        # Send notification to requester
        await NotificationService.create_notification(
            user_id=request["requested_by"],
            title="✅ Resource Request Approved",
            message=f"Your resource request '{request['title']}' has been approved",
            notification_type="resource_request_update",
            priority="high",
            action_url=f"/resource-requests/{request_id}",
            data={
                "action": "approved",
                "comments": comments,
                "allocated_resource": allocate_resource_id is not None
            }
        )
        
        return {
            "success": True,
            "message": "Resource request approved successfully",
            "request_id": request_id,
            "allocated_resource": allocate_resource_id is not None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approve resource request error: {e}")
        raise HTTPException(status_code=500, detail="Failed to approve resource request")


@router.post("/api/hod/resource-requests/{request_id}/reject", tags=["HOD - Resources"])
async def reject_resource_request(
    request_id: str,
    reason: str = Form(...),
    suggestions: Optional[str] = Form(None),
    current_user: dict = Depends(verify_token)
):
    """Reject a resource request"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Get request
        request = await resource_requests_collection.find_one({
            "_id": ObjectId(request_id),
            "department": department
        })
        
        if not request:
            raise HTTPException(status_code=404, detail="Resource request not found")
        
        if request.get("status") != "pending":
            raise HTTPException(status_code=400, detail=f"Request is already {request.get('status')}")
        
        # Update request
        await resource_requests_collection.update_one(
            {"_id": ObjectId(request_id)},
            {"$set": {
                "status": "rejected",
                "approval_status": "rejected",
                "rejected_at": datetime.now(timezone.utc),
                "rejected_by": str(current_user["_id"]),
                "rejected_by_name": current_user["full_name"],
                "rejection_reason": reason,
                "rejection_suggestions": suggestions,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        # Add comment
        comment = {
            "user_id": str(current_user["_id"]),
            "user_name": current_user["full_name"],
            "comment": f"Rejected: {reason}. Suggestions: {suggestions or 'None'}",
            "timestamp": datetime.now(timezone.utc),
            "action": "rejected"
        }
        
        await resource_requests_collection.update_one(
            {"_id": ObjectId(request_id)},
            {"$push": {"comments": comment}}
        )
        
        # Update linked approval if exists
        if request.get("approval_id"):
            await approvals_collection.update_one(
                {"_id": ObjectId(request["approval_id"])},
                {"$set": {
                    "status": "rejected",
                    "action_taken_by": str(current_user["_id"]),
                    "action_taken_by_name": current_user["full_name"],
                    "action_taken_at": datetime.now(timezone.utc),
                    "action_comments": f"Rejected: {reason}",
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
        
        # Send notification to requester
        await NotificationService.create_notification(
            user_id=request["requested_by"],
            title="❌ Resource Request Rejected",
            message=f"Your resource request '{request['title']}' has been rejected. Reason: {reason}",
            notification_type="resource_request_update",
            priority="high",
            action_url=f"/resource-requests/{request_id}"
        )
        
        return {
            "success": True,
            "message": "Resource request rejected",
            "request_id": request_id,
            "reason": reason
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reject resource request error: {e}")
        raise HTTPException(status_code=500, detail="Failed to reject resource request")


@router.post("/api/hod/resource-requests/{request_id}/complete", tags=["HOD - Resources"])
async def complete_resource_request(
    request_id: str,
    actual_cost: Optional[float] = Form(None),
    completion_notes: Optional[str] = Form(None),
    current_user: dict = Depends(verify_token)
):
    """Mark resource request as completed"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Get request
        request = await resource_requests_collection.find_one({
            "_id": ObjectId(request_id),
            "department": department
        })
        
        if not request:
            raise HTTPException(status_code=404, detail="Resource request not found")
        
        if request.get("status") not in ["approved", "in_progress"]:
            raise HTTPException(status_code=400, detail="Only approved or in-progress requests can be completed")
        
        # Update request
        await resource_requests_collection.update_one(
            {"_id": ObjectId(request_id)},
            {"$set": {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc),
                "completed_by": str(current_user["_id"]),
                "completed_by_name": current_user["full_name"],
                "actual_cost": actual_cost,
                "completion_notes": completion_notes,
                "updated_at": datetime.now(timezone.utc),
                "resolved_at": datetime.now(timezone.utc)
            }}
        )
        
        # Add comment
        comment = {
            "user_id": str(current_user["_id"]),
            "user_name": current_user["full_name"],
            "comment": f"Completed: {completion_notes or 'Request fulfilled'}",
            "timestamp": datetime.now(timezone.utc),
            "action": "completed"
        }
        
        await resource_requests_collection.update_one(
            {"_id": ObjectId(request_id)},
            {"$push": {"comments": comment}}
        )
        
        # Send notification to requester
        await NotificationService.create_notification(
            user_id=request["requested_by"],
            title="🏁 Resource Request Completed",
            message=f"Your resource request '{request['title']}' has been completed",
            notification_type="resource_request_update",
            priority="medium",
            action_url=f"/resource-requests/{request_id}"
        )
        
        return {
            "success": True,
            "message": "Resource request marked as completed",
            "request_id": request_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Complete resource request error: {e}")
        raise HTTPException(status_code=500, detail="Failed to complete resource request")


@router.post("/api/hod/resource-requests/{request_id}/comment", tags=["HOD - Resources"])
async def add_request_comment(
    request_id: str,
    comment: str = Form(...),
    current_user: dict = Depends(verify_token)
):
    """Add comment to resource request"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Get request
        request = await resource_requests_collection.find_one({
            "_id": ObjectId(request_id),
            "department": department
        })
        
        if not request:
            raise HTTPException(status_code=404, detail="Resource request not found")
        
        # Create comment
        comment_obj = {
            "user_id": str(current_user["_id"]),
            "user_name": current_user["full_name"],
            "comment": comment,
            "timestamp": datetime.now(timezone.utc),
            "action": "comment"
        }
        
        await resource_requests_collection.update_one(
            {"_id": ObjectId(request_id)},
            {
                "$push": {"comments": comment_obj},
                "$set": {"updated_at": datetime.now(timezone.utc)}
            }
        )
        
        # Send notification to requester
        if request["requested_by"] != str(current_user["_id"]):
            await NotificationService.create_notification(
                user_id=request["requested_by"],
                title="💬 New Comment on Resource Request",
                message=f"HOD commented on your resource request '{request['title']}'",
                notification_type="resource_request_comment",
                priority="medium",
                action_url=f"/resource-requests/{request_id}"
            )
        
        return {
            "success": True,
            "message": "Comment added successfully",
            "comment": comment_obj
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add request comment error: {e}")
        raise HTTPException(status_code=500, detail="Failed to add comment")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.get("/api/hod/resource-requests", tags=["HOD - Resources"])
async def get_resource_requests(
    status: Optional[str] = Query(None, description="Filter by status"),
    request_type: Optional[str] = Query(None, description="Filter by request type"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    search: Optional[str] = Query(None, description="Search by title or description"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get resource requests with filtering"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Build query
        query = {"department": department}
        
        if status:
            query["status"] = status
        
        if request_type:
            query["resource_type"] = request_type
        
        if priority:
            query["priority"] = priority
        
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"description": {"$regex": search, "$options": "i"}},
                {"item_name": {"$regex": search, "$options": "i"}}
            ]
        
        # Get total count
        total = await resource_requests_collection.count_documents(query)
        
        # Get requests
        requests = await resource_requests_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        # Enrich with requester details
        enriched_requests = []
        for req in requests:
            # Get requester info
            requester = None
            if req.get("requested_by"):
                requester_data = await users_collection.find_one({"_id": ObjectId(req["requested_by"])})
                if requester_data:
                    requester = {
                        "name": requester_data["full_name"],
                        "email": requester_data["email"],
                        "designation": requester_data.get("designation", "User"),
                        "department": requester_data.get("department")
                    }
            
            # Get related approval if exists
            approval = None
            if req.get("approval_id"):
                approval_data = await approvals_collection.find_one({"_id": ObjectId(req["approval_id"])})
                if approval_data:
                    approval = {
                        "id": str(approval_data["_id"]),
                        "status": approval_data.get("status"),
                        "action_taken_at": approval_data.get("action_taken_at")
                    }
            
            enriched_requests.append({
                **convert_objectid_to_str(req),
                "requester_details": requester,
                "approval_info": approval,
                "days_open": (datetime.now(timezone.utc) - req["created_at"]).days if req.get("created_at") else 0,
                "is_overdue": req.get("priority") == "urgent" and (datetime.now(timezone.utc) - req["created_at"]).days > 3
            })
        
        # Get statistics
        stats = {
            "pending": await resource_requests_collection.count_documents({**query, "status": "pending"}),
            "approved": await resource_requests_collection.count_documents({**query, "status": "approved"}),
            "rejected": await resource_requests_collection.count_documents({**query, "status": "rejected"}),
            "in_progress": await resource_requests_collection.count_documents({**query, "status": "in_progress"})
        }
        
        return {
            "requests": enriched_requests,
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            },
            "statistics": stats,
            "filter_options": {
                "statuses": ["pending", "approved", "rejected", "in_progress", "completed"],
                "priorities": ["low", "medium", "high", "urgent"],
                "types": await resource_requests_collection.distinct("resource_type", {"department": department})
            }
        }
        
    except Exception as e:
        logger.error(f"Get resource requests error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resource requests")


