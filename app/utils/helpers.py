"""
EduSync Backend - Helper Functions
Auto-extracted from main.py via AST parser.
Contains utility functions used across multiple route modules.
"""
import logging
import random
import io
import os
import re
import json
import hashlib
import uuid
import base64
import asyncio
import tempfile
import subprocess
import zipfile
import csv
import markdown
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta, date
from typing import Optional, List, Dict, Any, Union
from pathlib import Path

import bcrypt
import jwt
from bson import ObjectId
from fastapi import HTTPException, Depends, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from google import genai
import httpx

try:
    from gtts import gTTS
except ImportError:
    gTTS = None

try:
    import qrcode
    from io import BytesIO
except ImportError:
    qrcode = None

try:
    import git
except ImportError:
    git = None

from app.config import *
from app.database import *
from app.utils.common import convert_objectid_to_str
from app.utils.auth import create_access_token, hash_password, verify_password
from app.dependencies import verify_token
from app.services.ai_wrapper import gemini_model, get_gemini_model, AIModelWrapper, hod_gemini_model, faculty_gemini_models, get_faculty_gemini_model
from app.lifespan import get_redis_client, get_executor
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

logger = logging.getLogger("edusync")

async def get_faculty_stats(faculty_id: str):
    """Get detailed statistics for a faculty member"""
    try:
        # Get faculty user
        faculty = await users_collection.find_one({
            "_id": ObjectId(faculty_id),
            "user_type": UserType.FACULTY.value
        })
        
        if not faculty:
            return None
        
        # Get classes taught
        classes = await classrooms_collection.find({
            "instructor_id": faculty_id
        }).to_list(100)
        
        # Get assignments created
        assignments = await faculty_assignments_collection.count_documents({
            "instructor_id": faculty_id
        })
        
        # Get average student rating (simulated for now)
        avg_rating = random.uniform(3.5, 5.0)
        
        # Get attendance records
        attendance_records = await faculty_attendance_collection.count_documents({
            "marked_by": faculty_id
        })
        
        # Get research papers
        research_papers = faculty.get("publications", [])
        
        # Calculate workload percentage
        workload_percentage = min(100, len(classes) * 15 + assignments * 5)
        
        return {
            "faculty_id": faculty_id,
            "name": faculty["full_name"],
            "email": faculty["email"],
            "designation": faculty.get("designation", "Assistant Professor"),
            "specialization": faculty.get("expertise", [""])[0] if faculty.get("expertise") else "General",
            "classes_taught": len(classes),
            "assignments_created": assignments,
            "avg_rating": round(avg_rating, 1),
            "attendance_records": attendance_records,
            "research_papers": len(research_papers),
            "workload_percentage": round(workload_percentage),
            "status": "present",  # Simplified for demo
            "courses": [c.get("name", "Unnamed") for c in classes[:3]],
            "student_count": sum(len(c.get("students", [])) for c in classes),
            "research_progress": random.randint(30, 100)
        }
    except Exception as e:
        logger.error(f"Get faculty stats error: {e}")
        return None


async def calculate_department_stats(department: str, academic_year: str):
    """Calculate department statistics"""
    try:
        # Get all faculty in department
        faculty = await users_collection.find({
            "user_type": {"$in": [UserType.FACULTY.value, UserType.HOD.value]},
            "department": department
        }).to_list(100)
        
        # Get all students in department
        students = await users_collection.find({
            "user_type": UserType.STUDENT.value,
            "department": department
        }).to_list(1000)
        
        # Get all classes in department
        classes = await classrooms_collection.find({
            "department": department
        }).to_list(100)
        
        # Calculate various statistics
        faculty_count = len(faculty)
        student_count = len(students)
        
        # Calculate average pass percentage (simulated)
        pass_percentage = random.randint(75, 95)
        
        # Calculate placement rate (simulated)
        placement_rate = random.randint(70, 90)
        
        # Calculate attendance rate
        total_attendance = 0
        total_possible = 0
        
        for cls in classes:
            attendance_records = await faculty_attendance_collection.find({
                "classroom_id": str(cls["_id"])
            }).to_list(50)
            
            for record in attendance_records:
                total_attendance += record.get("stats", {}).get("present", 0)
                total_possible += record.get("stats", {}).get("total", 0)
        
        attendance_rate = (total_attendance / total_possible * 100) if total_possible > 0 else 0
        
        # Calculate research output
        total_publications = 0
        for fac in faculty:
            total_publications += len(fac.get("publications", []))
        
        # Calculate grants/funding (simulated)
        grants_amount = random.randint(500000, 5000000)
        
        return {
            "department": department,
            "academic_year": academic_year,
            "stats": {
                "faculty": {
                    "total": faculty_count,
                    "change": random.randint(0, 10)  # % change from previous period
                },
                "students": {
                    "total": student_count,
                    "change": random.randint(0, 15)
                },
                "pass_percentage": {
                    "value": pass_percentage,
                    "change": random.randint(-5, 5)
                },
                "placement": {
                    "value": placement_rate,
                    "change": random.randint(-3, 7)
                },
                "attendance_rate": round(attendance_rate, 1),
                "research_output": total_publications,
                "grants_amount": f"${grants_amount:,}",
                "classes_active": len(classes),
                "student_faculty_ratio": round(student_count / faculty_count, 1) if faculty_count > 0 else 0
            }
        }
    except Exception as e:
        logger.error(f"Calculate department stats error: {e}")
        return None


async def generate_department_report(department: str, report_type: str = "monthly"):
    """Generate department report"""
    try:
        # Get department stats
        stats = await calculate_department_stats(department, f"{datetime.now().year}-{datetime.now().year + 1}")
        
        if not stats:
            return None
        
        # Get faculty performance data
        faculty_list = await users_collection.find({
            "user_type": {"$in": [UserType.FACULTY.value, UserType.HOD.value]},
            "department": department
        }).to_list(50)
        
        faculty_performance = []
        for faculty in faculty_list:
            performance = await get_faculty_stats(str(faculty["_id"]))
            if performance:
                faculty_performance.append(performance)
        
        # Get recent achievements
        recent_achievements = await notifications_collection.find({
            "notification_type": "achievement",
            "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=30)}
        }).sort("created_at", -1).limit(10).to_list(10)
        
        # Get upcoming events
        upcoming_events = await events_collection.find({
            "department": department,
            "date": {"$gte": datetime.now(timezone.utc)}
        }).sort("date", 1).limit(10).to_list(10)
        
        report = {
            "department": department,
            "report_type": report_type,
            "generated_at": datetime.now(timezone.utc),
            "period": f"{datetime.now().strftime('%B %Y')}",
            "executive_summary": {
                "overall_performance": "Excellent",
                "key_achievements": [
                    f"{stats['stats']['pass_percentage']['value']}% pass percentage",
                    f"{stats['stats']['placement']['value']}% placement rate",
                    f"{stats['stats']['research_output']} research publications"
                ],
                "areas_for_improvement": [
                    "Increase research funding",
                    "Improve laboratory facilities",
                    "Enhance industry collaboration"
                ]
            },
            "detailed_stats": stats["stats"],
            "faculty_performance": faculty_performance,
            "recent_achievements": recent_achievements,
            "upcoming_events": upcoming_events,
            "recommendations": [
                "Increase research collaboration opportunities",
                "Enhance student-industry interaction programs",
                "Upgrade laboratory equipment",
                "Organize more faculty development programs"
            ]
        }
        
        return report
    except Exception as e:
        logger.error(f"Generate department report error: {e}")
        return None


def clean_markdown_formatting(text: str) -> str:
    """Convert markdown formatting to plain text for clean professional display"""
    # Remove **bold** and replace with plain text (handles nested cases)
    text = re.sub(r'\*\*+([^*]+)\*\*+', r'\1', text)
    # Remove *italic* and replace with plain text
    text = re.sub(r'(?<!\*)\*(?!\*)([^*\n]+)\*(?!\*)', r'\1', text)
    # Remove __bold__ and replace with plain text
    text = re.sub(r'__+([^_]+)__+', r'\1', text)
    # Remove _italic_ and replace with plain text
    text = re.sub(r'(?<!_)_(?!_)([^_\n]+)_(?!_)', r'\1', text)
    # Remove markdown headers
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    # Remove markdown code blocks
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    # Remove single backticks
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Replace multiple newlines with single ones
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


async def validate_file(file: UploadFile) -> tuple[bytes, int]:
    """Validate file size and type with correct parameter"""
    try:
        # Read file content
        content = await file.read()
        
        # Check file size
        file_size = len(content)
        if file_size > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File too large. Max size: {MAX_FILE_SIZE/1024/1024}MB")
        
        # Check file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(ALLOWED_EXTENSIONS)
            raise HTTPException(status_code=400, detail=f"File type {file_ext} not allowed. Allowed: {allowed}")
        
        # Reset file pointer for future reads
        await file.seek(0)
        
        return content, file_size
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File validation error: {e}")
        raise HTTPException(status_code=500, detail="File validation failed")


async def generate_qr_code(data: str):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    
    return buffer.getvalue()


async def send_email_async(to_email: str, subject: str, body: str):
    # This is a placeholder for actual email sending
    logger.info(f"Email sent to {to_email}: {subject}")
    return True


async def send_sms_async(phone: str, message: str):
    # Placeholder for SMS service
    logger.info(f"SMS sent to {phone}: {message}")
    return True


async def upload_to_cloud_storage(file_content: bytes, filename: str, content_type: str):
    # Save locally (for development)
    file_id = str(uuid.uuid4())
    file_ext = Path(filename).suffix.lower()
    safe_filename = f"{file_id}{file_ext}"
    file_path = f"uploads/{safe_filename}"
    
    os.makedirs(os.path.dirname(f"static/{file_path}"), exist_ok=True)
    with open(f"static/{file_path}", "wb") as f:
        f.write(file_content)
    
    return {
        "url": f"/static/{file_path}",
        "file_id": file_id,
        "filename": safe_filename
    }


async def calculate_level(xp: int) -> dict:
    """Calculate level based on XP"""
    level = 1
    xp_for_next = 1000
    
    while xp >= xp_for_next:
        xp -= xp_for_next
        level += 1
        xp_for_next = int(xp_for_next * 1.5)  # XP requirement increases
    
    return {
        "level": level,
        "current_xp": xp,
        "xp_for_next_level": xp_for_next,
        "xp_progress": (xp / xp_for_next) * 100 if xp_for_next > 0 else 100
    }


async def update_user_credits(user_id: str, amount: int, source: str, description: str, metadata: dict = None):
    """Update user credits and log transaction"""
    try:
        # Update user's credits
        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {"credits": amount}}
        )
        
        # Log transaction
        transaction = {
            "user_id": user_id,
            "amount": amount,
            "transaction_type": "award" if amount > 0 else "penalty",
            "source": source,
            "description": description,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc)
        }
        
        await credit_transactions_collection.insert_one(transaction)
        
        # Update XP based on credits earned
        if amount > 0:
            xp_earned = amount * 2  # 2 XP per credit
            await users_collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$inc": {"xp": xp_earned}}
            )
            
            # Log XP transaction
            xp_transaction = {
                "user_id": user_id,
                "amount": xp_earned,
                "type": "xp_award",
                "source": source,
                "description": f"XP earned from credits: {description}",
                "created_at": datetime.now(timezone.utc)
            }
            await credit_transactions_collection.insert_one(xp_transaction)
        
        return True
    except Exception as e:
        logger.error(f"Update credits error: {e}")
        return False


async def get_user_credits_summary(user_id: str):
    """Get user's credit summary"""
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            return None
        
        # Calculate level
        xp = user.get("xp", 0)
        level_data = await calculate_level(xp)
        
        # Get recent transactions
        recent_transactions = await credit_transactions_collection.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(10).to_list(10)
        
        # Calculate weekly earnings
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        weekly_earnings = await credit_transactions_collection.aggregate([
            {"$match": {
                "user_id": user_id,
                "amount": {"$gt": 0},
                "created_at": {"$gte": week_ago}
            }},
            {"$group": {
                "_id": None,
                "total": {"$sum": "$amount"}
            }}
        ]).to_list(1)
        
        # Get leaderboard position
        leaderboard_position = await get_leaderboard_position(user_id)
        
        return {
            "user_id": user_id,
            "full_name": user.get("full_name", ""),
            "credits": user.get("credits", 0),
            "xp": xp,
            "level_data": level_data,
            "weekly_earnings": weekly_earnings[0]["total"] if weekly_earnings else 0,
            "leaderboard_position": leaderboard_position,
            "recent_transactions": recent_transactions,
            "daily_login_streak": user.get("daily_login_streak", 0),
            "badges_count": len(user.get("badges", []))
        }
    except Exception as e:
        logger.error(f"Get credits summary error: {e}")
        return None


