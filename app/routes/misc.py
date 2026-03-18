"""
EduSync Backend - Misc Routes
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
from app.services.notification_service import NotificationService
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

router = APIRouter(tags=["Misc"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/approvals/request", tags=["Approvals"])
async def create_approval_request(
    request_data: ApprovalRequest,
    current_user: dict = Depends(verify_token)
):
    """Create a new approval request"""
    try:
        user_id = str(current_user["_id"])
        
        # Check if user can make requests
        if current_user["user_type"] not in [UserType.FACULTY.value, UserType.STUDENT.value, UserType.HOD.value]:
            raise HTTPException(status_code=403, detail="Not authorized to create approval requests")
        
        approval = {
            "title": request_data.title,
            "description": request_data.description,
            "approval_type": request_data.approval_type.value,
            "priority": request_data.priority.value,
            "department": request_data.department,
            "requested_by": user_id,
            "requested_by_name": current_user["full_name"],
            "requested_by_email": current_user["email"],
            "requested_by_role": current_user["user_type"],
            "due_date": request_data.due_date,
            "metadata": request_data.metadata,
            "attachments": request_data.attachments,
            "approvers": request_data.approvers or [current_user.get("hod_id", "hod")],  # Default to HOD
            "current_approver": request_data.approvers[0] if request_data.approvers else "hod",
            "status": ApprovalStatus.PENDING.value,
            "comments": request_data.comments or [],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "history": [{
                "action": "created",
                "by": user_id,
                "by_name": current_user["full_name"],
                "timestamp": datetime.now(timezone.utc),
                "notes": "Request submitted"
            }]
        }
        
        result = await approvals_collection.insert_one(approval)
        approval_id = str(result.inserted_id)
        
        # Send notifications to approvers
        for approver_id in approval["approvers"]:
            await NotificationService.create_notification(
                user_id=approver_id,
                title=f"New Approval Request: {request_data.title}",
                message=f"New {request_data.approval_type.value} request from {current_user['full_name']}",
                notification_type="approval",
                priority=request_data.priority.value,
                action_url=f"/hod/approvals/{approval_id}",
                data={
                    "approval_id": approval_id,
                    "approval_type": request_data.approval_type.value,
                    "requester": current_user["full_name"]
                }
            )
        
        return {
            "message": "Approval request created successfully",
            "approval_id": approval_id,
            "approval": convert_objectid_to_str(approval)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create approval request error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create approval request")


@router.post("/api/approvals/faculty-community", tags=["Approvals"])
async def request_faculty_community(
    community_data: FacultyCommunityRequest,
    current_user: dict = Depends(verify_token)
):
    """Request creation of faculty community (requires HOD approval)"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        # Get HOD for department
        hod = await users_collection.find_one({
            "user_type": UserType.HOD.value,
            "department": current_user["department"]
        })
        
        if not hod:
            raise HTTPException(status_code=404, detail="HOD not found for department")
        
        approval_data = {
            "title": f"Faculty Community: {community_data.community_name}",
            "description": f"Request to create {community_data.community_type} community.\n\nPurpose: {community_data.purpose}\n\nDuration: {community_data.duration_days} days\nPrivacy: {community_data.privacy}\nMembers: {len(community_data.members)} faculty members",
            "approval_type": ApprovalType.FACULTY_COMMUNITY.value,
            "priority": ApprovalPriority.MEDIUM.value,
            "department": current_user["department"],
            "requested_by": user_id,
            "requested_by_name": current_user["full_name"],
            "metadata": {
                "community_data": community_data.dict(),
                "community_type": community_data.community_type,
                "expected_members": len(community_data.members),
                "duration_days": community_data.duration_days
            },
            "attachments": [],
            "approvers": [str(hod["_id"])]
        }
        
        # Create the approval request
        result = await create_approval_request_internal(approval_data, current_user)
        
        return {
            "message": "Faculty community request submitted for HOD approval",
            "approval_id": result["approval_id"],
            "community_name": community_data.community_name,
            "hod_name": hod["full_name"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Faculty community request error: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit community request")


@router.post("/api/approvals/faculty-leave", tags=["Approvals"])
async def request_faculty_leave(
    leave_data: FacultyLeaveRequest,
    current_user: dict = Depends(verify_token)
):
    """Request faculty leave (requires HOD approval)"""
    try:
        if current_user["user_type"] != UserType.FACULTY.value:
            raise HTTPException(status_code=403, detail="For faculty only")
        
        user_id = str(current_user["_id"])
        
        # Calculate leave days
        start_date = leave_data.start_date
        end_date = leave_data.end_date
        leave_days = (end_date - start_date).days + 1
        
        # Get HOD for department
        hod = await users_collection.find_one({
            "user_type": UserType.HOD.value,
            "department": current_user["department"]
        })
        
        approval_data = {
            "title": f"Leave Request: {current_user['full_name']}",
            "description": f"Leave Type: {leave_data.leave_type}\n\nPeriod: {start_date} to {end_date} ({leave_days} days)\n\nReason: {leave_data.reason}\n\nEmergency Contact: {leave_data.emergency_contact or 'Not provided'}",
            "approval_type": ApprovalType.FACULTY_LEAVE.value,
            "priority": ApprovalPriority.HIGH.value if leave_days > 7 else ApprovalPriority.MEDIUM.value,
            "department": current_user["department"],
            "requested_by": user_id,
            "requested_by_name": current_user["full_name"],
            "due_date": start_date,
            "metadata": {
                "leave_data": leave_data.dict(),
                "leave_days": leave_days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "has_substitute": leave_data.assign_substitute
            },
            "attachments": leave_data.attachments,
            "approvers": [str(hod["_id"])] if hod else []
        }
        
        result = await create_approval_request_internal(approval_data, current_user)
        
        return {
            "message": "Leave request submitted for HOD approval",
            "approval_id": result["approval_id"],
            "leave_days": leave_days,
            "hod_name": hod["full_name"] if hod else "HOD"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Faculty leave request error: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit leave request")


@router.post("/api/approvals/resource-request", tags=["Approvals"])
async def request_resource(
    resource_data: ResourceRequest,
    current_user: dict = Depends(verify_token)
):
    """Request department resources"""
    try:
        user_id = str(current_user["_id"])
        
        # Get HOD for department
        hod = await users_collection.find_one({
            "user_type": UserType.HOD.value,
            "department": current_user["department"]
        })
        
        if not hod:
            raise HTTPException(status_code=400, detail="No HOD found for your department")
        
        approval_data = {
            "title": f"Resource Request: {resource_data.item_name}",
            "description": f"Resource Type: {resource_data.resource_type}\n\nQuantity: {resource_data.quantity}\n\nPurpose: {resource_data.purpose}\n\nUrgency: {resource_data.urgency}\n\nEstimated Cost: {resource_data.estimated_cost or 'Not specified'}",
            "approval_type": ApprovalType.RESOURCE_REQUEST.value,
            "priority": ApprovalPriority.URGENT.value if resource_data.urgency == "critical" else ApprovalPriority.HIGH.value,
            "department": current_user["department"],
            "requested_by": user_id,
            "requested_by_name": current_user["full_name"],
            "metadata": {
                "resource_data": resource_data.dict(),
                "estimated_cost": resource_data.estimated_cost,
                "vendor_details": resource_data.vendor_details
            },
            "attachments": resource_data.attachments,
            "approvers": [str(hod["_id"])]
        }
        
        result = await create_approval_request_internal(approval_data, current_user)
        
        return {
            "message": "Resource request submitted for HOD approval",
            "approval_id": result["approval_id"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resource request error: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit resource request")




