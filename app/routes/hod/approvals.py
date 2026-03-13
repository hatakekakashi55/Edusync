"""
EduSync Backend - HOD - Approvals Routes
Modularized and deduplicated.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends, status, Form, Query, Body

from app.dependencies import verify_token, convert_objectid_to_str
from app.database import *
from app.models.auth import UserType
from app.models.hod import ApprovalStatus, ApprovalType, ApprovalAction
from app.services.notification_service import NotificationService
from app.utils.helpers import execute_approved_action, get_approval_statistics, get_pending_by_type_counts, update_approval_statistics

logger = logging.getLogger("edusync")

router = APIRouter(prefix="/api/hod/approvals", tags=["HOD - Approvals"])

@router.get("/statistics", tags=["HOD - Approvals"])
async def get_approval_stats(
    period: str = Query("month", pattern="^(day|week|month|quarter|year)$"),
    current_user: dict = Depends(verify_token)
):
    """Get approval statistics for HOD"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        user_id = str(current_user["_id"])
        department = current_user["department"]
        
        stats = await get_approval_statistics(user_id, period)
        
        # Get recent activity
        recent_activity = await approvals_collection.find({
            "department": department,
            "status": {"$ne": ApprovalStatus.PENDING.value}
        }).sort("updated_at", -1).limit(10).to_list(10)
        
        return {
            "success": True,
            "statistics": stats,
            "recent_activity": convert_objectid_to_str(recent_activity),
            "period": period
        }
    except Exception as e:
        logger.error(f"Get approval statistics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get approval statistics")

@router.get("", tags=["HOD - Approvals"])
async def list_approvals(
    status: Optional[str] = None,
    approval_type: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get all approvals for HOD with filters"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        user_id = str(current_user["_id"])
        department = current_user.get("department")
        
        query = {"$or": [{"approvers": user_id}, {"department": department}]}
        
        if status:
            query["status"] = status
        if approval_type:
            query["approval_type"] = approval_type
        if priority:
            query["priority"] = priority
            
        if search:
            query["$or"] = [
                {"title": {"$regex": search, "$options": "i"}},
                {"requested_by_name": {"$regex": search, "$options": "i"}}
            ]
        
        total = await approvals_collection.count_documents(query)
        approvals = await approvals_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
            
        return {
            "success": True,
            "approvals": convert_objectid_to_str(approvals),
            "total": total
        }
    except Exception as e:
        logger.error(f"List approvals error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pending", tags=["HOD - Approvals"])
async def get_pending_approvals(
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Specific endpoint for pending approvals"""
    return await list_approvals(status=ApprovalStatus.PENDING.value, limit=limit, skip=skip, current_user=current_user)

@router.get("/{approval_id}", tags=["HOD - Approvals"])
async def get_approval_detail(
    approval_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get detailed approval info"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
            
        approval = await approvals_collection.find_one({"_id": ObjectId(approval_id)})
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
            
        return {
            "success": True,
            "approval": convert_objectid_to_str(approval)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{approval_id}/action", tags=["HOD - Approvals"])
async def process_approval(
    approval_id: str,
    action_data: ApprovalAction,
    current_user: dict = Depends(verify_token)
):
    """Approve or reject a request"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        user_id = str(current_user["_id"])
        approval = await approvals_collection.find_one({"_id": ObjectId(approval_id)})
        
        if not approval:
            raise HTTPException(status_code=404, detail="Approval not found")
            
        # Update logic
        update_doc = {
            "status": action_data.action.value,
            "action_taken_by": user_id,
            "action_taken_at": datetime.now(timezone.utc),
            "action_comments": action_data.comments,
            "updated_at": datetime.now(timezone.utc)
        }
        
        await approvals_collection.update_one(
            {"_id": ObjectId(approval_id)},
            {"$set": update_doc}
        )
        
        # Execute action if approved
        if action_data.action == ApprovalStatus.APPROVED:
            await execute_approved_action(approval, current_user)
            
        # Notify requester
        await NotificationService.create_notification(
            user_id=approval["requested_by"],
            title=f"Request {action_data.action.value.capitalize()}",
            message=f"Your request '{approval['title']}' has been {action_data.action.value}.",
            notification_type="approval_update"
        )
        
        return {
            "success": True,
            "message": f"Approval {action_data.action.value} successfully"
        }
    except Exception as e:
        logger.error(f"Process approval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
