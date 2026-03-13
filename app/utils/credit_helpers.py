"""
EduSync Backend - Credit Helpers
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


async def get_license_renewal_history(license_id: str):
    """Get renewal history for a license"""
    return await db.license_renewals.find({"license_id": license_id}) \
        .sort("renewed_at", -1) \
        .limit(5) \
        .to_list(5)

async def get_licenses_by_type(department: str):
    """Get license count by type"""
    pipeline = [
        {"$match": {"department": department}},
        {"$group": {
            "_id": "$license_type",
            "count": {"$sum": 1},
            "total_cost": {"$sum": "$cost"}
        }}
    ]
    
    return list(await software_licenses_collection.aggregate(pipeline).to_list(10))

async def count_renewals_this_month(department: str):
    """Count renewals in current month"""
    now = datetime.now(timezone.utc)
    start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    
    return await db.license_renewals.count_documents({
        "department": department,
        "renewed_at": {"$gte": start_of_month}
    })

def get_renewal_timeline(licenses):
    """Get renewal timeline for next 6 months"""
    now = datetime.now(timezone.utc)
    timeline = []
    
    for license in licenses:
        if license.get("expiry_date"):
            try:
                expiry_date = datetime.fromisoformat(license["expiry_date"].replace('Z', '+00:00'))
                months_until_expiry = (expiry_date.year - now.year) * 12 + (expiry_date.month - now.month)
                
                if 0 <= months_until_expiry <= 6:
                    timeline.append({
                        "name": license["name"],
                        "expiry_date": license["expiry_date"],
                        "months_until": months_until_expiry,
                        "vendor": license.get("vendor")
                    })
            except:
                pass
    
    timeline.sort(key=lambda x: x["months_until"])
    return timeline[:10]  # Return top 10

async def count_overdue_maintenance(department: str):
    """Count overdue maintenance records"""
    now = datetime.now(timezone.utc).isoformat()
    
    return await maintenance_collection.count_documents({
        "department": department,
        "status": {"$in": ["pending", "in_progress"]},
        "scheduled_date": {"$lt": now}
    })

async def get_maintenance_by_type(department: str):
    """Get maintenance count by type"""
    pipeline = [
        {"$match": {"department": department}},
        {"$group": {
            "_id": "$maintenance_type",
            "count": {"$sum": 1},
            "avg_hours": {"$avg": "$actual_hours"}
        }}
    ]
    
    return list(await maintenance_collection.aggregate(pipeline).to_list(10))

async def get_maintenance_by_priority(department: str):
    """Get maintenance count by priority"""
    pipeline = [
        {"$match": {"department": department}},
        {"$group": {
            "_id": "$priority",
            "count": {"$sum": 1},
            "completed": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}}
        }}
    ]
    
    return list(await maintenance_collection.aggregate(pipeline).to_list(10))

async def get_maintenance_priority_distribution(department: str):
    """Get maintenance priority distribution"""
    pipeline = [
        {"$match": {"department": department}},
        {"$group": {
            "_id": "$priority",
            "count": {"$sum": 1}
        }}
    ]
    
    result = list(await maintenance_collection.aggregate(pipeline).to_list(10))
    return {item["_id"]: item["count"] for item in result}

def calculate_days_difference(date_str, reference_date):
    """Calculate days difference between date string and reference date"""
    if not date_str:
        return None
    
    try:
        date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        diff = (date - reference_date).days
        return diff
    except:
        return None
    