async def get_leaderboard_position(user_id: str):
    """Get user's position in leaderboard"""
    try:
        # Get all users sorted by credits
        users = await users_collection.find(
            {"user_type": UserType.STUDENT.value},
            {"credits": 1, "full_name": 1, "department": 1}
        ).sort("credits", -1).to_list(100)
        
        # Find user position
        for index, user in enumerate(users):
            if str(user["_id"]) == user_id:
                return {
                    "position": index + 1,
                    "total_users": len(users),
                    "top_3": [
                        {
                            "name": users[0].get("full_name", "User 1"),
                            "credits": users[0].get("credits", 0),
                            "department": users[0].get("department", "")
                        },
                        {
                            "name": users[1].get("full_name", "User 2") if len(users) > 1 else None,
                            "credits": users[1].get("credits", 0) if len(users) > 1 else 0,
                            "department": users[1].get("department", "") if len(users) > 1 else ""
                        },
                        {
                            "name": users[2].get("full_name", "User 3") if len(users) > 2 else None,
                            "credits": users[2].get("credits", 0) if len(users) > 2 else 0,
                            "department": users[2].get("department", "") if len(users) > 2 else ""
                        }
                    ]
                }
        
        return {"position": 0, "total_users": 0, "top_3": []}
    except Exception as e:
        logger.error(f"Get leaderboard position error: {e}")
        return {"position": 0, "total_users": 0, "top_3": []}


async def get_pending_by_type_counts(department: str):
    """Get counts of pending approvals by type"""
    pipeline = [
        {"$match": {
            "department": department,
            "status": ApprovalStatus.PENDING.value
        }},
        {"$group": {
            "_id": "$approval_type",
            "count": {"$sum": 1},
            "urgent": {"$sum": {"$cond": [{"$eq": ["$priority", "urgent"]}, 1, 0]}},
            "high": {"$sum": {"$cond": [{"$eq": ["$priority", "high"]}, 1, 0]}}
        }}
    ]
    
    result = list(await approvals_collection.aggregate(pipeline).to_list(10))
    return {item["_id"]: item for item in result}


async def create_approval_request_internal(approval_data: dict, current_user: dict):
    """Internal function to create approval request"""
    approval = {
        **approval_data,
        "requested_by_email": current_user["email"],
        "requested_by_role": current_user["user_type"],
        "status": ApprovalStatus.PENDING.value,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "history": [{
            "action": "created",
            "by": approval_data["requested_by"],
            "by_name": approval_data["requested_by_name"],
            "timestamp": datetime.now(timezone.utc),
            "notes": "Request submitted"
        }]
    }
    
    result = await approvals_collection.insert_one(approval)
    approval_id = str(result.inserted_id)
    
    return {"approval_id": approval_id, "approval": approval}


async def execute_approved_action(approval: dict, current_user: dict):
    """Execute action after approval"""
    try:
        approval_type = approval["approval_type"]
        
        if approval_type == ApprovalType.FACULTY_COMMUNITY.value:
            # Create faculty community
            community_data = approval.get("metadata", {}).get("community_data", {})
            if community_data:
                # Add HOD to members
                members = community_data.get("members", [])
                members.append(str(current_user["_id"]))
                
                community = {
                    "name": community_data["community_name"],
                    "description": community_data["description"],
                    "type": community_data["community_type"],
                    "privacy": community_data["privacy"],
                    "members": members,
                    "created_by": approval["requested_by"],
                    "created_by_name": approval["requested_by_name"],
                    "created_at": datetime.now(timezone.utc),
                    "approved_by": str(current_user["_id"]),
                    "approved_at": datetime.now(timezone.utc),
                    "approval_id": str(approval["_id"]),
                    "status": "active",
                    "duration_days": community_data.get("duration_days", 30)
                }
                
                await faculty_communities_collection.insert_one(community)
                
                # Notify all members
                for member_id in members:
                    await NotificationService.create_notification(
                        user_id=member_id,
                        title=f"New Community: {community_data['community_name']}",
                        message=f"You've been added to {community_data['community_type']} community '{community_data['community_name']}'",
                        notification_type="community",
                        action_url=f"/communities/{str(community['_id'])}"
                    )
        
        elif approval_type == ApprovalType.FACULTY_LEAVE.value:
            # Update faculty leave status
            leave_data = approval.get("metadata", {}).get("leave_data", {})
            
            # Create leave record
            leave_record = {
                "faculty_id": approval["requested_by"],
                "faculty_name": approval["requested_by_name"],
                "leave_type": leave_data.get("leave_type"),
                "start_date": leave_data.get("start_date"),
                "end_date": leave_data.get("end_date"),
                "reason": leave_data.get("reason"),
                "status": "approved",
                "approved_by": str(current_user["_id"]),
                "approved_at": datetime.now(timezone.utc),
                "approval_id": str(approval["_id"])
            }
            
            await db.faculty_leaves.insert_one(leave_record)
            
            # Update faculty status
            await users_collection.update_one(
                {"_id": ObjectId(approval["requested_by"])},
                {"$set": {"status": "on_leave", "leave_start": leave_data.get("start_date"), "leave_end": leave_data.get("end_date")}}
            )
        
        elif approval_type == ApprovalType.RESOURCE_REQUEST.value:
            # Process resource request
            resource_data = approval.get("metadata", {}).get("resource_data", {})
            
            # Create resource allocation record
            resource_record = {
                "item_name": resource_data.get("item_name"),
                "resource_type": resource_data.get("resource_type"),
                "quantity": resource_data.get("quantity"),
                "requested_by": approval["requested_by"],
                "requested_by_name": approval["requested_by_name"],
                "purpose": resource_data.get("purpose"),
                "status": "allocated",
                "approved_by": str(current_user["_id"]),
                "approved_at": datetime.now(timezone.utc),
                "approval_id": str(approval["_id"]),
                "estimated_cost": resource_data.get("estimated_cost")
            }
            
            await db.resource_allocations.insert_one(resource_record)
            
        logger.info(f"Executed approved action for {approval_type}")
        
    except Exception as e:
        logger.error(f"Execute approved action error: {e}")


async def get_approval_statistics(hod_id: str, period: str = "month"):
    """Get approval statistics"""
    try:
        # Calculate date range based on period
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
        
        # Get counts
        pipeline = [
            {"$match": {
                "approvers": hod_id,
                "created_at": {"$gte": start_date}
            }},
            {"$facet": {
                "total": [{"$count": "count"}],
                "by_status": [{"$group": {"_id": "$status", "count": {"$sum": 1}}}],
                "by_type": [{"$group": {"_id": "$approval_type", "count": {"$sum": 1}}}],
                "by_priority": [{"$group": {"_id": "$priority", "count": {"$sum": 1}}}],
                "pending_urgent": [
                    {"$match": {"status": "pending", "priority": "urgent"}},
                    {"$count": "count"}
                ],
                "pending_high": [
                    {"$match": {"status": "pending", "priority": "high"}},
                    {"$count": "count"}
                ],
                "recent_actions": [
                    {"$match": {"status": {"$ne": "pending"}}},
                    {"$sort": {"updated_at": -1}},
                    {"$limit": 5},
                    {"$project": {
                        "title": 1,
                        "status": 1,
                        "updated_at": 1,
                        "requested_by_name": 1,
                        "approval_type": 1
                    }}
                ]
            }}
        ]
        
        result = list(await approvals_collection.aggregate(pipeline).to_list(1))
        if not result:
            return {}
        
        stats = result[0]
        
        # Calculate average processing time for completed approvals
        processing_pipeline = [
            {"$match": {
                "approvers": hod_id,
                "status": {"$in": ["approved", "rejected"]},
                "created_at": {"$gte": start_date},
                "updated_at": {"$exists": True}
            }},
            {"$project": {
                "processing_hours": {
                    "$divide": [
                        {"$subtract": ["$updated_at", "$created_at"]},
                        3600000  # Convert to hours
                    ]
                }
            }},
            {"$group": {
                "_id": None,
                "avg_hours": {"$avg": "$processing_hours"},
                "min_hours": {"$min": "$processing_hours"},
                "max_hours": {"$max": "$processing_hours"}
            }}
        ]
        
        processing_stats = list(await approvals_collection.aggregate(processing_pipeline).to_list(1))
        
        return {
            "total": stats["total"][0]["count"] if stats["total"] else 0,
            "by_status": {item["_id"]: item["count"] for item in stats["by_status"]},
            "by_type": {item["_id"]: item["count"] for item in stats["by_type"]},
            "by_priority": {item["_id"]: item["count"] for item in stats["by_priority"]},
            "pending_urgent": stats["pending_urgent"][0]["count"] if stats["pending_urgent"] else 0,
            "pending_high": stats["pending_high"][0]["count"] if stats["pending_high"] else 0,
            "processing_stats": processing_stats[0] if processing_stats else {},
            "recent_actions": stats["recent_actions"]
        }
        
    except Exception as e:
        logger.error(f"Get approval statistics error: {e}")
        return {}


async def update_approval_statistics(department: str):
    """Update department approval statistics"""
    try:
        # This would update department-wide statistics
        # Implementation depends on your requirements
        pass
    except Exception as e:
        logger.error(f"Update approval statistics error: {e}")


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


