"""
EduSync Backend - Background Tasks
Auto-extracted from main.py
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from bson import ObjectId

from app.database import *
from app.config import *

logger = logging.getLogger("edusync")

# =============== BACKGROUND TASKS ===============
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


        
        

