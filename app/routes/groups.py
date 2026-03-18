"""
EduSync Backend - Groups Routes
Modularized and deduplicated.
"""
import logging
import uuid
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from bson import ObjectId

from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form, Query, Body
from fastapi.responses import JSONResponse

from app.dependencies import get_current_user, verify_token, convert_objectid_to_str
from app.database import *
from app.models.group import *
from app.services.websocket_manager import WebSocketManager
from app.services.notification_service import NotificationService
from app.utils.helpers import validate_file, upload_to_cloud_storage

logger = logging.getLogger("edusync")

router = APIRouter(prefix="/api/groups", tags=["Groups"])

@router.post("/create", tags=["Groups"])
async def create_group(
    name: str = Form(...),
    description: str = Form(""),
    privacy: str = Form("public"),
    department: str = Form("General"),
    year: int = Form(1),
    current_user: dict = Depends(verify_token)
):
    """Create a new study group/team"""
    try:
        user_id = str(current_user["_id"])
        
        group = {
            "name": name,
            "description": description,
            "privacy": privacy,
            "department": department,
            "year": year,
            "owner_id": user_id,
            "owner_name": current_user.get("full_name", "Unknown"),
            "creator_id": user_id, # For compatibility
            "members": [user_id],
            "admins": [user_id],
            "max_members": 100,
            "is_educational": True,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "messages": [],
            "files": []
        }
        
        result = await groups_collection.insert_one(group)
        group["_id"] = str(result.inserted_id)
        
        return convert_objectid_to_str(group)
        
    except Exception as e:
        logger.error(f"Create group error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create group")

@router.get("", tags=["Groups"])
async def list_groups(
    public_only: bool = Query(False),
    current_user: dict = Depends(verify_token)
):
    """Get all groups for the current user and/or public groups"""
    try:
        user_id = str(current_user["_id"])
        
        query = {
            "$or": [
                {"creator_id": user_id},
                {"members": user_id}
            ]
        }
        
        if public_only:
            query["$or"].append({"privacy": "public"})
            
        groups = await groups_collection.find(query).sort("created_at", -1).to_list(100)
        
        for group in groups:
            group["is_member"] = user_id in group.get("members", [])
            group["member_count"] = len(group.get("members", []))
            
        return {"success": True, "groups": convert_objectid_to_str(groups)}
    except Exception as e:
        logger.error(f"List groups error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/discover", tags=["Groups"])