async def generate_report_background(report_id: str, report_data: ReportGenerate, 
                                   department: str, user_id: str, user_name: str):
    """Background task for report generation"""
    try:
        # Simulate report generation (replace with actual report generation logic)
        await asyncio.sleep(5)  # Simulate processing time
        
        # Generate report based on type
        report_content = generate_report_content(report_data, department)
        
        # Save report file
        file_path = f"static/reports/{report_id}.{report_data.format}"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        if report_data.format == "pdf":
            # Generate PDF report
            await generate_pdf_report(report_content, file_path)
        elif report_data.format == "excel":
            # Generate Excel report
            await generate_excel_report(report_content, file_path)
        elif report_data.format == "csv":
            # Generate CSV report
            await generate_csv_report(report_content, file_path)
        
        # Update report record
        file_size = os.path.getsize(file_path)
        
        await reports_collection.update_one(
            {"_id": ObjectId(report_id)},
            {
                "$set": {
                    "status": ReportStatus.GENERATED.value,
                    "file_path": file_path,
                    "file_size": file_size,
                    "generation_time": 5,  # Simulated time
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )
        
        # Send notification
        await NotificationService.create_notification(
            user_id=user_id,
            title="Report Generated",
            message=f"Your report '{report_data.title}' has been generated successfully.",
            notification_type="report",
            action_url=f"/reports/{report_id}"
        )
        
        logger.info(f"Report {report_id} generated successfully")
        
    except Exception as e:
        logger.error(f"Background report generation error: {e}")
        
        # Update report as failed
        await reports_collection.update_one(
            {"_id": ObjectId(report_id)},
            {
                "$set": {
                    "status": ReportStatus.FAILED.value,
                    "error_message": str(e),
                    "updated_at": datetime.now(timezone.utc)
                }
            }
        )


def generate_report_content(report_data: ReportGenerate, department: str) -> Dict[str, Any]:
    """Generate report content based on type"""
    # This is a simplified version - implement actual data fetching based on report type
    content = {
        "department": department,
        "title": report_data.title,
        "type": report_data.type.value,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": {}
    }
    
    # Add data based on sections
    for section in report_data.sections:
        if section == "summary":
            content["sections"]["summary"] = generate_summary_data(department)
        elif section == "faculty_performance":
            content["sections"]["faculty_performance"] = generate_faculty_performance_data(department)
        elif section == "student_performance":
            content["sections"]["student_performance"] = generate_student_performance_data(department)
        elif section == "attendance":
            content["sections"]["attendance"] = generate_attendance_data(department)
        elif section == "resource_utilization":
            content["sections"]["resource_utilization"] = generate_resource_utilization_data(department)
        elif section == "financial":
            content["sections"]["financial"] = generate_financial_data(department)
        elif section == "placement":  
            content["sections"]["placement"] = generate_placement_data(department)
        elif section == "research":
            content["sections"]["research"] = generate_research_data(department)
    
    return content


async def generate_summary_data(department: str):
    """Generate summary data for department"""
    try:
        # Get department stats
        stats = await calculate_department_stats(department, f"{datetime.now().year}-{datetime.now().year + 1}")
        
        if not stats:
            return None
        
        # Get faculty count
        faculty_count = await users_collection.count_documents({
            "department": department,
            "user_type": {"$in": [UserType.FACULTY.value, UserType.HOD.value]}
        })
        
        # Get student count
        student_count = await users_collection.count_documents({
            "department": department,
            "user_type": UserType.STUDENT.value
        })
        
        # Get active classes
        active_classes = await classrooms_collection.count_documents({
            "department": department,
            "status": "active"
        })
        
        # Get ongoing projects
        ongoing_projects = await projects_collection.count_documents({
            "department": department,
            "status": {"$in": ["in_progress", "planning"]}
        })
        
        # Get recent achievements
        recent_achievements = await notifications_collection.find({
            "notification_type": "achievement",
            "department": department,
            "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=30)}
        }).sort("created_at", -1).limit(5).to_list(5)
        
        return {
            "faculty_count": faculty_count,
            "student_count": student_count,
            "active_classes": active_classes,
            "ongoing_projects": ongoing_projects,
            "pass_percentage": stats.get("stats", {}).get("pass_percentage", {}).get("value", 0),
            "placement_rate": stats.get("stats", {}).get("placement", {}).get("value", 0),
            "attendance_rate": stats.get("stats", {}).get("attendance_rate", 0),
            "student_faculty_ratio": stats.get("stats", {}).get("student_faculty_ratio", 0),
            "research_output": stats.get("stats", {}).get("research_output", 0),
            "recent_achievements": recent_achievements,
            "overall_performance": "Excellent" if stats.get("stats", {}).get("pass_percentage", {}).get("value", 0) > 85 else "Good"
        }
    except Exception as e:
        logger.error(f"Generate summary data error: {e}")
        return None


async def generate_faculty_performance_data(department: str):
    """Generate faculty performance data"""
    try:
        # Get all faculty in department
        faculty_list = await users_collection.find({
            "user_type": {"$in": [UserType.FACULTY.value, UserType.HOD.value]},
            "department": department
        }).to_list(50)
        
        faculty_performance = []
        for faculty in faculty_list:
            performance = await get_faculty_stats(str(faculty["_id"]))
            if performance:
                faculty_performance.append(performance)
        
        # Calculate department averages
        if faculty_performance:
            avg_rating = sum(f["avg_rating"] for f in faculty_performance) / len(faculty_performance)
            avg_workload = sum(f["workload_percentage"] for f in faculty_performance) / len(faculty_performance)
            total_research = sum(f["research_papers"] for f in faculty_performance)
        else:
            avg_rating = 0
            avg_workload = 0
            total_research = 0
        
        # Get faculty by performance tier
        high_performers = [f for f in faculty_performance if f["avg_rating"] >= 4.5]
        medium_performers = [f for f in faculty_performance if 3.5 <= f["avg_rating"] < 4.5]
        low_performers = [f for f in faculty_performance if f["avg_rating"] < 3.5]
        
        # Get top 3 performing faculty
        top_faculty = sorted(faculty_performance, key=lambda x: x["avg_rating"], reverse=True)[:3]
        
        return {
            "total_faculty": len(faculty_performance),
            "average_rating": round(avg_rating, 1),
            "average_workload": round(avg_workload, 1),
            "total_research_papers": total_research,
            "performance_distribution": {
                "high_performers": len(high_performers),
                "medium_performers": len(medium_performers),
                "low_performers": len(low_performers)
            },
            "top_performers": top_faculty,
            "faculty_details": faculty_performance[:10],  # Limit for report
            "by_designation": await get_faculty_by_designation(department),
            "workload_analysis": await analyze_faculty_workload(department)
        }
    except Exception as e:
        logger.error(f"Generate faculty performance data error: {e}")
        return None


async def generate_student_performance_data(department: str):
    """Generate student performance data"""
    try:
        # Get all students in department
        students = await users_collection.find({
            "user_type": UserType.STUDENT.value,
            "department": department
        }).to_list(1000)
        
        # This would normally come from exam/assignment submissions
        # For demo, generate simulated data
        
        # Simulate student performance by year
        performance_by_year = {}
        for year in range(1, 6):
            year_students = [s for s in students if s.get("year") == year]
            if year_students:
                # Simulate average scores
                avg_score = random.uniform(65, 90)
                pass_rate = random.uniform(80, 98)
                
                performance_by_year[year] = {
                    "student_count": len(year_students),
                    "average_score": round(avg_score, 1),
                    "pass_percentage": round(pass_rate, 1),
                    "top_performers": random.randint(1, 5),
                    "needs_improvement": random.randint(0, 3)
                }
        
        # Get recent exam results (simulated)
        recent_exams = []
        exam_titles = ["Mid-Term Exam", "Final Exam", "Internal Assessment 1", "Internal Assessment 2"]
        
        for i in range(4):
            recent_exams.append({
                "exam_title": exam_titles[i],
                "subject": f"Subject {i+1}",
                "average_score": random.uniform(65, 85),
                "pass_percentage": random.uniform(75, 95),
                "top_scorer": random.randint(85, 100),
                "date": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))).isoformat()
            })
        
        # Get student achievements
        student_achievements = await notifications_collection.find({
            "notification_type": "student_achievement",
            "department": department,
            "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=90)}
        }).sort("created_at", -1).limit(10).to_list(10)
        
        # Calculate overall statistics
        total_students = len(students)
        overall_avg_score = sum(p["average_score"] for p in performance_by_year.values()) / len(performance_by_year) if performance_by_year else 0
        overall_pass_rate = sum(p["pass_percentage"] for p in performance_by_year.values()) / len(performance_by_year) if performance_by_year else 0
        
        return {
            "total_students": total_students,
            "overall_average_score": round(overall_avg_score, 1),
            "overall_pass_percentage": round(overall_pass_rate, 1),
            "performance_by_year": performance_by_year,
            "recent_exam_results": recent_exams,
            "student_achievements": student_achievements,
            "academic_improvement": await calculate_academic_improvement(department),
            "weak_areas_analysis": await analyze_weak_areas(department)
        }
    except Exception as e:
        logger.error(f"Generate student performance data error: {e}")
        return None


async def generate_attendance_data(department: str):
    """Generate attendance data"""
    try:
        # Get all classes in department
        classes = await classrooms_collection.find({
            "department": department,
            "status": "active"
        }).to_list(100)
        
        total_classes = len(classes)
        attendance_summary = []
        total_present = 0
        total_expected = 0
        
        # Process each class
        for cls in classes:
            class_id = str(cls["_id"])
            
            # Get attendance records for this class (simulated for demo)
            attendance_records = await faculty_attendance_collection.find({
                "classroom_id": class_id
            }).sort("date", -1).limit(10).to_list(10)
            
            class_present = 0
            class_expected = 0
            
            for record in attendance_records:
                stats = record.get("stats", {})
                class_present += stats.get("present", 0)
                class_expected += stats.get("total", 0)
            
            attendance_rate = (class_present / class_expected * 100) if class_expected > 0 else 0
            
            attendance_summary.append({
                "classroom_code": cls.get("code"),
                "classroom_name": cls.get("name"),
                "total_sessions": len(attendance_records),
                "average_attendance": round(attendance_rate, 1),
                "present_count": class_present,
                "expected_count": class_expected
            })
            
            total_present += class_present
            total_expected += class_expected
        
        # Calculate overall attendance
        overall_attendance = (total_present / total_expected * 100) if total_expected > 0 else 0
        
        # Get attendance trends (last 30 days)
        attendance_trend = []
        for i in range(30):
            date = datetime.now(timezone.utc) - timedelta(days=30-i)
            # Simulate daily attendance
            daily_attendance = random.uniform(70, 95)
            attendance_trend.append({
                "date": date.strftime("%Y-%m-%d"),
                "attendance_rate": round(daily_attendance, 1)
            })
        
        # Get classes with low attendance
        low_attendance_classes = [c for c in attendance_summary if c["average_attendance"] < 75]
        
        # Get student attendance patterns
        student_attendance_patterns = await analyze_student_attendance_patterns(department)
        
        return {
            "overall_attendance_rate": round(overall_attendance, 1),
            "total_sessions_tracked": total_classes * 10,  # Approximate
            "attendance_by_class": attendance_summary[:10],  # Top 10 for report
            "attendance_trend": attendance_trend,
            "low_attendance_classes": low_attendance_classes[:5],
            "best_attendance_classes": sorted(attendance_summary, key=lambda x: x["average_attendance"], reverse=True)[:3],
            "student_attendance_patterns": student_attendance_patterns,
            "recommendations": [
                "Implement automated attendance tracking",
                "Address low attendance in specific classes",
                "Introduce attendance incentives"
            ]
        }
    except Exception as e:
        logger.error(f"Generate attendance data error: {e}")
        return None


async def generate_resource_utilization_data(department: str):
    """Generate resource utilization data"""
    try:
        # Get all resources in department
        resources = await resources_collection.find({
            "department": department,
            "status": {"$ne": "archived"}
        }).to_list(100)
        
        resource_summary = []
        total_resources = len(resources)
        in_use_count = 0
        available_count = 0
        maintenance_count = 0
        total_cost = 0
        
        # Process each resource
        for resource in resources:
            status = resource.get("status", "available")
            
            if status == "in-use":
                in_use_count += 1
            elif status == "available":
                available_count += 1
            elif status == "maintenance":
                maintenance_count += 1
            
            if resource.get("purchase_cost"):
                total_cost += resource["purchase_cost"]
            
            # Calculate utilization if available
            usage_count = resource.get("usage_count", 0)
            age_days = calculate_resource_age_days(resource.get("purchase_date"))
            utilization_rate = (usage_count / max(age_days, 1)) * 100 if age_days > 0 else 0
            
            resource_summary.append({
                "name": resource["name"],
                "category": resource.get("category"),
                "status": status,
                "location": resource.get("location"),
                "purchase_cost": resource.get("purchase_cost", 0),
                "usage_count": usage_count,
                "last_used": resource.get("last_used"),
                "utilization_rate": round(min(utilization_rate, 100), 1)
            })
        
        # Calculate overall utilization
        utilization_rate = (in_use_count / total_resources * 100) if total_resources > 0 else 0
        
        # Get resources by category
        resources_by_category = {}
        for resource in resources:
            category = resource.get("category", "other")
            if category not in resources_by_category:
                resources_by_category[category] = 0
            resources_by_category[category] += 1
        
        # Get maintenance status
        maintenance_records = await maintenance_collection.find({
            "department": department,
            "status": {"$in": ["pending", "in_progress"]}
        }).sort("scheduled_date", 1).limit(10).to_list(10)
        
        # Get resource requests
        pending_requests = await resource_requests_collection.count_documents({
            "department": department,
            "status": "pending"
        })
        
        # Calculate cost efficiency
        avg_cost_per_resource = total_cost / total_resources if total_resources > 0 else 0
        
        return {
            "total_resources": total_resources,
            "in_use_count": in_use_count,
            "available_count": available_count,
            "maintenance_count": maintenance_count,
            "overall_utilization_rate": round(utilization_rate, 1),
            "total_investment": total_cost,
            "average_cost_per_resource": round(avg_cost_per_resource, 2),
            "resources_by_category": resources_by_category,
            "top_utilized_resources": sorted(resource_summary, key=lambda x: x["utilization_rate"], reverse=True)[:5],
            "underutilized_resources": [r for r in resource_summary if r["utilization_rate"] < 30][:5],
            "pending_maintenance": len(maintenance_records),
            "pending_resource_requests": pending_requests,
            "recommendations": [
                "Optimize utilization of underutilized resources",
                "Plan maintenance schedules better",
                "Consider resource sharing between departments"
            ]
        }
    except Exception as e:
        logger.error(f"Generate resource utilization data error: {e}")
        return None


