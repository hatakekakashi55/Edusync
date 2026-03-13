"""
EduSync Backend - HOD - Software Licenses Routes
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

router = APIRouter(tags=["HOD - Software Licenses"])

# Note: Use get_redis_client() instead of redis_client
# Note: Use get_executor() instead of executor

@router.post("/api/hod/software-licenses", tags=["HOD - Resources"])
async def create_software_license(
    license_data: SoftwareLicenseCreate,
    current_user: dict = Depends(verify_token)
):
    """Create a new software license"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Check for duplicate license key
        if license_data.license_key:
            existing = await software_licenses_collection.find_one({
                "license_key": license_data.license_key,
                "department": department
            })
            if existing:
                raise HTTPException(status_code=400, detail="License key already exists")
        
        # Create license
        license = {
            "name": license_data.name,
            "version": license_data.version,
            "license_type": license_data.license_type,
            "license_key": license_data.license_key,
            "max_users": license_data.max_users,
            "expiry_date": license_data.expiry_date,
            "vendor": license_data.vendor,
            "cost": license_data.cost,
            "notes": license_data.notes,
            "department": department,
            "created_by": str(current_user["_id"]),
            "created_by_name": current_user["full_name"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "status": "active",
            "purchase_date": datetime.now(timezone.utc).isoformat(),
            "renewal_count": 0,
            "current_users": 0
        }
        
        result = await software_licenses_collection.insert_one(license)
        license_id = str(result.inserted_id)
        
        # Send notification
        await NotificationService.create_notification(
            user_id=str(current_user["_id"]),
            title="📄 Software License Added",
            message=f"Software license '{license_data.name}' has been added",
            notification_type="software_license",
            priority="medium"
        )
        
        return {
            "success": True,
            "message": "Software license created successfully",
            "license_id": license_id,
            "license": convert_objectid_to_str(license)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create software license error: {e}")
        raise HTTPException(status_code=500, detail="Failed to create software license")


@router.get("/api/hod/software-licenses/stats", tags=["HOD - Resources"])
async def get_software_licenses_stats(
    current_user: dict = Depends(verify_token)
):
    """Get software licenses dashboard statistics"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Get all licenses
        licenses = await software_licenses_collection.find({"department": department}).to_list(100)
        
        now = datetime.now(timezone.utc)
        
        # Calculate statistics
        total_licenses = len(licenses)
        active_licenses = 0
        expiring_soon = 0
        expired_licenses = 0
        total_cost = 0
        total_users = 0
        
        for license in licenses:
            # Check status
            if license.get("expiry_date"):
                try:
                    expiry_date = datetime.fromisoformat(license["expiry_date"].replace('Z', '+00:00'))
                    days_remaining = (expiry_date - now).days
                    
                    if days_remaining >= 0:
                        active_licenses += 1
                        if days_remaining < 30:
                            expiring_soon += 1
                    else:
                        expired_licenses += 1
                except:
                    active_licenses += 1
            else:
                active_licenses += 1
            
            # Add cost
            if license.get("cost"):
                total_cost += license["cost"]
            
            # Add users
            if license.get("max_users"):
                total_users += license["max_users"]
        
        # Get licenses by type
        licenses_by_type = {}
        for license in licenses:
            license_type = license.get("license_type", "unknown")
            if license_type not in licenses_by_type:
                licenses_by_type[license_type] = 0
            licenses_by_type[license_type] += 1
        
        # Get upcoming renewals (next 30 days)
        upcoming_renewals = []
        for license in licenses:
            if license.get("expiry_date"):
                try:
                    expiry_date = datetime.fromisoformat(license["expiry_date"].replace('Z', '+00:00'))
                    days_remaining = (expiry_date - now).days
                    if 0 <= days_remaining <= 30:
                        upcoming_renewals.append({
                            "name": license["name"],
                            "expiry_date": license["expiry_date"],
                            "days_remaining": days_remaining,
                            "vendor": license.get("vendor"),
                            "cost": license.get("cost")
                        })
                except:
                    pass
        
        # Sort by days remaining
        upcoming_renewals.sort(key=lambda x: x["days_remaining"])
        
        # Get most used licenses (by user count)
        most_used = []
        for license in licenses:
            if license.get("max_users"):
                most_used.append({
                    "name": license["name"],
                    "max_users": license["max_users"],
                    "utilization_percentage": random.randint(60, 95)  # Simulated utilization
                })
        
        most_used.sort(key=lambda x: x["utilization_percentage"], reverse=True)
        
        return {
            "summary": {
                "total_licenses": total_licenses,
                "active_licenses": active_licenses,
                "expiring_soon": expiring_soon,
                "expired_licenses": expired_licenses,
                "total_cost": total_cost,
                "total_users": total_users,
                "avg_cost_per_license": total_cost / total_licenses if total_licenses > 0 else 0
            },
            "licenses_by_type": licenses_by_type,
            "upcoming_renewals": upcoming_renewals[:5],  # Top 5
            "most_used_licenses": most_used[:5],  # Top 5
            "renewal_timeline": get_renewal_timeline(licenses)
        }
        
    except Exception as e:
        logger.error(f"Get software licenses stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get software licenses statistics")


@router.delete("/api/hod/software-licenses/{license_id}", tags=["HOD - Resources"])
async def delete_software_license(
    license_id: str,
    current_user: dict = Depends(verify_token)
):
    """Delete a software license"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Check if license exists
        license = await software_licenses_collection.find_one({
            "_id": ObjectId(license_id),
            "department": department
        })
        
        if not license:
            raise HTTPException(status_code=404, detail="Software license not found")
        
        # Soft delete by marking as archived
        await software_licenses_collection.update_one(
            {"_id": ObjectId(license_id)},
            {"$set": {
                "status": "archived",
                "archived_at": datetime.now(timezone.utc),
                "archived_by": str(current_user["_id"]),
                "archived_by_name": current_user["full_name"],
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        return {
            "success": True,
            "message": "Software license archived successfully",
            "license_id": license_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete software license error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete software license")


@router.post("/api/hod/software-licenses/{license_id}/renew", tags=["HOD - Resources"])
async def renew_software_license(
    license_id: str,
    new_expiry_date: str = Form(...),
    renewal_cost: Optional[float] = Form(None),
    notes: Optional[str] = Form(None),
    current_user: dict = Depends(verify_token)
):
    """Renew a software license"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Check if license exists
        license = await software_licenses_collection.find_one({
            "_id": ObjectId(license_id),
            "department": department
        })
        
        if not license:
            raise HTTPException(status_code=404, detail="Software license not found")
        
        # Log renewal
        renewal_record = {
            "license_id": license_id,
            "license_name": license["name"],
            "previous_expiry": license.get("expiry_date"),
            "new_expiry": new_expiry_date,
            "renewal_cost": renewal_cost,
            "renewed_by": str(current_user["_id"]),
            "renewed_by_name": current_user["full_name"],
            "renewed_at": datetime.now(timezone.utc),
            "notes": notes,
            "department": department
        }
        
        await db.license_renewals.insert_one(renewal_record)
        
        # Update license
        update_data = {
            "expiry_date": new_expiry_date,
            "renewal_count": (license.get("renewal_count", 0) + 1),
            "last_renewal": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc),
            "updated_by": str(current_user["_id"]),
            "updated_by_name": current_user["full_name"]
        }
        
        if renewal_cost:
            update_data["cost"] = (license.get("cost", 0) or 0) + renewal_cost
        
        await software_licenses_collection.update_one(
            {"_id": ObjectId(license_id)},
            {"$set": update_data}
        )
        
        # Send notification
        await NotificationService.create_notification(
            user_id=str(current_user["_id"]),
            title="🔄 Software License Renewed",
            message=f"Software license '{license['name']}' has been renewed until {new_expiry_date}",
            notification_type="software_license_renewal",
            priority="medium"
        )
        
        return {
            "success": True,
            "message": "Software license renewed successfully",
            "license_id": license_id,
            "renewal": renewal_record
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Renew software license error: {e}")
        raise HTTPException(status_code=500, detail="Failed to renew software license")




# ========== RECOVERED MISSING ENDPOINTS ==========

@router.get("/api/hod/software-licenses", tags=["HOD - Resources"])
async def get_software_licenses(
    license_type: Optional[str] = Query(None, description="Filter by license type"),
    status: Optional[str] = Query(None, description="Filter by status: active, expired, expiring_soon"),
    search: Optional[str] = Query(None, description="Search by name or vendor"),
    sort_by: str = Query("name", description="Sort field"),
    sort_order: str = Query("asc", description="Sort order"),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token)
):
    """Get software licenses with filtering"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Build query
        query = {"department": department}
        
        if license_type:
            query["license_type"] = license_type
        
        if search:
            query["$or"] = [
                {"name": {"$regex": search, "$options": "i"}},
                {"vendor": {"$regex": search, "$options": "i"}},
                {"license_key": {"$regex": search, "$options": "i"}}
            ]
        
        # Get total count
        total = await software_licenses_collection.count_documents(query)
        
        # Determine sort direction
        sort_direction = 1 if sort_order == "asc" else -1
        
        # Get licenses
        licenses = await software_licenses_collection.find(query) \
            .sort(sort_by, sort_direction) \
            .skip(skip) \
            .limit(limit) \
            .to_list(limit)
        
        # Process licenses to add status and expiry info
        processed_licenses = []
        now = datetime.now(timezone.utc)
        
        for license in licenses:
            # Determine status based on expiry date
            status_info = {"status": "active", "message": ""}
            if license.get("expiry_date"):
                try:
                    expiry_date = datetime.fromisoformat(license["expiry_date"].replace('Z', '+00:00'))
                    days_remaining = (expiry_date - now).days
                    
                    if days_remaining < 0:
                        status_info = {"status": "expired", "message": f"Expired {-days_remaining} days ago"}
                    elif days_remaining < 30:
                        status_info = {"status": "expiring_soon", "message": f"Expires in {days_remaining} days"}
                    else:
                        status_info = {"status": "active", "message": f"Valid for {days_remaining} days"}
                except:
                    status_info = {"status": "active", "message": "No expiry date"}
            
            # Calculate utilization if max_users specified
            utilization = None
            if license.get("max_users"):
                # Get current users (simulated - in real app, track actual usage)
                current_users = random.randint(1, min(license["max_users"], 10))
                utilization = {
                    "current": current_users,
                    "max": license["max_users"],
                    "percentage": round((current_users / license["max_users"]) * 100, 1),
                    "available": license["max_users"] - current_users
                }
            
            # Get renewal history
            renewal_history = await get_license_renewal_history(str(license["_id"]))
            
            processed_licenses.append({
                **convert_objectid_to_str(license),
                **status_info,
                "utilization": utilization,
                "renewal_history": renewal_history,
                "is_expiring_soon": status_info["status"] == "expiring_soon",
                "is_expired": status_info["status"] == "expired"
            })
        
        # Apply status filter after processing
        if status:
            if status == "active":
                processed_licenses = [l for l in processed_licenses if l["status"] == "active"]
            elif status == "expired":
                processed_licenses = [l for l in processed_licenses if l["status"] == "expired"]
            elif status == "expiring_soon":
                processed_licenses = [l for l in processed_licenses if l["status"] == "expiring_soon"]
        
        # Get statistics
        stats = {
            "total": total,
            "active": len([l for l in processed_licenses if l["status"] == "active"]),
            "expired": len([l for l in processed_licenses if l["status"] == "expired"]),
            "expiring_soon": len([l for l in processed_licenses if l["status"] == "expiring_soon"]),
            "by_type": await get_licenses_by_type(department),
            "total_cost": sum(l.get("cost", 0) for l in licenses if l.get("cost")),
            "renewals_this_month": await count_renewals_this_month(department)
        }
        
        return {
            "licenses": processed_licenses,
            "pagination": {
                "total": total,
                "limit": limit,
                "skip": skip,
                "has_more": (skip + limit) < total
            },
            "statistics": stats,
            "filter_options": {
                "license_types": await software_licenses_collection.distinct("license_type", {"department": department}),
                "vendors": await software_licenses_collection.distinct("vendor", {"department": department})
            }
        }
        
    except Exception as e:
        logger.error(f"Get software licenses error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get software licenses")


@router.put("/api/hod/software-licenses/{license_id}", tags=["HOD - Resources"])
async def update_software_license(
    license_id: str,
    license_data: dict,
    current_user: dict = Depends(verify_token)
):
    """Update software license information"""
    try:
        if current_user["user_type"] != UserType.HOD.value:
            raise HTTPException(status_code=403, detail="For HOD only")
        
        department = current_user["department"]
        
        # Check if license exists
        license = await software_licenses_collection.find_one({
            "_id": ObjectId(license_id),
            "department": department
        })
        
        if not license:
            raise HTTPException(status_code=404, detail="Software license not found")
        
        # Check for duplicate license key if updating
        if license_data.get("license_key") and license_data["license_key"] != license.get("license_key"):
            existing = await software_licenses_collection.find_one({
                "license_key": license_data["license_key"],
                "department": department,
                "_id": {"$ne": ObjectId(license_id)}
            })
            if existing:
                raise HTTPException(status_code=400, detail="License key already exists")
        
        # Prepare update data
        update_data = {
            **license_data,
            "updated_at": datetime.now(timezone.utc),
            "updated_by": str(current_user["_id"]),
            "updated_by_name": current_user["full_name"]
        }
        
        # If renewing license (updating expiry date)
        if "expiry_date" in license_data and license_data["expiry_date"] != license.get("expiry_date"):
            update_data["renewal_count"] = (license.get("renewal_count", 0) + 1)
            update_data["last_renewal"] = datetime.now(timezone.utc).isoformat()
            
            # Log renewal
            await db.license_renewals.insert_one({
                "license_id": license_id,
                "previous_expiry": license.get("expiry_date"),
                "new_expiry": license_data["expiry_date"],
                "renewed_by": str(current_user["_id"]),
                "renewed_by_name": current_user["full_name"],
                "renewed_at": datetime.now(timezone.utc),
                "notes": f"License renewed via update"
            })
        
        # Update license
        await software_licenses_collection.update_one(
            {"_id": ObjectId(license_id)},
            {"$set": update_data}
        )
        
        return {
            "success": True,
            "message": "Software license updated successfully",
            "license_id": license_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update software license error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update software license")