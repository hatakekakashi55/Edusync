import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from app.database import *
from app.dependencies import get_current_user, verify_token
from app.models.auth import UserType
from app.routes.health import health_check

logger = logging.getLogger("edusync")

router = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.get("/stats", tags=["Admin"])
async def get_admin_stats(current_user: dict = Depends(verify_token)):
    """Get admin statistics"""
    try:
        # Check if user is admin
        if current_user["user_type"] not in [UserType.ADMIN, UserType.HOD]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get total counts
        total_users = await users_collection.count_documents({})
        total_students = await users_collection.count_documents({"user_type": UserType.STUDENT.value})
        total_challenges = await challenges_collection.count_documents({})
        total_submissions = await submissions_collection.count_documents({})
        total_groups = await groups_collection.count_documents({})
        total_projects = await projects_collection.count_documents({})
        total_repositories = await code_repositories_collection.count_documents({})
        
        # Get daily active users (last 24 hours)
        day_ago = datetime.now(timezone.utc) - timedelta(days=1)
        daily_active_users = await users_collection.count_documents({
            "last_active": {"$gte": day_ago}
        })
        
        # Get completion rates
        completed_submissions = await submissions_collection.count_documents({"completed": True})
        completion_rate = (completed_submissions / total_submissions * 100) if total_submissions > 0 else 0
        
        # Get user growth (last 30 days)
        month_ago = datetime.now(timezone.utc) - timedelta(days=30)
        new_users = await users_collection.count_documents({
            "created_at": {"$gte": month_ago}
        })
        
        # Get challenge completion by stage
        pipeline = [
            {"$match": {"completed": True}},
            {"$lookup": {
                "from": "challenges",
                "localField": "challenge_id",
                "foreignField": "_id",
                "as": "challenge"
            }},
            {"$unwind": "$challenge"},
            {"$group": {
                "_id": "$challenge.stage",
                "count": {"$sum": 1}
            }}
        ]
        
        stage_completion = list(await submissions_collection.aggregate(pipeline).to_list(length=None))
        
        # Get system health
        system_health = await health_check()
        
        return {
            "summary": {
                "total_users": total_users,
                "total_students": total_students,
                "total_challenges": total_challenges,
                "total_submissions": total_submissions,
                "total_groups": total_groups,
                "total_projects": total_projects,
                "total_repositories": total_repositories,
                "daily_active_users": daily_active_users,
                "completion_rate": round(completion_rate, 2),
                "new_users_last_30_days": new_users
            },
            "stage_completion": {
                stage["_id"]: stage["count"] for stage in stage_completion
            },
            "system_health": system_health,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get admin stats error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get admin statistics")


@router.get("/transactions", tags=["Admin"])
async def get_credit_transactions(current_user: dict = Depends(verify_token)):
    """Get credit transactions"""
    try:
        if current_user.get("user_type") not in ["admin", "hod"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get transactions (assuming a credit_transactions collection exists)
        transactions = await db["credit_transactions"].find().sort("created_at", -1).to_list(length=100)
        
        for transaction in transactions:
            transaction["_id"] = str(transaction["_id"])
        
        return {"transactions": transactions}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get transactions error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch transactions")