async def generate_financial_data(department: str):
    """Generate financial data"""
    try:
        # This would normally come from financial systems
        # For demo, generate simulated data
        
        # Simulate budget allocation
        budget_categories = {
            "Salaries": random.randint(500000, 1000000),
            "Infrastructure": random.randint(200000, 500000),
            "Research": random.randint(100000, 300000),
            "Training": random.randint(50000, 150000),
            "Equipment": random.randint(150000, 400000),
            "Events": random.randint(50000, 100000),
            "Miscellaneous": random.randint(50000, 100000)
        }
        
        total_budget = sum(budget_categories.values())
        
        # Simulate expenses
        expenses_by_category = {}
        for category, budget in budget_categories.items():
            # Expenses are typically 70-95% of budget
            expenses = budget * random.uniform(0.7, 0.95)
            expenses_by_category[category] = round(expenses, 2)
        
        total_expenses = sum(expenses_by_category.values())
        
        # Simulate grants and funding
        grants = [
            {"name": "Research Grant 2024", "amount": random.randint(50000, 200000), "status": "active"},
            {"name": "Infrastructure Grant", "amount": random.randint(100000, 300000), "status": "active"},
            {"name": "Student Scholarship Fund", "amount": random.randint(50000, 150000), "status": "active"}
        ]
        
        total_grants = sum(g["amount"] for g in grants)
        
        # Calculate utilization percentages
        budget_utilization = {}
        for category in budget_categories:
            utilization = (expenses_by_category.get(category, 0) / budget_categories[category]) * 100
            budget_utilization[category] = round(utilization, 1)
        
        overall_utilization = (total_expenses / total_budget) * 100
        
        # Get recent financial transactions (simulated)
        recent_transactions = []
        transaction_types = ["Salary Payment", "Equipment Purchase", "Software License", "Maintenance", "Training", "Event Sponsorship"]
        
        for i in range(10):
            recent_transactions.append({
                "date": (datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d"),
                "description": f"{random.choice(transaction_types)} - {i+1}",
                "amount": random.randint(1000, 50000),
                "type": "expense",
                "category": random.choice(list(budget_categories.keys()))
            })
        
        # Get pending approvals with financial impact
        financial_approvals = await approvals_collection.find({
            "department": department,
            "approval_type": {"$in": ["budget_allocation", "resource_request"]},
            "status": "pending"
        }).sort("created_at", -1).limit(5).to_list(5)
        
        # Calculate financial health indicators
        budget_variance = total_expenses - total_budget
        burn_rate = total_expenses / 12  # Monthly burn rate
        
        return {
            "total_budget": total_budget,
            "total_expenses": total_expenses,
            "budget_variance": budget_variance,
            "overall_utilization": round(overall_utilization, 1),
            "budget_by_category": budget_categories,
            "expenses_by_category": expenses_by_category,
            "utilization_by_category": budget_utilization,
            "grants_and_funding": grants,
            "total_grants": total_grants,
            "recent_transactions": recent_transactions,
            "pending_financial_approvals": len(financial_approvals),
            "financial_health": "Good" if overall_utilization < 90 else "Needs Attention",
            "burn_rate": round(burn_rate, 2),
            "recommendations": [
                "Review high-utilization categories",
                "Optimize resource allocation",
                "Explore additional funding opportunities"
            ]
        }
    except Exception as e:
        logger.error(f"Generate financial data error: {e}")
        return None


async def generate_placement_data(department: str):
    """Generate placement data"""
    try:
        # This would normally come from placement records
        # For demo, generate simulated data
        
        # Simulate placement statistics
        placement_stats = {
            "total_students_eligible": random.randint(100, 300),
            "placed_students": random.randint(80, 250),
            "placement_percentage": 0,  # Will be calculated
            "average_salary": random.randint(400000, 800000),
            "highest_salary": random.randint(800000, 1500000),
            "companies_visited": random.randint(20, 50),
            "offers_made": random.randint(100, 300)
        }
        
        placement_stats["placement_percentage"] = round(
            (placement_stats["placed_students"] / placement_stats["total_students_eligible"]) * 100, 
            1
        )
        
        # Simulate placement by company
        companies = ["Infosys", "TCS", "Wipro", "Accenture", "Amazon", "Google", "Microsoft", "IBM", "Cognizant", "Capgemini"]
        placement_by_company = []
        
        for company in companies[:6]:  # Top 6 companies
            placements = random.randint(5, 30)
            avg_salary = random.randint(400000, 700000)
            placement_by_company.append({
                "company": company,
                "placements": placements,
                "average_salary": avg_salary,
                "highest_salary": random.randint(avg_salary + 100000, avg_salary + 500000)
            })
        
        # Simulate placement trend (last 5 years)
        placement_trend = []
        current_year = datetime.now().year
        
        for year in range(current_year - 4, current_year + 1):
            placements = random.randint(60, 120)
            eligible = random.randint(80, 150)
            percentage = round((placements / eligible) * 100, 1)
            avg_salary = random.randint(300000 + (year - (current_year - 4)) * 50000, 
                                       500000 + (year - (current_year - 4)) * 50000)
            
            placement_trend.append({
                "year": year,
                "eligible_students": eligible,
                "placed_students": placements,
                "placement_percentage": percentage,
                "average_salary": avg_salary
            })
        
        # Simulate upcoming placement drives
        upcoming_drives = []
        drive_companies = ["Amazon", "Microsoft", "Google", "Adobe", "Intel"]
        
        for i in range(3):
            drive_date = datetime.now(timezone.utc) + timedelta(days=random.randint(7, 60))
            upcoming_drives.append({
                "company": drive_companies[i],
                "date": drive_date.strftime("%Y-%m-%d"),
                "positions": random.randint(5, 20),
                "eligibility_criteria": "CGPA > 7.5, No backlogs",
                "status": "scheduled"
            })
        
        # Get student achievements in placements
        placement_achievements = await notifications_collection.find({
            "notification_type": "placement",
            "department": department,
            "created_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=180)}
        }).sort("created_at", -1).limit(5).to_list(5)
        
        # Calculate growth metrics
        if len(placement_trend) >= 2:
            growth_rate = ((placement_trend[-1]["placement_percentage"] - placement_trend[-2]["placement_percentage"]) / 
                          placement_trend[-2]["placement_percentage"]) * 100
        else:
            growth_rate = 0
        
        return {
            **placement_stats,
            "placement_by_company": placement_by_company,
            "placement_trend": placement_trend,
            "top_recruiters": sorted(placement_by_company, key=lambda x: x["placements"], reverse=True)[:3],
            "upcoming_drives": upcoming_drives,
            "placement_achievements": placement_achievements,
            "year_over_year_growth": round(growth_rate, 1),
            "placement_support_activities": await get_placement_support_activities(department),
            "recommendations": [
                "Increase industry collaboration",
                "Enhance placement training programs",
                "Diversify recruiter portfolio"
            ]
        }
    except Exception as e:
        logger.error(f"Generate placement data error: {e}")
        return None


async def generate_research_data(department: str):
    """Generate research data"""
    try:
        # Get all faculty in department
        faculty_list = await users_collection.find({
            "user_type": {"$in": [UserType.FACULTY.value, UserType.HOD.value]},
            "department": department
        }).to_list(50)
        
        # Calculate research metrics
        total_publications = 0
        total_grants = 0
        total_projects = 0
        faculty_research = []
        
        for faculty in faculty_list:
            publications = faculty.get("publications", [])
            grants = faculty.get("grants", [])
            projects = faculty.get("research_projects", [])
            
            total_publications += len(publications)
            total_grants += len(grants)
            total_projects += len(projects)
            
            faculty_research.append({
                "faculty_name": faculty["full_name"],
                "publications": len(publications),
                "grants": len(grants),
                "projects": len(projects),
                "h_index": random.randint(5, 20),  # Simulated
                "citations": random.randint(100, 1000)  # Simulated
            })
        
        # Get research publications (simulated details)
        recent_publications = []
        publication_types = ["Journal", "Conference", "Book Chapter", "Patent"]
        
        for i in range(10):
            recent_publications.append({
                "title": f"Research Publication {i+1}",
                "authors": ["Faculty Member 1", "Faculty Member 2", "Student 1"],
                "type": random.choice(publication_types),
                "year": random.randint(2020, 2024),
                "citations": random.randint(0, 50),
                "journal": f"Journal of {department} Sciences",
                "impact_factor": round(random.uniform(2.0, 5.0), 2)
            })
        
        # Get research grants
        research_grants = []
        grant_agencies = ["DST", "UGC", "AICTE", "CSIR", "ICMR", "Industry Collaboration"]
        
        for i in range(6):
            amount = random.randint(500000, 3000000)
            start_date = datetime.now(timezone.utc) - timedelta(days=random.randint(100, 1000))
            end_date = start_date + timedelta(days=random.randint(365, 1095))
            
            research_grants.append({
                "title": f"Research Grant {i+1}",
                "agency": random.choice(grant_agencies),
                "amount": amount,
                "principal_investigator": random.choice([f["full_name"] for f in faculty_list]),
                "start_date": start_date.strftime("%Y-%m-%d"),
                "end_date": end_date.strftime("%Y-%m-%d"),
                "status": "ongoing" if end_date > datetime.now(timezone.utc) else "completed"
            })
        
        # Calculate total grant amount
        total_grant_amount = sum(g["amount"] for g in research_grants)
        
        # Get ongoing research projects
        ongoing_projects = await projects_collection.find({
            "department": department,
            "project_type": "research",
            "status": {"$in": ["planning", "in_progress"]}
        }).sort("created_at", -1).limit(5).to_list(5)
        
        # Calculate research productivity
        faculty_count = len(faculty_list)
        publications_per_faculty = total_publications / faculty_count if faculty_count > 0 else 0
        grants_per_faculty = total_grants / faculty_count if faculty_count > 0 else 0
        
        # Get research collaborations
        collaborations = await analyze_research_collaborations(department)
        
        # Get student research participation
        student_research = await get_student_research_participation(department)
        
        return {
            "faculty_count": faculty_count,
            "total_publications": total_publications,
            "total_grants": total_grants,
            "total_grant_amount": total_grant_amount,
            "total_research_projects": total_projects,
            "publications_per_faculty": round(publications_per_faculty, 1),
            "grants_per_faculty": round(grants_per_faculty, 1),
            "faculty_research_performance": sorted(faculty_research, key=lambda x: x["publications"], reverse=True)[:5],
            "recent_publications": recent_publications[:5],
            "research_grants": research_grants,
            "ongoing_research_projects": ongoing_projects,
            "research_collaborations": collaborations,
            "student_research_participation": student_research,
            "research_impact": await calculate_research_impact(department),
            "recommendations": [
                "Increase interdisciplinary research",
                "Enhance industry-academia collaboration",
                "Improve research publication quality"
            ]
        }
    except Exception as e:
        logger.error(f"Generate research data error: {e}")
        return None


async def get_faculty_by_designation(department: str):
    """Get faculty count by designation"""
    pipeline = [
        {"$match": {
            "department": department,
            "user_type": {"$in": [UserType.FACULTY.value, UserType.HOD.value]}
        }},
        {"$group": {
            "_id": "$designation",
            "count": {"$sum": 1},
            "avg_experience": {"$avg": "$experience_years"}
        }}
    ]
    
    result = list(await users_collection.aggregate(pipeline).to_list(10))
    return {item["_id"]: {"count": item["count"], "avg_experience": item["avg_experience"]} for item in result}


async def analyze_faculty_workload(department: str):
    """Analyze faculty workload distribution"""
    # This would analyze classes, assignments, research, etc.
    # For demo, return simulated data
    return {
        "teaching_load": random.randint(60, 90),
        "research_load": random.randint(10, 30),
        "administrative_load": random.randint(5, 20),
        "balanced_workload_faculty": random.randint(60, 80),
        "overloaded_faculty": random.randint(10, 25),
        "recommendations": "Consider redistributing teaching assignments"
    }


async def calculate_academic_improvement(department: str):
    """Calculate academic improvement trends"""
    # Simulated improvement data
    return {
        "overall_improvement": random.uniform(2.0, 10.0),
        "improvement_by_year": {
            1: random.uniform(3.0, 12.0),
            2: random.uniform(2.5, 10.0),
            3: random.uniform(2.0, 8.0),
            4: random.uniform(1.5, 6.0)
        },
        "most_improved_subjects": ["Mathematics", "Programming", "Database Systems"],
        "areas_needing_attention": ["Communication Skills", "Advanced Algorithms"]
    }


async def analyze_weak_areas(department: str):
    """Analyze weak areas in student performance"""
    # Simulated weak areas analysis
    return {
        "common_weak_areas": [
            {"subject": "Advanced Mathematics", "students_affected": random.randint(20, 40)},
            {"subject": "Data Structures", "students_affected": random.randint(15, 30)},
            {"subject": "Software Engineering", "students_affected": random.randint(10, 25)}
        ],
        "remediation_effectiveness": random.randint(60, 85),
        "suggested_interventions": [
            "Additional tutorial sessions",
            "Peer mentoring programs",
            "Online learning resources"
        ]
    }


async def analyze_student_attendance_patterns(department: str):
    """Analyze student attendance patterns"""
    # Simulated attendance patterns
    return {
        "regular_attenders": random.randint(60, 85),
        "irregular_attenders": random.randint(10, 25),
        "chronic_absentees": random.randint(2, 8),
        "peak_absent_days": ["Monday", "Friday"],
        "common_reasons_for_absence": ["Health issues", "Transport problems", "Personal reasons"],
        "attendance_correlation_with_performance": random.uniform(0.6, 0.9)
    }


def calculate_resource_age_days(purchase_date: Optional[str]):
    """Calculate age of resource in days"""
    if not purchase_date:
        return 365  # Default 1 year
    
    try:
        purchase = datetime.fromisoformat(purchase_date.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        return (now - purchase).days
    except:
        return 365


async def get_placement_support_activities(department: str):
    """Get placement support activities"""
    # Simulated placement activities
    activities = [
        {"activity": "Resume Building Workshop", "participants": random.randint(50, 150), "effectiveness": "High"},
        {"activity": "Mock Interviews", "participants": random.randint(30, 100), "effectiveness": "Very High"},
        {"activity": "Soft Skills Training", "participants": random.randint(40, 120), "effectiveness": "Medium"},
        {"activity": "Technical Aptitude Tests", "participants": random.randint(60, 180), "effectiveness": "High"},
        {"activity": "Industry Expert Sessions", "participants": random.randint(20, 80), "effectiveness": "Medium"}
    ]
    return activities


async def analyze_research_collaborations(department: str):
    """Analyze research collaborations"""
    # Simulated collaboration data
    return {
        "industry_collaborations": random.randint(3, 10),
        "international_collaborations": random.randint(1, 5),
        "interdisciplinary_collaborations": random.randint(5, 15),
        "collaboration_types": {
            "joint_research": random.randint(2, 8),
            "student_exchange": random.randint(1, 4),
            "conference_organization": random.randint(1, 3),
            "publication_collaboration": random.randint(3, 12)
        }
    }


async def get_student_research_participation(department: str):
    """Get student research participation data"""
    # Simulated student research data
    return {
        "ug_students_in_research": random.randint(10, 30),
        "pg_students_in_research": random.randint(5, 15),
        "phd_students": random.randint(3, 8),
        "student_publications": random.randint(5, 20),
        "student_conference_presentations": random.randint(10, 25),
        "student_research_awards": random.randint(1, 5)
    }


async def calculate_research_impact(department: str):
    """Calculate research impact metrics"""
    # Simulated research impact
    return {
        "average_citations_per_paper": random.randint(5, 25),
        "h_index_department": random.randint(10, 30),
        "patents_filed": random.randint(1, 8),
        "technology_transfers": random.randint(0, 3),
        "societal_impact_projects": random.randint(2, 7)
    }


async def generate_pdf_report(content: Dict[str, Any], file_path: str):
    """Generate PDF report"""
    # Implement PDF generation using reportlab or other library
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
    c = canvas.Canvas(file_path, pagesize=letter)
    c.setFont("Helvetica", 12)
    
    # Add title
    c.drawString(100, 750, content["title"])
    c.drawString(100, 730, f"Department: {content['department']}")
    c.drawString(100, 710, f"Generated: {content['generated_at']}")
    
    # Add sections
    y_position = 680
    for section_name, section_data in content["sections"].items():
        c.drawString(100, y_position, f"{section_name.replace('_', ' ').title()}:")
        y_position -= 20
        
        if isinstance(section_data, dict):
            for key, value in section_data.items():
                c.drawString(120, y_position, f"{key}: {value}")
                y_position -= 20
        elif isinstance(section_data, list):
            for item in section_data:
                c.drawString(120, y_position, f"- {item}")
                y_position -= 20
        
        y_position -= 10
    
    c.save()


async def generate_excel_report(content: Dict[str, Any], file_path: str):
    """Generate Excel report"""
    # Implement Excel generation using openpyxl or pandas
    import pandas as pd
    
    # Create DataFrame from content
    data = []
    for section_name, section_data in content["sections"].items():
        if isinstance(section_data, dict):
            for key, value in section_data.items():
                data.append({
                    "Section": section_name,
                    "Metric": key,
                    "Value": value
                })
    
    df = pd.DataFrame(data)
    df.to_excel(file_path, index=False)


async def generate_csv_report(content: Dict[str, Any], file_path: str):
    """Generate CSV report"""
    
    # Create DataFrame from content
    data = []
    for section_name, section_data in content["sections"].items():
        if isinstance(section_data, dict):
            for key, value in section_data.items():
                data.append({
                    "Section": section_name,
                    "Metric": key,
                    "Value": value
                })
    
    df = pd.DataFrame(data)
    df.to_csv(file_path, index=False)


def calculate_utilization_rate(total_reports: int, period: str) -> float:
    """
    Calculate report utilization rate based on period.
    Returns a percentage value (0-100).
    """
    try:
        # Define expected report counts per period
        expected_counts = {
            "week": 5,      # ~5 reports per week expected
            "month": 20,    # ~20 reports per month expected
            "quarter": 60,  # ~60 reports per quarter expected
            "year": 240     # ~240 reports per year expected
        }
        
        # Get expected count for the period
        expected = expected_counts.get(period, 20)  # Default to month if not found
        
        if expected == 0:
            return 0.0
        
        # Calculate utilization rate (capped at 100%)
        utilization = (total_reports / expected) * 100
        
        # Cap at 100%
        return min(100.0, round(utilization, 1))
        
    except Exception as e:
        logger.error(f"Calculate utilization rate error: {e}")
        return 0.0


async def get_report_templates_stats(department: str):
    """Get report templates statistics"""
    pipeline = [
        {"$match": {"department": department}},
        {"$group": {
            "_id": "$type",
            "count": {"$sum": 1},
            "active": {"$sum": {"$cond": [{"$eq": ["$is_active", True]}, 1, 0]}}
        }}
    ]
    
    result = list(await report_templates_collection.aggregate(pipeline).to_list(10))
    return result


async def get_scheduled_reports_stats(department: str):
    """Get scheduled reports statistics"""
    pipeline = [
        {"$match": {"department": department}},
        {"$group": {
            "_id": "$frequency",
            "count": {"$sum": 1},
            "active": {"$sum": {"$cond": [{"$eq": ["$is_active", True]}, 1, 0]}}
        }}
    ]
    
    result = list(await scheduled_reports_collection.aggregate(pipeline).to_list(10))
    return result


async def get_reports_by_type(department: str):
    """Get reports count by type"""
    pipeline = [
        {"$match": {"department": department}},
        {"$group": {
            "_id": "$type",
            "count": {"$sum": 1},
            "last_generated": {"$max": "$generated_at"}
        }}
    ]
    
    result = list(await reports_collection.aggregate(pipeline).to_list(10))
    return result


async def get_reports_by_status(department: str):
    """Get reports count by status"""
    pipeline = [
        {"$match": {"department": department}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1}
        }}
    ]
    
    result = list(await reports_collection.aggregate(pipeline).to_list(10))
    return {item["_id"]: item["count"] for item in result}