async def discover_groups(
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Find public groups that the user is not a member of"""
    try:
        user_id = str(current_user["_id"])
        
        query = {
            "privacy": "public",
            "members": {"$ne": user_id}
        }
        
        total = await groups_collection.count_documents(query)
        groups = await groups_collection.find(query) \
            .sort("created_at", -1) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
            
        return {
            "success": True,
            "groups": convert_objectid_to_str(groups),
            "total": total
        }
    except Exception as e:
        logger.error(f"Discover groups error: {e}")
        raise HTTPException(status_code=500, detail="Failed to discover groups")

@router.get("/{group_id}", tags=["Groups"])
async def get_group_detail(
    group_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get group details including member information"""
    try:
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        user_id = str(current_user["_id"])
        
        # Get member details
        member_ids = group.get("members", [])
        members_data = await users_collection.find(
            {"_id": {"$in": [ObjectId(mid) for mid in member_ids]}}
        ).to_list(100)
        
        members_list = [
            {
                "id": str(m["_id"]),
                "name": m.get("full_name", "Unknown"),
                "email": m.get("email", ""),
                "role": "Creator" if str(m["_id"]) == group.get("creator_id") else "Member"
            }
            for m in members_data
        ]
        
        group_data = convert_objectid_to_str(group)
        if group_data:
            group_data["members_list"] = members_list
            group_data["is_member"] = user_id in member_ids
        else:
            group_data = {"members_list": members_list, "is_member": user_id in member_ids}
        
        return {
            "success": True,
            "group": group_data
        }
    except Exception as e:
        logger.error(f"Get group detail error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{group_id}/join", tags=["Groups"])
async def join_group(
    group_id: str,
    current_user: dict = Depends(verify_token)
):
    """Join a study group (public only)"""
    try:
        user_id = str(current_user["_id"])
        
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
        
        if user_id in group.get("members", []):
            raise HTTPException(status_code=400, detail="Already a member")
        
        if group.get("privacy") != "public":
            raise HTTPException(status_code=403, detail="Joining private groups requires a request/invite")
        
        await groups_collection.update_one(
            {"_id": ObjectId(group_id)},
            {"$addToSet": {"members": user_id}}
        )
        
        return {"success": True, "message": "Joined successfully"}
    except Exception as e:
        logger.error(f"Join group error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{group_id}/request", tags=["Groups"])
async def request_to_join_group(
    group_id: str,
    current_user: dict = Depends(verify_token)
):
    """Request to join a private group"""
    try:
        user_id = str(current_user["_id"])
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
        
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")
            
        # Check if already has a pending request
        existing_request = await group_requests_collection.find_one({
            "group_id": group_id,
            "user_id": user_id,
            "status": "pending"
        })
        if existing_request:
            raise HTTPException(status_code=400, detail="Join request already pending")
            
        request_obj = {
            "group_id": group_id,
            "group_name": group["name"],
            "user_id": user_id,
            "user_name": current_user.get("full_name") or current_user.get("name"),
            "status": "pending",
            "type": "join_request",
            "created_at": datetime.now(timezone.utc)
        }
        
        result = await group_requests_collection.insert_one(request_obj)
        
        # Notify admins
        for admin_id in group.get("admins", []):
            await NotificationService.create_notification(
                user_id=admin_id,
                title="New Group Join Request",
                message=f"{request_obj['user_name']} requested to join {group['name']}",
                notification_type="group_request",
                data={"group_id": group_id, "request_id": str(result.inserted_id)}
            )
            
        return {"success": True, "message": "Join request sent successfully"}
    except Exception as e:
        logger.error(f"Join request error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{group_id}/requests", tags=["Groups"])
async def get_group_requests(
    group_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get pending join requests (Admins only)"""
    try:
        user_id = str(current_user["_id"])
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
        
        if not group or user_id not in group.get("admins", []):
            raise HTTPException(status_code=403, detail="Forbidden")
            
        requests = await group_requests_collection.find({
            "group_id": group_id,
            "status": "pending"
        }).to_list(100)
            
        return {"success": True, "requests": convert_objectid_to_str(requests)}
    except Exception as e:
        logger.error(f"Get requests error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{group_id}/requests/{request_id}/action", tags=["Groups"])
async def action_group_request(
    group_id: str,
    request_id: str,
    action: str = Body(..., embed=True), # "approve" or "reject"
    current_user: dict = Depends(verify_token)
):
    """Approve or reject a join request"""
    try:
        user_id = str(current_user["_id"])
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
        
        if not group or user_id not in group.get("admins", []):
            raise HTTPException(status_code=403, detail="Forbidden")
            
        request_obj = await group_requests_collection.find_one({"_id": ObjectId(request_id)})
        if not request_obj:
            raise HTTPException(status_code=404, detail="Request not found")
            
        if action == "approve":
            await groups_collection.update_one(
                {"_id": ObjectId(group_id)},
                {"$addToSet": {"members": request_obj["user_id"]}}
            )
            status_val = "approved"
        else:
            status_val = "rejected"
            
        await group_requests_collection.update_one(
            {"_id": ObjectId(request_id)},
            {"$set": {"status": status_val, "processed_at": datetime.now(timezone.utc)}}
        )
        
        return {"success": True, "message": f"Request {status_val}"}
    except Exception as e:
        logger.error(f"Action request error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{group_id}/messages", tags=["Groups"])
async def get_group_messages(
    group_id: str,
    current_user: dict = Depends(verify_token)
):
    """Get group messages"""
    try:
        user_id = str(current_user["_id"])
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
        
        if not group or user_id not in group.get("members", []):
            raise HTTPException(status_code=403, detail="Not a member")
        
        return {"success": True, "messages": group.get("messages", [])}
    except Exception as e:
        logger.error(f"Get messages error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{group_id}/send-message", tags=["Groups"])
async def send_group_message(
    group_id: str,
    content: str = Form(...),
    current_user: dict = Depends(verify_token)
):
    """Send a message to the group"""
    try:
        user_id = str(current_user["_id"])
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
        
        if not group or user_id not in group.get("members", []):
            raise HTTPException(status_code=403, detail="Not a member")
            
        msg = {
            "id": str(uuid.uuid4()),
            "sender_id": user_id,
            "sender_name": current_user.get("full_name", "Unknown"),
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        await groups_collection.update_one(
            {"_id": ObjectId(group_id)},
            {"$push": {"messages": msg}}
        )
        
        # Broadcast via WebSocket
        try:
             await WebSocketManager.broadcast_to_group(group_id, {
                "type": "new_message",
                "group_id": group_id,
                "message": msg
            })
        except: pass
            
        return {"success": True, "message": msg}
    except Exception as e:
        logger.error(f"Send message error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{group_id}/files", tags=["Groups"])
async def upload_group_file(
    group_id: str,
    file: UploadFile = File(...),
    description: str = Form(""),
    current_user: dict = Depends(verify_token)
):
    """Upload file to group"""
    try:
        user_id = str(current_user["_id"])
        group = await groups_collection.find_one({"_id": ObjectId(group_id)})
        if not group or user_id not in group.get("members", []):
            raise HTTPException(status_code=403, detail="Forbidden")
        
        content, file_size = await validate_file(file)
        
        upload_result = await upload_to_cloud_storage(
            content,
            f"group_{group_id}_{datetime.now().timestamp()}_{file.filename}",
            file.content_type or "application/octet-stream"
        )
        
        file_record = {
            "id": str(uuid.uuid4()),
            "name": file.filename,
            "url": upload_result["url"],
            "uploaded_by": user_id,
            "uploaded_by_name": current_user["full_name"],
            "description": description,
            "size": file_size,
            "type": file.content_type,
            "uploaded_at": datetime.now(timezone.utc)
        }
        
        await groups_collection.update_one(
            {"_id": ObjectId(group_id)},
            {"$push": {"files": file_record}}
        )
        
        return {"success": True, "file": file_record}
    except Exception as e:
        logger.error(f"Upload record error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