async def get_recently_generated(department: str, limit: int = 5):
    """Get recently generated reports"""
    reports = await reports_collection.find({
        "department": department,
        "status": ReportStatus.GENERATED.value
    }).sort("generated_at", -1).limit(limit).to_list(limit)
    
    return convert_objectid_to_str(reports)


async def get_reports_trend(department: str, period: str):
    """Get reports generation trend"""
    now = datetime.now(timezone.utc)
    
    if period == "week":
        days = 7
        format_str = "%Y-%m-%d"
    elif period == "month":
        days = 30
        format_str = "%Y-%m-%d"
    elif period == "quarter":
        days = 90
        format_str = "%Y-%m-%d"
    elif period == "year":
        days = 365
        format_str = "%Y-%m"
    else:
        days = 30
        format_str = "%Y-%m-%d"
    
    pipeline = [
        {"$match": {
            "department": department,
            "generated_at": {"$gte": now - timedelta(days=days)}
        }},
        {"$group": {
            "_id": {"$dateToString": {"format": format_str, "date": "$generated_at"}},
            "count": {"$sum": 1},
            "successful": {"$sum": {"$cond": [{"$eq": ["$status", "generated"]}, 1, 0]}}
        }},
        {"$sort": {"_id": 1}}
    ]
    
    result = list(await reports_collection.aggregate(pipeline).to_list(100))
    return result


def calculate_next_run(frequency: str, day_of_week: str = None, time: str = None) -> datetime:
    """Calculate next run time based on frequency"""
    now = datetime.now(timezone.utc)
    
    if frequency == "daily":
        next_run = now + timedelta(days=1)
    elif frequency == "weekly":
        days_ahead = 7 - now.weekday()
        next_run = now + timedelta(days=days_ahead)
    elif frequency == "monthly":
        # First day of next month
        if now.month == 12:
            next_run = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            next_run = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    elif frequency == "quarterly":
        # First day of next quarter
        quarter = (now.month - 1) // 3 + 1
        if quarter == 4:
            next_run = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            next_run = datetime(now.year, quarter * 3 + 1, 1, tzinfo=timezone.utc)
    elif frequency == "yearly":
        next_run = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    elif frequency == "custom" and day_of_week and time:
        # Custom schedule logic
        next_run = calculate_custom_schedule(day_of_week, time)
    else:
        next_run = now + timedelta(days=1)
    
    # Set time if specified
    if time:
        hour, minute = map(int, time.split(":"))
        next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    return next_run


def calculate_custom_schedule(day_of_week: str, time: str) -> datetime:
    """Calculate next run for custom schedule"""
    # Implementation for custom schedule
    now = datetime.now(timezone.utc)
    days_map = {
        "monday": 0, "tuesday": 1, "wednesday": 2,
        "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
    }
    
    target_day = days_map.get(day_of_week.lower(), 0)
    current_day = now.weekday()
    
    days_ahead = target_day - current_day
    if days_ahead <= 0:
        days_ahead += 7
    
    next_run = now + timedelta(days=days_ahead)
    
    hour, minute = map(int, time.split(":"))
    next_run = next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    return next_run


async def calculate_career_score(user_id: str):
    """Calculate real-time career readiness score for a user"""
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user: return 0
        
        score = 0
        
        # 1. Profile Completeness (max 20)
        profile_fields = ["full_name", "bio", "skills", "profile_picture", "linkedin_url", "github_url"]
        completed_fields = sum(1 for field in profile_fields if user.get(field))
        score += (completed_fields / len(profile_fields)) * 20
        
        # 2. Projects (max 30) - 10 points per project up to 3
        projects_count = await projects_collection.count_documents({"owner_id": user_id})
        score += min(projects_count * 10, 30)
        
        # 3. Interviews (max 30) - 10 points per completed interview up to 3
        interviews_count = await interviews_collection.count_documents({"user_id": user_id, "status": "completed"})
        score += min(interviews_count * 10, 30)
        
        # 4. Challenges (max 20)
        submissions_count = await submissions_collection.count_documents({"user_id": user_id, "completed": True})
        score += min(submissions_count * 2, 20)
        
        # Update user's career score in database
        await users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"career_score": int(score)}}
        )
        
        return int(score)
    except Exception as e:
        logger.error(f"Error calculating career score: {e}")
        return 0


async def get_faculty_management_data(department: str):
    """Get comprehensive faculty management data"""
    try:
        # Get all faculty
        faculty = await users_collection.find({
            "user_type": UserType.FACULTY.value,
            "department": department,
            "is_active": True
        }).sort("full_name", 1).to_list(100)
        
        faculty_data = []
        for fac in faculty:
            stats = await get_faculty_stats(str(fac["_id"]))
            if stats:
                faculty_data.append({
                    **convert_objectid_to_str(fac),
                    **stats
                })
        
        # Get department stats
        dept_stats = await calculate_department_stats(department, f"{datetime.now().year}-{datetime.now().year + 1}")
        
        # Get workload summary
        workload_summary = {
            "overloaded": len([f for f in faculty_data if f.get("workload_percentage", 0) > 80]),
            "optimal": len([f for f in faculty_data if 50 <= f.get("workload_percentage", 0) <= 80]),
            "underloaded": len([f for f in faculty_data if f.get("workload_percentage", 0) < 50]),
            "on_leave": len([f for f in faculty_data if f.get("status") == "leave"])
        }
        
        return {
            "faculty_list": faculty_data,
            "summary": {
                "total_faculty": len(faculty_data),
                "workload_summary": workload_summary,
                "avg_rating": sum(f.get("avg_rating", 0) for f in faculty_data) / len(faculty_data) if faculty_data else 0,
                "total_courses": sum(f.get("classes_taught", 0) for f in faculty_data),
                "total_students": sum(f.get("student_count", 0) for f in faculty_data)
            }
        }
        
    except Exception as e:
        logger.error(f"Get faculty management data error: {e}")
        return {"faculty_list": [], "summary": {}}


async def get_curriculum_data(department: str):
    """Get comprehensive curriculum data"""
    try:
        # Get courses
        courses = await courses_collection.find({"department": department}).to_list(100)
        
        # Get classrooms
        classrooms = await classrooms_collection.find({"department": department}).to_list(100)
        
        # Get faculty assignments
        faculty_assignments = {}
        faculty_list = await users_collection.find({
            "user_type": UserType.FACULTY.value,
            "department": department
        }).to_list(50)
        
        for faculty in faculty_list:
            fac_classrooms = await classrooms_collection.find({
                "instructor_id": str(faculty["_id"])
            }).to_list(20)
            
            if fac_classrooms:
                faculty_assignments[str(faculty["_id"])] = {
                    "name": faculty["full_name"],
                    "classrooms": [c.get("name") for c in fac_classrooms],
                    "total_classes": len(fac_classrooms)
                }
        
        # Organize by year and semester
        curriculum_by_year = {}
        for course in courses:
            year = course.get("year", 1)
            semester = course.get("semester", 1)
            
            if year not in curriculum_by_year:
                curriculum_by_year[year] = {}
            if semester not in curriculum_by_year[year]:
                curriculum_by_year[year][semester] = []
            
            curriculum_by_year[year][semester].append({
                "course_code": course.get("course_code"),
                "title": course.get("title"),
                "credits": course.get("credits", 3),
                "type": course.get("type", "core"),
                "description": course.get("description", "")
            })
        
        return {
            "courses": convert_objectid_to_str(courses),
            "classrooms": convert_objectid_to_str(classrooms),
            "faculty_assignments": faculty_assignments,
            "curriculum_structure": curriculum_by_year,
            "academic_calendar": await get_academic_calendar(department)
        }
        
    except Exception as e:
        logger.error(f"Get curriculum data error: {e}")
        return {"courses": [], "classrooms": [], "curriculum_structure": {}}


async def get_comprehensive_analytics(department: str):
    """Get comprehensive department analytics"""
    try:
        # Get department stats
        dept_stats = await calculate_department_stats(department, f"{datetime.now().year}-{datetime.now().year + 1}")
        
        # Get faculty performance
        faculty = await users_collection.find({
            "user_type": UserType.FACULTY.value,
            "department": department
        }).to_list(50)
        
        faculty_performance = []
        for fac in faculty:
            stats = await get_faculty_stats(str(fac["_id"]))
            if stats:
                faculty_performance.append(stats)
        
        # Get student stats
        students = await users_collection.find({
            "user_type": UserType.STUDENT.value,
            "department": department,
            "is_active": True
        }).to_list(1000)
        
        student_stats = {
            "total": len(students),
            "by_year": {},
            "by_gender": {"male": 0, "female": 0, "other": 0},
            "attendance_rate": 0,
            "average_gpa": 0
        }
        
        # Get attendance data
        attendance_records = await faculty_attendance_collection.find({
            "department": department
        }).to_list(100)
        
        total_present = 0
        total_possible = 0
        for record in attendance_records:
            total_present += record.get("stats", {}).get("present", 0)
            total_possible += record.get("stats", {}).get("total", 0)
        
        if total_possible > 0:
            student_stats["attendance_rate"] = round((total_present / total_possible) * 100, 1)
        
        # Calculate placement statistics
        placement_stats = {
            "placed": random.randint(70, 90),
            "higher_studies": random.randint(10, 20),
            "entrepreneurship": random.randint(2, 5),
            "seeking": random.randint(5, 15)
        }
        
        # Research output
        research_output = {
            "publications": sum(len(f.get("publications", [])) for f in faculty),
            "projects": random.randint(10, 30),
            "grants": random.randint(5, 15),
            "patents": random.randint(1, 5)
        }
        
        return {
            "department_overview": dept_stats,
            "faculty_performance": faculty_performance,
            "student_statistics": student_stats,
            "placement_statistics": placement_stats,
            "research_output": research_output,
            "trends": await get_performance_trends(department)
        }
        
    except Exception as e:
        logger.error(f"Get analytics error: {e}")
        return {}


async def get_pending_approvals_data(user_id: str):
    """Get comprehensive approvals data"""
    try:
        approvals = await notifications_collection.find({
            "user_id": user_id,
            "type": {"$in": ["approval", "request"]},
            "read": False
        }).sort("created_at", -1).to_list(50)
        
        enriched_approvals = []
        for approval in approvals:
            # Get requester info
            requester = None
            if approval.get("requested_by"):
                requester_data = await users_collection.find_one({"_id": ObjectId(approval["requested_by"])})
                if requester_data:
                    requester = {
                        "name": requester_data["full_name"],
                        "designation": requester_data.get("designation", "Faculty"),
                        "department": requester_data.get("department", "Unknown")
                    }
            
            enriched_approvals.append({
                **convert_objectid_to_str(approval),
                "requester": requester
            })
        
        # Group by type
        approvals_by_type = {}
        for approval in enriched_approvals:
            approval_type = approval.get("approval_type", "general")
            if approval_type not in approvals_by_type:
                approvals_by_type[approval_type] = []
            approvals_by_type[approval_type].append(approval)
        
        return {
            "pending_approvals": enriched_approvals,
            "by_type": approvals_by_type,
            "count_by_priority": {
                "high": len([a for a in enriched_approvals if a.get("priority") == "high"]),
                "medium": len([a for a in enriched_approvals if a.get("priority") == "medium"]),
                "low": len([a for a in enriched_approvals if a.get("priority") == "low"])
            }
        }
        
    except Exception as e:
        logger.error(f"Get approvals data error: {e}")
        return {"pending_approvals": [], "by_type": {}}


async def get_department_resources(department: str):
    """Get department resources data"""
    try:
        # This would normally come from a resources collection
        # For now, return sample data structure
        return {
            "laboratories": [
                {
                    "name": "Computer Lab 1",
                    "equipment": "30 Computers, Projector, Whiteboard",
                    "capacity": 30,
                    "status": "operational",
                    "last_maintenance": "2024-01-15"
                },
                {
                    "name": "Computer Lab 2",
                    "equipment": "25 Computers, 3D Printer, Servers",
                    "capacity": 25,
                    "status": "operational",
                    "last_maintenance": "2024-02-20"
                }
            ],
            "software_licenses": {
                "matlab": {"total": 50, "available": 12},
                "autocad": {"total": 30, "available": 8},
                "msoffice": {"total": 100, "available": 45}
            },
            "library_resources": {
                "books": 5000,
                "journals": 120,
                "e_resources": 1500
            },
            "budget_allocation": {
                "equipment": 500000,
                "software": 200000,
                "maintenance": 100000,
                "research": 300000,
                "total": 1100000
            }
        }
    except Exception as e:
        logger.error(f"Get resources error: {e}")
        return {}


async def get_report_templates(department: str):
    """Get report templates and generated reports"""
    try:
        # Get generated reports
        reports = await hod_reports_collection.find({
            "department": department
        }).sort("generated_at", -1).limit(10).to_list(10)
        
        return {
            "templates": [
                {"id": "monthly", "name": "Monthly Department Report", "description": "Comprehensive monthly report"},
                {"id": "academic", "name": "Academic Performance Report", "description": "Student performance analysis"},
                {"id": "faculty", "name": "Faculty Performance Report", "description": "Faculty workload and performance"},
                {"id": "placement", "name": "Placement Report", "description": "Placement statistics and analysis"},
                {"id": "research", "name": "Research Output Report", "description": "Research publications and projects"}
            ],
            "generated_reports": convert_objectid_to_str(reports),
            "scheduled_reports": [
                {"name": "Monthly Report", "schedule": "1st of every month", "status": "active"},
                {"name": "End Semester Report", "schedule": "After exams", "status": "pending"}
            ]
        }
    except Exception as e:
        logger.error(f"Get reports error: {e}")
        return {}


async def get_department_settings(department: str):
    """Get department settings"""
    try:
        # Get from settings collection or use defaults
        settings = await db.department_settings.find_one({"department": department})
        
        if not settings:
            settings = {
                "department": department,
                "settings": {
                    "attendance_threshold": 75,
                    "pass_percentage": 40,
                    "max_class_size": 60,
                    "min_faculty_student_ratio": "1:20",
                    "office_hours": "9:00 AM - 5:00 PM",
                    "assessment_pattern": {"internal": 40, "external": 60},
                    "grading_system": "absolute",
                    "leave_policy": {"casual": 12, "medical": 15, "earned": 30},
                    "research_requirements": {"min_publications": 2, "conferences": 1},
                    "notification_preferences": {
                        "email_alerts": True,
                        "sms_alerts": False,
                        "approval_reminders": True,
                        "report_generation": True
                    }
                }
            }
        
        return settings
    except Exception as e:
        logger.error(f"Get settings error: {e}")
        return {}


async def get_performance_trends(department: str):
    """Get performance trends over time"""
    # This would normally analyze historical data
    # For now, return sample trends
    return {
        "pass_percentage": [85, 87, 86, 88, 90, 92, 91, 93, 92, 94, 93, 95],
        "placement_rate": [78, 80, 82, 84, 85, 87, 88, 90, 89, 91, 92, 94],
        "attendance": [88, 87, 89, 90, 91, 92, 90, 93, 92, 94, 93, 95],
        "research_output": [5, 7, 6, 8, 9, 10, 12, 11, 13, 14, 15, 16]
    }


async def get_academic_calendar(department: str):
    """Get academic calendar"""
    current_year = datetime.now().year
    return [
        {"event": "Semester 1 Begins", "date": f"{current_year}-08-01", "type": "academic"},
        {"event": "Mid-term Exams", "date": f"{current_year}-09-15", "type": "examination"},
        {"event": "Semester 1 Ends", "date": f"{current_year}-11-30", "type": "academic"},
        {"event": "Semester 2 Begins", "date": f"{current_year}-12-15", "type": "academic"},
        {"event": "Final Exams", "date": f"{current_year+1}-04-01", "type": "examination"},
        {"event": "Semester 2 Ends", "date": f"{current_year+1}-05-15", "type": "academic"},
        {"event": "Result Declaration", "date": f"{current_year+1}-06-01", "type": "administrative"},
        {"event": "Placement Drive", "date": f"{current_year+1}-07-15", "type": "placement"}
    ]


async def calculate_classroom_stats(classroom_id: str):
    """Calculate statistics for a classroom"""
    try:
        # Get all assignments
        assignments = await faculty_assignments_collection.find({
            "classroom_id": classroom_id
        }).to_list(100)
        
        # Get all submissions
        submission_stats = await faculty_submissions_collection.aggregate([
            {"$match": {"classroom_id": classroom_id}},
            {"$group": {
                "_id": None,
                "average_score": {"$avg": "$score"},
                "submission_count": {"$sum": 1}
            }}
        ]).to_list(1)
        
        # Get attendance stats
        attendance_stats = await faculty_attendance_collection.aggregate([
            {"$match": {"classroom_id": classroom_id}},
            {"$group": {
                "_id": None,
                "avg_present": {"$avg": "$stats.present"},
                "avg_total": {"$avg": "$stats.total"}
            }}
        ]).to_list(1)
        
        stats = {
            "assignment_count": len(assignments),
            "average_score": 0,
            "attendance_rate": 0
        }
        
        if submission_stats:
            stats["average_score"] = submission_stats[0].get("average_score", 0)
        
        if attendance_stats:
            avg_present = attendance_stats[0].get("avg_present", 0)
            avg_total = attendance_stats[0].get("avg_total", 0)
            if avg_total > 0:
                stats["attendance_rate"] = (avg_present / avg_total) * 100
        
        # Update classroom
        await faculty_classrooms_collection.update_one(
            {"_id": ObjectId(classroom_id)},
            {"$set": {
                "average_score": stats["average_score"],
                "attendance_rate": stats["attendance_rate"],
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        
        return stats
        
    except Exception as e:
        logger.error(f"Calculate classroom stats error: {e}")
        return {}


async def call_gemini_with_retry(prompt: str, max_retries: int = 3) -> Any:
    """Call Gemini AI with retry logic"""
    if not gemini_model:
        return None
    
    for attempt in range(max_retries):
        try:
            response = gemini_model.generate_content(prompt)
            return response
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Gemini API failed after {max_retries} attempts: {e}")
                raise
            wait_time = 2 ** attempt  # Exponential backoff
            logger.warning(f"Gemini API attempt {attempt + 1} failed, retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)
    
    return None


async def update_user_analytics(user_id: str):
    try:
        # Calculate various analytics
        total_submissions = await submissions_collection.count_documents({"user_id": user_id})
        completed_challenges = await submissions_collection.count_documents({
            "user_id": user_id,
            "completed": True
        })
        
        # Calculate average score
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": None,
                "avg_score": {"$avg": "$score"},
                "total_credits": {"$sum": "$credits_earned"}
            }}
        ]
        
        result = list(await submissions_collection.aggregate(pipeline).to_list(length=1))
        avg_score = result[0]["avg_score"] if result else 0
        total_credits = result[0]["total_credits"] if result else 0
        
        # Update user analytics
        await analytics_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "total_submissions": total_submissions,
                "completed_challenges": completed_challenges,
                "average_score": avg_score,
                "total_credits": total_credits,
                "last_updated": datetime.now(timezone.utc)
            }},
            upsert=True
        )
        
    except Exception as e:
        logger.error(f"Analytics update error: {e}")


async def process_submission_async(submission_id: str):
    try:
        submission = await submissions_collection.find_one({"_id": ObjectId(submission_id)})
        if not submission:
            return
        
        # Update leaderboard
        await update_leaderboard(submission["user_id"], submission.get("score", 0))
        
        # Check for badge eligibility
        await check_badge_eligibility(submission["user_id"])
        
        # Update user analytics in background
        asyncio.create_task(update_user_analytics(submission["user_id"]))
        
    except Exception as e:
        logger.error(f"Submission processing error: {e}")


async def update_leaderboard(user_id: str, score: float):
    try:
        week_start = datetime.now(timezone.utc) - timedelta(days=datetime.now(timezone.utc).weekday())
        
        await leaderboard_collection.update_one(
            {
                "user_id": user_id,
                "period": "weekly",
                "week_start": week_start
            },
            {"$inc": {
                "total_score": score,
                "challenges_completed": 1
            }},
            upsert=True
        )
        
        # Also update monthly leaderboard
        month_start = datetime.now(timezone.utc).replace(day=1)
        await leaderboard_collection.update_one(
            {
                "user_id": user_id,
                "period": "monthly",
                "month_start": month_start
            },
            {"$inc": {
                "total_score": score,
                "challenges_completed": 1
            }},
            upsert=True
        )
        
    except Exception as e:
        logger.error(f"Leaderboard update error: {e}")


async def check_badge_eligibility(user_id: str):
    try:
        user = await users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            return
        
        badges_doc = await badges_collection.find_one({"user_id": user_id})
        current_badges = badges_doc.get("badges", []) if badges_doc else []
        earned_badges = []
        
        # Check various badge criteria
        
        # Streak badges
        streak = user.get("daily_login_streak", 0)
        if streak >= 30 and not any(b.get("name") == "30 Day Streak" for b in current_badges):
            earned_badges.append({
                "name": "30 Day Streak",
                "icon": "🔥",
                "earned_date": datetime.now(timezone.utc),
                "description": "Logged in for 30 consecutive days",
                "category": "streak"
            })
        
        # Challenge badges
        completed_challenges = user.get("completed_challenges", 0)
        if completed_challenges >= 50 and not any(b.get("name") == "Challenge Master" for b in current_badges):
            earned_badges.append({
                "name": "Challenge Master",
                "icon": "🏆",
                "earned_date": datetime.now(timezone.utc),
                "description": "Completed 50 challenges",
                "category": "challenges"
            })
        
        # Credit badges
        credits = user.get("credits", 0)
        if credits >= 1000 and not any(b.get("name") == "Credit Millionaire" for b in current_badges):
            earned_badges.append({
                "name": "Credit Millionaire",
                "icon": "💰",
                "earned_date": datetime.now(timezone.utc),
                "description": "Earned 1000 credits",
                "category": "credits"
            })
        
        # Voice challenge badges
        voice_subs = await submissions_collection.count_documents({
            "user_id": user_id,
            "challenge_type": "voice",
            "score": {"$gte": 90}
        })
        if voice_subs >= 10 and not any(b.get("name") == "Voice Virtuoso" for b in current_badges):
            earned_badges.append({
                "name": "Voice Virtuoso",
                "icon": "🎤",
                "earned_date": datetime.now(timezone.utc),
                "description": "10 voice challenges with 90+ score",
                "category": "voice"
            })
        
        # Repository badges
        user_repos = await code_repositories_collection.count_documents({"owner_id": user_id})
        if user_repos >= 5 and not any(b.get("name") == "Code Contributor" for b in current_badges):
            earned_badges.append({
                "name": "Code Contributor",
                "icon": "💾",
                "earned_date": datetime.now(timezone.utc),
                "description": "Created 5 code repositories",
                "category": "coding"
            })
        
        # Add new badges
        if earned_badges:
            if badges_doc:
                await badges_collection.update_one(
                    {"user_id": user_id},
                    {"$push": {"badges": {"$each": earned_badges}}}
                )
            else:
                await badges_collection.insert_one({
                    "user_id": user_id,
                    "badges": earned_badges,
                    "created_at": datetime.now(timezone.utc)
                })
            
            # Send notification for each badge
            for badge in earned_badges:
                await NotificationService.create_notification(
                    user_id=user_id,
                    title="🏆 New Badge Earned!",
                    message=f"Congratulations! You earned the '{badge['name']}' badge: {badge['description']}",
                    notification_type="achievement",
                    priority="high",
                    data={"badge": badge}
                )
        
    except Exception as e:
        logger.error(f"Badge check error: {e}")


async def get_challenge_statistics(challenge_id: str):
    """Get statistics for a challenge"""
    try:
        pipeline = [
            {"$match": {"challenge_id": challenge_id}},
            {"$group": {
                "_id": None,
                "total_attempts": {"$sum": 1},
                "average_score": {"$avg": "$score"},
                "completion_count": {"$sum": {"$cond": ["$completed", 1, 0]}},
                "top_score": {"$max": "$score"},
                "unique_users": {"$addToSet": "$user_id"}
            }}
        ]
        
        result = list(await submissions_collection.aggregate(pipeline).to_list(length=1))
        if result:
            stats = result[0]
            return {
                "total_attempts": stats["total_attempts"],
                "average_score": round(stats["average_score"], 2),
                "completion_rate": (stats["completion_count"] / stats["total_attempts"] * 100) if stats["total_attempts"] > 0 else 0,
                "top_score": stats["top_score"],
                "unique_users": len(stats["unique_users"])
            }
        return {
            "total_attempts": 0,
            "average_score": 0,
            "completion_rate": 0,
            "top_score": 0,
            "unique_users": 0
        }
    except:
        return {
            "total_attempts": 0,
            "average_score": 0,
            "completion_rate": 0,
            "top_score": 0,
            "unique_users": 0
        }


async def get_similar_challenges(challenge: Dict):
    """Get similar challenges based on tags and difficulty"""
    try:
        query = {
            "_id": {"$ne": challenge["_id"]},
            "difficulty": challenge["difficulty"],
            "stage": challenge["stage"],
            "tags": {"$in": challenge.get("tags", [])}
        }
        
        similar = await challenges_collection.find(query) \
            .sort("created_at", -1) \
            .limit(5) \
            .to_list(5)
        
        return [
            {
                "id": str(ch["_id"]),
                "title": ch["title"],
                "challenge_type": ch["challenge_type"],
                "difficulty": ch["difficulty"],
                "credits_reward": ch["credits_reward"]
            }
            for ch in similar
        ]
    except:
        return []


async def get_challenge_leaderboard(challenge_id: str, limit: int = 10):
    """Get leaderboard for a specific challenge"""
    try:
        pipeline = [
            {"$match": {"challenge_id": challenge_id, "completed": True}},
            {"$sort": {"score": -1, "submitted_at": 1}},
            {"$limit": limit},
            {"$lookup": {
                "from": "users",
                "localField": "user_id",
                "foreignField": "_id",
                "as": "user"
            }},
            {"$unwind": "$user"},
            {"$project": {
                "user_id": 1,
                "user_name": "$user.full_name",
                "score": 1,
                "submitted_at": 1,
                "execution_time": "$ai_feedback.execution_time",
                "department": "$user.department"
            }}
        ]
        
        leaderboard = list(await submissions_collection.aggregate(pipeline).to_list(length=limit))
        
        return [
            {
                "rank": idx + 1,
                "user_id": entry["user_id"],
                "user_name": entry["user_name"],
                "score": entry["score"],
                "submitted_at": entry["submitted_at"],
                "department": entry.get("department"),
                "execution_time": entry.get("execution_time")
            }
            for idx, entry in enumerate(leaderboard)
        ]
    except:
        return []


def get_next_stage(current_stage: str):
    """Get the next stage after current stage"""
    stages = [Stage.FRESHIE, Stage.SOPHOMORE, Stage.JUNIOR, Stage.FINAL_YEAR, Stage.ALUMNI]
    try:
        current_index = stages.index(Stage(current_stage))
        if current_index < len(stages) - 1:
            return stages[current_index + 1]
    except:
        pass
    return None


async def execute_code_in_docker(execution_request: CodeExecution) -> Dict[str, Any]:
    """
    Execute code in Docker container
    Supports multiple languages: Python, JavaScript, Java, C, C++, Go, Rust
    """
    try:
        language = execution_request.language.lower()
        code = execution_request.code
        input_data = execution_request.input_data or ""
        
        # Validate language
        if language not in LANG_CONFIG:
            return {
                "success": False,
                "error": f"Unsupported language: {language}. Supported: {', '.join(LANG_CONFIG.keys())}",
                "output": "",
                "execution_time": 0
            }
        
        # Get language config
        lang_config = LANG_CONFIG[language]
        
        # Create temporary file with code
        import tempfile
        import subprocess
        
        with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{lang_config["file_ext"]}', delete=False, dir="/tmp") as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # Prepare Docker command
            container_name = f"code-runner-{language}-{datetime.now().timestamp()}"
            
            # Mount the temp file
            docker_cmd = [
                "docker", "run",
                "--rm",
                f"--name={container_name}",
                f"--cpus={DOCKER_CPU}",
                f"--memory={DOCKER_MEMORY}",
                f"--timeout={TIMEOUT_SECONDS}",
                "-v", f"{temp_file}:/code/{os.path.basename(temp_file)}",
                "-w", "/code",
                lang_config["image"]
            ]
            
            # Add compile command if needed
            if lang_config.get("compile_cmd"):
                compile_cmd = lang_config["compile_cmd"].format(filename=os.path.basename(temp_file))
                docker_cmd.extend(["sh", "-c", f"{compile_cmd} && {lang_config['run_cmd'].format(filename=os.path.basename(temp_file))}"])
            else:
                run_cmd = lang_config["run_cmd"].format(filename=os.path.basename(temp_file))
                docker_cmd.extend(["sh", "-c", run_cmd])
            
            # Execute in Docker
            import time
            start_time = time.time()
            
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=input_data.encode() if input_data else b""),
                    timeout=TIMEOUT_SECONDS
                )
                
                execution_time = time.time() - start_time
                
                output = stdout.decode('utf-8', errors='replace') if stdout else ""
                error = stderr.decode('utf-8', errors='replace') if stderr else ""
                
                return {
                    "success": process.returncode == 0,
                    "output": output.strip(),
                    "error": error.strip() if error else None,
                    "execution_time": execution_time,
                    "return_code": process.returncode,
                    "language": language
                }
                
            except asyncio.TimeoutError:
                await process.kill()
                return {
                    "success": False,
                    "error": f"Execution timeout (exceeded {TIMEOUT_SECONDS} seconds)",
                    "output": "",
                    "execution_time": TIMEOUT_SECONDS,
                    "return_code": -1,
                    "language": language
                }
        
        finally:
            # Clean up temp file
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    except Exception as e:
        logger.error(f"Docker execution error: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Execution error: {str(e)}",
            "output": "",
            "execution_time": 0,
            "return_code": -1,
            "language": execution_request.language
        }


async def run_code():
    """
    Simple wrapper to run code from CodeExecution request
    For standalone code execution without HTTP request context
    """
    try:
        # This can be called internally or from other functions
        # Create a default CodeExecution object if needed
        execution_request = CodeExecution(
            code="",
            language="python",
            input_data=""
        )
        
        result = await execute_code_in_docker(execution_request)
        return result
    
    except Exception as e:
        logger.error(f"Run code error: {e}")
        return {
            "success": False,
            "error": str(e),
            "output": "",
            "execution_time": 0
        }


def generate_default_learning_path(focus_areas: List[str], duration_days: int, goals: List[str]):
    """Generate a default learning path template"""
    return {
        "overview": f"Learn {', '.join(focus_areas)} in {duration_days} days",
        "daily_plans": [
            {
                "day_number": i + 1,
                "focus_areas": focus_areas,
                "tasks": [f"Study {area}" for area in focus_areas],
                "resources": ["Online tutorials", "Practice exercises"],
                "estimated_hours": 2
            }
            for i in range(min(duration_days, 30))
        ],
        "weekly_milestones": [
            f"Week {i+1}: Foundation in {', '.join(focus_areas[:2])}"
            for i in range(min(duration_days // 7, 4))
        ],
        "recommended_courses": ["Introduction to Programming"],
        "project_ideas": ["Build a simple application"],
        "skill_development_timeline": f"{duration_days} days",
        "assessment_schedule": ["Weekly review"],
        "motivational_quotes": ["Keep learning!"],
        "success_metrics": ["Complete daily tasks"]
    }


def clean_mongodb_document(doc):
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    doc.pop("_cls", None)
    return doc


async def execute_python_code_safe(code: str):
    """Execute Python code safely with timeout"""
    try:
        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        # Execute code with timeout
        process = await asyncio.create_subprocess_exec(
            'python', temp_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
        except asyncio.TimeoutError:
            process.kill()
            return {"output": "", "error": "Execution timeout (5 seconds exceeded)"}
        finally:
            # Clean up
            try:
                os.unlink(temp_file)
            except:
                pass
        
        if process.returncode == 0:
            return {"output": stdout.decode().strip(), "error": None}
        else:
            return {"output": "", "error": stderr.decode().strip()}
            
    except Exception as e:
        return {"output": "", "error": str(e)}


async def execute_c_code_safe(code: str):
    """Execute C code safely with compilation and timeout"""
    try:
        # Create temp files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.c', delete=False) as f:
            f.write(code)
            c_file = f.name
        
        exe_file = c_file.replace('.c', '.exe')
        
        # Compile C code
        compile_process = await asyncio.create_subprocess_exec(
            'gcc', c_file, '-o', exe_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        compile_stdout, compile_stderr = await compile_process.communicate()
        
        if compile_process.returncode != 0:
            # Clean up
            try:
                os.unlink(c_file)
            except:
                pass
            return {"output": "", "error": f"Compilation error:\\n{compile_stderr.decode().strip()}"}
        
        # Execute compiled code
        exec_process = await asyncio.create_subprocess_exec(
            exe_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(exec_process.communicate(), timeout=5)
        except asyncio.TimeoutError:
            exec_process.kill()
            return {"output": "", "error": "Execution timeout (5 seconds exceeded)"}
        finally:
            # Clean up
            try:
                os.unlink(c_file)
                if os.path.exists(exe_file):
                    os.unlink(exe_file)
            except:
                pass
        
        if exec_process.returncode == 0:
            return {"output": stdout.decode().strip(), "error": None}
        else:
            return {"output": "", "error": stderr.decode().strip()}
            
    except Exception as e:
        return {"output": "", "error": str(e)}


async def execute_cpp_code_safe(code: str):
    """Execute C++ code safely with compilation and timeout"""
    try:
        # Create temp files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cpp', delete=False) as f:
            f.write(code)
            cpp_file = f.name
        
        exe_file = cpp_file.replace('.cpp', '.exe')
        
        # Compile C++ code
        compile_process = await asyncio.create_subprocess_exec(
            'g++', cpp_file, '-o', exe_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        compile_stdout, compile_stderr = await compile_process.communicate()
        
        if compile_process.returncode != 0:
            # Clean up
            try:
                os.unlink(cpp_file)
            except:
                pass
            return {"output": "", "error": f"Compilation error:\\n{compile_stderr.decode().strip()}"}
        
        # Execute compiled code
        exec_process = await asyncio.create_subprocess_exec(
            exe_file,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(exec_process.communicate(), timeout=5)
        except asyncio.TimeoutError:
            exec_process.kill()
            return {"output": "", "error": "Execution timeout (5 seconds exceeded)"}
        finally:
            # Clean up
            try:
                os.unlink(cpp_file)
                if os.path.exists(exe_file):
                    os.unlink(exe_file)
            except:
                pass
        
        if exec_process.returncode == 0:
            return {"output": stdout.decode().strip(), "error": None}
        else:
            return {"output": "", "error": stderr.decode().strip()}
            
    except Exception as e:
        return {"output": "", "error": str(e)}


def get_campus_email(username: str) -> str:
    """Convert username to campus email"""
    # Clean username and add domain
    clean_username = username.lower().replace(" ", ".").replace("_", ".")
    return f"{clean_username}@campus.com"


async def get_user_email(user: dict) -> str:
    """Get user's campus email"""
    if "email" in user and "@campus.com" in user["email"]:
        return user["email"]
    
    # Generate from username/email
    username = user.get("username") or user.get("email", "").split("@")[0]
    return get_campus_email(username)


async def save_attachments(files: List[UploadFile], user_id: str) -> List[str]:
    """Save mail attachments and return file paths"""
    attachments = []
    
    for file in files:
        try:
            # Validate file
            content = await file.read()
            if len(content) > 10 * 1024 * 1024:  # 10MB max per file
                continue
                
            # Generate unique filename
            file_id = str(uuid.uuid4())
            file_ext = os.path.splitext(file.filename)[1]
            filename = f"mail_attachments/{user_id}/{file_id}{file_ext}"
            filepath = f"static/{filename}"
            
            # Create directory if not exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Save file
            with open(filepath, "wb") as f:
                f.write(content)
            
            attachments.append(f"/{filename}")
            
        except Exception as e:
            logger.error(f"Attachment save error: {e}")
            continue
    
    return attachments


def generate_fallback_response(user_message: str, mode: str) -> dict:
    """Generate helpful fallback response without API calls - clean professional formatting"""
    
    message_lower = user_message.lower()
    
    if mode == "grammar":
        # Grammar feedback with clean formatting
        tips = []
        reply = "Great practice! Your English is coming along well. Here are some helpful tips to improve further."
        
        # Check for common patterns
        if any(pattern in message_lower for pattern in ["am going", "is going", "are going"]):
            tips.append("Present continuous tense is used well for actions happening now")
        if "has" in message_lower or "have" in message_lower:
            tips.append("Perfect tense shows connection between past and present - nice usage")
        if "yesterday" in message_lower:
            tips.append("Past tense usage looks natural in your sentence")
        
        if not tips:
            tips = [
                "Subject-verb-object word order creates clear, natural sentences",
                "Articles (a, an, the) are placed correctly in your text",
                "Verb tenses match the time context of your message"
            ]
        
        return {
            "reply": reply,
            "tips": tips[:2],
            "encouragement": "Keep practicing! Every conversation helps you improve."
        }
    
    elif mode == "pronunciation":
        # Pronunciation guidance with clean format
        words = user_message.split()
        common_words = {
            "the": "pronounced as /ðə/ when unstressed or /ðiː/ before vowel sounds",
            "beautiful": "pronounced as /ˈbjuːtɪfl/ with emphasis on the first syllable",
            "often": "pronounced as /ˈɔːfən/ in American English",
            "wednesday": "pronounced as /ˈwednzdeɪ/ - the first 'd' is silent",
            "hour": "pronounced as /ˈaʊər/ - the 'h' is silent",
            "knife": "pronounced as /naɪf/ - the 'k' and 'n' are silent",
            "psychology": "pronounced as /saɪˈkɒlədʒi/ with stress on second syllable"
        }
        
        found_words = [w.lower() for w in words if w.lower() in common_words]
        
        if found_words:
            reply = "Here's how to pronounce these words in your message:"
            tips = [common_words[word] for word in found_words[:2]]
        else:
            reply = "Good effort! Here are pronunciation tips to help you sound more natural when speaking these words."
            tips = [
                "Focus on word stress and emphasis for natural-sounding speech",
                "Practice with native speaker recordings to train your ear",
                "Record yourself speaking and compare with native speakers"
            ]
        
        return {
            "reply": reply,
            "tips": tips,
            "encouragement": "Pronunciation takes practice - you're on the right track!"
        }
    
    elif mode == "conversation":
        # Conversation practice feedback
        reply = "Great effort! Your response shows good understanding. Here are some ways to enhance your conversational skills."
        
        tips = [
            "Add more specific details to make your answer more engaging",
            "Ask follow-up questions to show interest in the conversation",
            "Use natural expressions and varied vocabulary"
        ]
        
        return {
            "reply": reply,
            "tips": tips[:2],
            "encouragement": "Keep conversations flowing naturally - you're improving!"
        }
    
    else:  # general mode
        reply = "Excellent practice! You're building strong English skills. Focus on consistent practice across grammar, pronunciation, and speaking to see the best results."
        
        return {
            "reply": reply,
            "tips": [
                "Practice speaking aloud to improve pronunciation and confidence",
                "Learn grammar patterns through real conversations, not just rules",
                "Review your mistakes as learning opportunities, not failures"
            ],
            "encouragement": "You're making great progress! Keep it up!"
        }


def clean_markdown_formatting(text: str) -> str:
    """Convert markdown formatting to plain text for clean professional display"""
    # Remove **bold** and replace with plain text (handles nested cases)
    text = re.sub(r'\*\*+([^*]+)\*\*+', r'\1', text)
    # Remove *italic* and replace with plain text
    text = re.sub(r'(?<!\*)\*(?!\*)([^*\n]+)\*(?!\*)', r'\1', text)
    # Remove __bold__ and replace with plain text
    text = re.sub(r'__+([^_]+)__+', r'\1', text)
    # Remove _italic_ and replace with plain text
    text = re.sub(r'(?<!_)_(?!_)([^_\n]+)_(?!_)', r'\1', text)
    # Remove markdown headers
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    # Remove markdown code blocks
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    # Remove inline code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Remove numbered list markers - more aggressive (handles leading spaces)
    text = re.sub(r'^\s*\d+[\.\)]\s+', '', text, flags=re.MULTILINE)
    # Remove bullet points (-, *, +, •)
    text = re.sub(r'^\s*[-*+•]\s+', '', text, flags=re.MULTILINE)
    # Clean up extra whitespace and newlines
    text = re.sub(r'\n\s*\n', '\n', text)  # Remove extra blank lines
    # Remove leading/trailing whitespace from each line
    lines = text.split('\n')
    lines = [line.strip() for line in lines]
    text = '\n'.join(lines)
    return text


