"""
EduSync Backend - Subscription & Licensing Service
Core business logic for license management, EduCredits, validity tracking, and analytics.
"""
import logging
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from bson import ObjectId

from app.database import db, users_collection
from app.models.subscription import CREDIT_COSTS, LicenseTier

logger = logging.getLogger("edusync")

# ===================== COLLECTION REFERENCES =====================
licenses_collection = db.licenses
edu_credits_collection = db.edu_credits
credit_refill_requests_collection = db.credit_refill_requests
subscription_analytics_collection = db.subscription_analytics
renewal_quotes_collection = db.renewal_quotes


class SubscriptionService:
    """Core service for license and credit management"""

    @staticmethod
    def _ensure_utc(dt):
        """Ensure a datetime is UTC-aware (MongoDB returns naive datetimes)"""
        if dt is None:
            return datetime.now(timezone.utc)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    # ===================== LICENSE KEY GENERATION =====================

    @staticmethod
    def generate_license_key(tier: str = "professional") -> str:
        """Generate a unique institutional license key"""
        prefix_map = {
            "starter": "ES-STR",
            "professional": "ES-PRO",
            "enterprise": "ES-ENT",
        }
        prefix = prefix_map.get(tier, "ES-PRO")
        random_part = secrets.token_hex(12).upper()
        # Format: ES-PRO-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX
        formatted = "-".join([random_part[i:i+4] for i in range(0, 24, 4)])
        key = f"{prefix}-{formatted}"
        return key

    @staticmethod
    def hash_license_key(key: str) -> str:
        """Hash a license key for secure storage"""
        return hashlib.sha256(key.encode()).hexdigest()

    # ===================== LICENSE MANAGEMENT =====================

    @staticmethod
    async def create_license(
        college_id: str,
        college_name: str,
        admin_email: str,
        tier: str = "professional",
        total_allowed_users: int = 500,
        validity_days: int = 365,
        contact_phone: str = None,
        address: str = None,
    ) -> Dict[str, Any]:
        """Create a new institutional license"""
        try:
            # Check if college already has an active license
            existing = await licenses_collection.find_one({
                "college_id": college_id,
                "status": "active"
            })
            if existing:
                return {"success": False, "error": "College already has an active license"}

            license_key = SubscriptionService.generate_license_key(tier)
            key_hash = SubscriptionService.hash_license_key(license_key)
            now = datetime.now(timezone.utc)

            license_doc = {
                "license_key_hash": key_hash,
                "license_key_preview": f"{license_key[:10]}...{license_key[-4:]}",
                "college_id": college_id,
                "college_name": college_name,
                "admin_email": admin_email,
                "tier": tier,
                "total_allowed_users": total_allowed_users,
                "current_user_count": 0,
                "status": "active",
                "activation_date": now,
                "expiry_date": now + timedelta(days=validity_days),
                "validity_days": validity_days,
                "contact_phone": contact_phone,
                "address": address,
                "features": SubscriptionService._get_tier_features(tier),
                "created_at": now,
                "updated_at": now,
                "renewal_history": [],
                "usage_stats": {
                    "total_ai_sessions": 0,
                    "total_compilations": 0,
                    "total_quizzes": 0,
                    "total_credits_distributed": 0,
                    "total_credits_consumed": 0,
                },
            }

            # Create/Get Admin User for this college
            # This ensures they have an account to log in and activate
            admin_user = await users_collection.find_one({"email": admin_email})
            if not admin_user:
                from app.utils.auth import hash_password
                # Default password for first login: admin@[college_id]
                temp_password = f"admin@{college_id.lower()}"
                
                new_admin = {
                    "full_name": f"{college_name} Admin",
                    "email": admin_email,
                    "password": hash_password(temp_password),
                    "user_type": "admin",
                    "college_code": college_id,
                    "is_active": True,
                    "is_verified": True,
                    "created_at": now,
                    "updated_at": now,
                }
                await users_collection.insert_one(new_admin)
                logger.info(f"👤 Auto-created Admin account for {admin_email}")
                auto_created_pass = temp_password
            else:
                auto_created_pass = "Using existing account password"

            result = await licenses_collection.insert_one(license_doc)

            logger.info(f"🔑 License created for {college_name} (ID: {college_id})")

            return {
                "success": True,
                "license_key": license_key,
                "license_id": str(result.inserted_id),
                "college_id": college_id,
                "college_name": college_name,
                "tier": tier,
                "admin_email": admin_email,
                "temp_password": auto_created_pass,
                "expiry_date": license_doc["expiry_date"].isoformat(),
                "total_allowed_users": total_allowed_users,
            }
        except Exception as e:
            logger.error(f"Create license error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def activate_license(license_key: str, admin_email: str = None) -> Dict[str, Any]:
        """Activate a license key (Admin enters in admin.html)"""
        try:
            key_hash = SubscriptionService.hash_license_key(license_key)

            license_doc = await licenses_collection.find_one({"license_key_hash": key_hash})
            if not license_doc:
                return {"success": False, "error": "Invalid license key"}

            if license_doc["status"] == "expired":
                return {"success": False, "error": "License has expired. Please renew."}

            if license_doc["status"] == "suspended":
                return {"success": False, "error": "License is suspended. Contact support."}

            # Check expiry
            expiry = SubscriptionService._ensure_utc(license_doc["expiry_date"])
            if datetime.now(timezone.utc) > expiry:
                await licenses_collection.update_one(
                    {"_id": license_doc["_id"]},
                    {"$set": {"status": "expired", "updated_at": datetime.now(timezone.utc)}}
                )
                return {"success": False, "error": "License has expired"}

            # Update activation
            update_data = {
                "last_activated_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            if admin_email:
                update_data["activated_by"] = admin_email

            await licenses_collection.update_one(
                {"_id": license_doc["_id"]},
                {"$set": update_data}
            )

            # Calculate days remaining
            days_remaining = (expiry - datetime.now(timezone.utc)).days

            logger.info(f"✅ License activated for {license_doc['college_name']}")

            return {
                "success": True,
                "college_id": license_doc["college_id"],
                "college_name": license_doc["college_name"],
                "tier": license_doc["tier"],
                "status": "active",
                "expiry_date": expiry.isoformat(),
                "days_remaining": days_remaining,
                "total_allowed_users": license_doc["total_allowed_users"],
                "current_user_count": license_doc["current_user_count"],
                "features": license_doc.get("features", {}),
            }
        except Exception as e:
            logger.error(f"Activate license error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def get_license_status(college_id: str = None, license_key: str = None) -> Dict[str, Any]:
        """Get current license status for Validity Tracker"""
        try:
            query = {}
            if college_id:
                query["college_id"] = college_id
            elif license_key:
                query["license_key_hash"] = SubscriptionService.hash_license_key(license_key)
            else:
                # Get the first active license (for single-tenant setups)
                query["status"] = {"$in": ["active", "pending"]}

            license_doc = await licenses_collection.find_one(query)
            if not license_doc:
                return {"success": False, "error": "No license found", "has_license": False}

            now = datetime.now(timezone.utc)
            expiry = SubscriptionService._ensure_utc(license_doc["expiry_date"])
            days_remaining = max(0, (expiry - now).days)
            total_days = license_doc.get("validity_days", 365)
            days_used = total_days - days_remaining
            health_percentage = max(0, min(100, (days_remaining / total_days) * 100))

            # Auto-expire if past expiry date
            if now > expiry and license_doc["status"] == "active":
                await licenses_collection.update_one(
                    {"_id": license_doc["_id"]},
                    {"$set": {"status": "expired", "updated_at": now}}
                )
                license_doc["status"] = "expired"

            # Determine alert level
            alert_level = "normal"
            alert_message = None
            if days_remaining <= 0:
                alert_level = "critical"
                alert_message = "License has expired! Platform access will be restricted."
            elif days_remaining <= 15:
                alert_level = "danger"
                alert_message = f"License expires in {days_remaining} days! Auto-renewal quote generated."
            elif days_remaining <= 30:
                alert_level = "warning"
                alert_message = f"{days_remaining} days remaining until license expiry."
            elif days_remaining <= 60:
                alert_level = "info"
                alert_message = f"{days_remaining} days remaining."

            return {
                "success": True,
                "has_license": True,
                "license_id": str(license_doc["_id"]),
                "college_id": license_doc["college_id"],
                "college_name": license_doc["college_name"],
                "tier": license_doc["tier"],
                "status": license_doc["status"],
                "activation_date": SubscriptionService._ensure_utc(license_doc.get("activation_date", license_doc["created_at"])).isoformat(),
                "expiry_date": expiry.isoformat(),
                "days_remaining": days_remaining,
                "days_used": days_used,
                "total_days": total_days,
                "health_percentage": round(health_percentage, 1),
                "alert_level": alert_level,
                "alert_message": alert_message,
                "total_allowed_users": license_doc["total_allowed_users"],
                "current_user_count": license_doc["current_user_count"],
                "user_utilization": round(
                    (license_doc["current_user_count"] / license_doc["total_allowed_users"]) * 100, 1
                ) if license_doc["total_allowed_users"] > 0 else 0,
                "features": license_doc.get("features", {}),
                "usage_stats": license_doc.get("usage_stats", {}),
            }
        except Exception as e:
            logger.error(f"Get license status error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def get_all_licenses() -> Dict[str, Any]:
        """Get all licenses (Super Admin dashboard)"""
        try:
            licenses = await licenses_collection.find().sort("created_at", -1).to_list(100)
            now = datetime.now(timezone.utc)
            result = []
            for lic in licenses:
                expiry = SubscriptionService._ensure_utc(lic["expiry_date"])
                days_remaining = max(0, (expiry - now).days)
                health_percentage = max(0, min(100, (days_remaining / lic.get("validity_days", 365)) * 100))
                
                result.append({
                    "license_id": str(lic["_id"]),
                    "college_id": lic["college_id"],
                    "college_name": lic["college_name"],
                    "tier": lic["tier"],
                    "status": lic["status"],
                    "activation_date": SubscriptionService._ensure_utc(lic.get("activation_date", lic["created_at"])).isoformat(),
                    "expiry_date": expiry.isoformat(),
                    "days_remaining": days_remaining,
                    "health_percentage": round(health_percentage, 1),
                    "total_allowed_users": lic["total_allowed_users"],
                    "current_user_count": lic["current_user_count"],
                    "user_utilization": round(
                        (lic["current_user_count"] / max(lic["total_allowed_users"], 1)) * 100, 1
                    ),
                    "license_key_preview": lic.get("license_key_preview", "*****"),
                })
            return {"success": True, "licenses": result}
        except Exception as e:
            logger.error(f"Get all licenses error: {e}")
            return {"success": False, "error": str(e)}

    # ===================== EDUCREDITS MANAGEMENT =====================

    @staticmethod
    async def get_student_edu_credits(user_id: str) -> Dict[str, Any]:
        """Get a student's EduCredit balance and history"""
        try:
            credit_doc = await edu_credits_collection.find_one({"user_id": user_id})

            if not credit_doc:
                # Create default credit record
                now = datetime.now(timezone.utc)
                credit_doc = {
                    "user_id": user_id,
                    "total_credits": 500,
                    "used_credits": 0,
                    "available_credits": 500,
                    "monthly_allocation": 500,
                    "last_refill_date": now,
                    "next_refill_date": now + timedelta(days=30),
                    "consumption_history": [],
                    "refill_history": [{"amount": 500, "source": "initial_allocation", "date": now}],
                    "created_at": now,
                    "updated_at": now,
                }
                await edu_credits_collection.insert_one(credit_doc)

            return {
                "success": True,
                "user_id": user_id,
                "total_credits": credit_doc["total_credits"],
                "used_credits": credit_doc["used_credits"],
                "available_credits": credit_doc["available_credits"],
                "monthly_allocation": credit_doc.get("monthly_allocation", 500),
                "last_refill_date": credit_doc.get("last_refill_date", "").isoformat() if credit_doc.get("last_refill_date") else None,
                "next_refill_date": credit_doc.get("next_refill_date", "").isoformat() if credit_doc.get("next_refill_date") else None,
            }
        except Exception as e:
            logger.error(f"Get EduCredits error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def consume_credits(user_id: str, task_type: str, metadata: dict = None) -> Dict[str, Any]:
        """Consume EduCredits for an AI task"""
        try:
            cost = CREDIT_COSTS.get(task_type, 10)

            credit_doc = await edu_credits_collection.find_one({"user_id": user_id})
            if not credit_doc:
                # Auto-create with default allocation
                credit_doc = await SubscriptionService._init_edu_credits(user_id)

            if credit_doc["available_credits"] < cost:
                return {
                    "success": False,
                    "error": "Insufficient EduCredits",
                    "available": credit_doc["available_credits"],
                    "required": cost,
                    "can_request_refill": True,
                }

            # Deduct credits
            now = datetime.now(timezone.utc)
            consumption_record = {
                "task_type": task_type,
                "cost": cost,
                "timestamp": now,
                "metadata": metadata or {},
            }

            await edu_credits_collection.update_one(
                {"user_id": user_id},
                {
                    "$inc": {
                        "used_credits": cost,
                        "available_credits": -cost,
                    },
                    "$push": {
                        "consumption_history": {
                            "$each": [consumption_record],
                            "$slice": -100,  # Keep last 100 records
                        }
                    },
                    "$set": {"updated_at": now},
                }
            )

            # Update license usage stats
            stat_field = "usage_stats.total_ai_sessions"
            if task_type == "code_compilation":
                stat_field = "usage_stats.total_compilations"
            elif task_type == "daily_quiz":
                stat_field = "usage_stats.total_quizzes"

            await licenses_collection.update_one(
                {"status": "active"},
                {
                    "$inc": {
                        stat_field: 1,
                        "usage_stats.total_credits_consumed": cost,
                    }
                }
            )

            new_balance = credit_doc["available_credits"] - cost

            logger.info(f"💳 {cost} EduCredits consumed by user {user_id} for {task_type}")

            return {
                "success": True,
                "task_type": task_type,
                "credits_consumed": cost,
                "remaining_credits": new_balance,
                "message": f"{cost} EduCredits used for {task_type.replace('_', ' ').title()}",
            }
        except Exception as e:
            logger.error(f"Consume credits error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    async def refill_credits(
        student_ids: List[str] = None,
        department: str = None,
        year: int = None,
        credits_amount: int = 500,
        reason: str = "Monthly refill",
        refilled_by: str = None,
    ) -> Dict[str, Any]:
        """Bulk refill EduCredits (by HOD or Admin)"""
        try:
            query = {"user_type": "student"}
            if student_ids:
                query["_id"] = {"$in": [ObjectId(sid) for sid in student_ids]}
            if department:
                query["department"] = department
            if year:
                query["year"] = year

            students = await users_collection.find(query, {"_id": 1}).to_list(10000)
            if not students:
                return {"success": False, "error": "No matching students found"}

            now = datetime.now(timezone.utc)
            refill_count = 0

            for student in students:
                user_id = str(student["_id"])

                await edu_credits_collection.update_one(
                    {"user_id": user_id},
                    {
                        "$inc": {
                            "total_credits": credits_amount,
                            "available_credits": credits_amount,
                        },
                        "$set": {
                            "last_refill_date": now,
                            "next_refill_date": now + timedelta(days=30),
                            "updated_at": now,
                        },
                        "$push": {
                            "refill_history": {
                                "$each": [{
                                    "amount": credits_amount,
                                    "source": "bulk_refill",
                                    "reason": reason,
                                    "refilled_by": refilled_by,
                                    "date": now,
                                }],
                                "$slice": -50,
                            }
                        },
                    },
                    upsert=True,
                )
                refill_count += 1

            # Update license stats
            total_distributed = refill_count * credits_amount
            await licenses_collection.update_one(
                {"status": "active"},
                {"$inc": {"usage_stats.total_credits_distributed": total_distributed}}
            )

            logger.info(f"🔄 Refilled {credits_amount} EduCredits for {refill_count} students")

            return {
                "success": True,
                "students_refilled": refill_count,
                "credits_per_student": credits_amount,
                "total_distributed": total_distributed,
                "reason": reason,
            }
        except Exception as e:
            logger.error(f"Refill credits error: {e}")
            return {"success": False, "error": str(e)}

    # ===================== STUDENT ONBOARDING =====================

    @staticmethod
    async def bulk_onboard_students(
        csv_data: List[Dict[str, str]],
        college_code: str,
        created_by: str = None,
    ) -> Dict[str, Any]:
        """Process CSV data to create student accounts"""
        try:
            from app.utils.auth import hash_password

            # Verify college code matches active license
            license_doc = await licenses_collection.find_one({
                "college_id": college_code,
                "status": "active"
            })
            if not license_doc:
                return {"success": False, "error": f"No active license found for college code: {college_code}"}

            # Check user limit
            remaining_slots = license_doc["total_allowed_users"] - license_doc["current_user_count"]

            created = []
            failed = []
            skipped = []

            for i, row in enumerate(csv_data):
                if len(created) >= remaining_slots:
                    failed.append({"row": i + 1, "error": "User limit reached"})
                    continue

                email = row.get("email", "").strip()
                full_name = row.get("full_name", row.get("name", "")).strip()
                roll_number = row.get("roll_number", row.get("roll", "")).strip()
                department = row.get("department", row.get("dept", "")).strip()
                year_str = row.get("year", "1").strip()

                if not email or not full_name:
                    failed.append({"row": i + 1, "error": "Missing email or name"})
                    continue

                # Check if user already exists
                existing = await users_collection.find_one({"email": email})
                if existing:
                    skipped.append({"row": i + 1, "email": email, "reason": "Already exists"})
                    continue

                try:
                    year_val = int(year_str) if year_str else 1
                except ValueError:
                    year_val = 1

                # Default password: first 4 chars of name + roll_number
                default_password = f"{full_name[:4].lower()}{roll_number}" if roll_number else f"{full_name[:4].lower()}2026"

                user_data = {
                    "full_name": full_name,
                    "email": email,
                    "password": hash_password(default_password),
                    "user_type": "student",
                    "department": department or "General",
                    "year": year_val,
                    "roll_number": roll_number or None,
                    "college_code": college_code,
                    "stage": "freshie",
                    "credits": 0,
                    "xp": 0,
                    "level": 1,
                    "is_active": True,
                    "is_verified": True,
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                    "onboarded_by": created_by,
                    "daily_login_streak": 0,
                    "weekly_login_streak": 0,
                    "completed_challenges": 0,
                    "projects_completed": 0,
                    "badges": [],
                    "achievements": [],
                    "skills": [],
                    "interests": [],
                    "career_goals": [],
                    "weak_areas": [],
                    "strengths": [],
                }

                result = await users_collection.insert_one(user_data)
                user_id = str(result.inserted_id)

                # Initialize EduCredits for the student
                await SubscriptionService._init_edu_credits(user_id, credits=500)

                created.append({
                    "user_id": user_id,
                    "email": email,
                    "full_name": full_name,
                    "default_password": default_password,
                })

            # Update license user count
            if created:
                await licenses_collection.update_one(
                    {"_id": license_doc["_id"]},
                    {"$inc": {"current_user_count": len(created)}}
                )

            logger.info(f"📋 Bulk onboarded {len(created)} students for {college_code}")

            return {
                "success": True,
                "total_processed": len(csv_data),
                "created": len(created),
                "skipped": len(skipped),
                "failed": len(failed),
                "created_accounts": created,
                "skipped_accounts": skipped,
                "failed_accounts": failed,
            }
        except Exception as e:
            logger.error(f"Bulk onboard error: {e}")
            return {"success": False, "error": str(e)}

    # ===================== RENEWAL & BUDGET PROPOSALS =====================

    @staticmethod
    async def generate_renewal_quote(
        license_key: str = None,
        college_id: str = None,
        proposed_tier: str = None,
        proposed_users: int = None,
        include_gpu_cluster: bool = False,
    ) -> Dict[str, Any]:
        """Generate an auto-renewal budget proposal"""
        try:
            query = {}
            if license_key:
                query["license_key_hash"] = SubscriptionService.hash_license_key(license_key)
            elif college_id:
                query["college_id"] = college_id
            else:
                query["status"] = {"$in": ["active", "expired"]}

            license_doc = await licenses_collection.find_one(query)
            if not license_doc:
                return {"success": False, "error": "License not found"}

            current_tier = license_doc["tier"]
            new_tier = proposed_tier or current_tier
            current_users = license_doc["total_allowed_users"]
            new_users = proposed_users or current_users
            usage_stats = license_doc.get("usage_stats", {})

            # Pricing (annual)
            tier_pricing = {
                "starter": 50000,      # ₹50,000
                "professional": 150000,  # ₹1,50,000
                "enterprise": 500000,    # ₹5,00,000
            }

            base_price = tier_pricing.get(new_tier, 150000)

            # Per-user addon
            if new_users > 500:
                extra_users = new_users - 500
                per_user_cost = 200  # ₹200 per extra user
                user_addon = extra_users * per_user_cost
            else:
                user_addon = 0

            # GPU cluster addon
            gpu_addon = 0
            if include_gpu_cluster:
                gpu_addon = 250000  # ₹2,50,000 for 4x RTX 5090 maintenance

            total_price = base_price + user_addon + gpu_addon

            # ROI calculation based on usage
            total_sessions = usage_stats.get("total_ai_sessions", 0)
            cost_per_session = round(total_price / max(total_sessions, 1), 2)

            now = datetime.now(timezone.utc)
            quote = {
                "quote_id": f"RQ-{secrets.token_hex(4).upper()}",
                "college_id": license_doc["college_id"],
                "college_name": license_doc["college_name"],
                "current_tier": current_tier,
                "proposed_tier": new_tier,
                "current_users": current_users,
                "proposed_users": new_users,
                "pricing": {
                    "base_price": base_price,
                    "user_addon": user_addon,
                    "gpu_cluster_addon": gpu_addon,
                    "total_annual": total_price,
                    "monthly_equivalent": round(total_price / 12, 2),
                    "currency": "INR",
                },
                "roi_metrics": {
                    "total_ai_sessions": total_sessions,
                    "total_compilations": usage_stats.get("total_compilations", 0),
                    "total_quizzes": usage_stats.get("total_quizzes", 0),
                    "cost_per_session": cost_per_session,
                    "credits_distributed": usage_stats.get("total_credits_distributed", 0),
                    "credits_consumed": usage_stats.get("total_credits_consumed", 0),
                },
                "validity": "365 days",
                "generated_at": now,
                "valid_until": now + timedelta(days=30),
                "status": "pending",
            }

            await renewal_quotes_collection.insert_one(quote)

            logger.info(f"📄 Renewal quote generated for {license_doc['college_name']}: ₹{total_price:,}")

            return {"success": True, "quote": quote}
        except Exception as e:
            logger.error(f"Generate renewal quote error: {e}")
            return {"success": False, "error": str(e)}

    # ===================== USAGE ANALYTICS =====================

    @staticmethod
    async def get_usage_analytics(
        college_id: str = None,
        period: str = "month",
    ) -> Dict[str, Any]:
        """Get detailed usage analytics for ROI proof"""
        try:
            now = datetime.now(timezone.utc)
            period_map = {
                "day": timedelta(days=1),
                "week": timedelta(days=7),
                "month": timedelta(days=30),
                "quarter": timedelta(days=90),
                "year": timedelta(days=365),
            }
            since = now - period_map.get(period, timedelta(days=30))

            # Get license info
            query = {"status": {"$in": ["active", "expired"]}}
            if college_id:
                query["college_id"] = college_id
            license_doc = await licenses_collection.find_one(query)

            # Engagement metrics: Total hours on AI features
            ai_sessions = await db.roleplay_sessions.count_documents({
                "started_at": {"$gte": since}
            })

            # Get all EduCredit consumption data
            credit_pipeline = [
                {"$unwind": "$consumption_history"},
                {"$match": {"consumption_history.timestamp": {"$gte": since}}},
                {"$group": {
                    "_id": "$consumption_history.task_type",
                    "count": {"$sum": 1},
                    "total_cost": {"$sum": "$consumption_history.cost"},
                }},
            ]
            consumption_stats = await edu_credits_collection.aggregate(credit_pipeline).to_list(20)

            # Skill growth: Average score progression
            students = await users_collection.find(
                {"user_type": "student"},
                {"_id": 1, "full_name": 1, "credits": 1, "xp": 1, "completed_challenges": 1}
            ).to_list(1000)

            total_students = len(students)
            avg_credits = sum(s.get("credits", 0) for s in students) / max(total_students, 1)
            avg_xp = sum(s.get("xp", 0) for s in students) / max(total_students, 1)
            avg_challenges = sum(s.get("completed_challenges", 0) for s in students) / max(total_students, 1)

            # Resource utilization (GPU cluster simulation)
            resource_utilization = {
                "gpu_cluster": {
                    "name": "4x RTX 5090 Cluster",
                    "total_capacity": 100,
                    "current_usage": min(95, max(15, ai_sessions % 100)),
                    "peak_usage": min(100, max(30, (ai_sessions + 20) % 100)),
                    "avg_usage": min(85, max(10, ai_sessions % 80)),
                    "unit": "%",
                },
                "storage": {
                    "name": "Storage Pool",
                    "total_capacity_gb": 2000,
                    "used_gb": 450 + (total_students * 2),
                    "unit": "GB",
                },
            }

            # Daily activity trend (last 7 days)
            daily_trend = []
            for i in range(7):
                day = now - timedelta(days=6 - i)
                day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)

                day_count = await edu_credits_collection.aggregate([
                    {"$unwind": "$consumption_history"},
                    {"$match": {
                        "consumption_history.timestamp": {"$gte": day_start, "$lt": day_end}
                    }},
                    {"$count": "total"}
                ]).to_list(1)

                daily_trend.append({
                    "date": day_start.strftime("%Y-%m-%d"),
                    "day": day_start.strftime("%a"),
                    "sessions": day_count[0]["total"] if day_count else 0,
                })

            return {
                "success": True,
                "period": period,
                "since": since.isoformat(),
                "engagement": {
                    "total_ai_sessions": ai_sessions,
                    "consumption_by_type": {
                        item["_id"]: {"count": item["count"], "credits_used": item["total_cost"]}
                        for item in consumption_stats
                    },
                    "daily_trend": daily_trend,
                },
                "skill_growth": {
                    "total_students": total_students,
                    "avg_credits": round(avg_credits, 1),
                    "avg_xp": round(avg_xp, 1),
                    "avg_challenges_completed": round(avg_challenges, 1),
                },
                "resource_utilization": resource_utilization,
                "license_info": {
                    "college_name": license_doc.get("college_name", "Unknown") if license_doc else "No License",
                    "tier": license_doc.get("tier", "none") if license_doc else "none",
                    "usage_stats": license_doc.get("usage_stats", {}) if license_doc else {},
                },
            }
        except Exception as e:
            logger.error(f"Get usage analytics error: {e}")
            return {"success": False, "error": str(e)}

    # ===================== MIDDLEWARE: CREDIT PROTECTION =====================

    @staticmethod
    async def check_subscription_and_credits(user_id: str, required_credits: int) -> Dict[str, Any]:
        """
        Middleware check before any AI service access.
        1. Verify college license is valid
        2. Verify student has enough EduCredits
        3. Return permission to proceed
        """
        try:
            # 1. Find the user's college
            user = await users_collection.find_one({"_id": ObjectId(user_id)})
            if not user:
                return {"allowed": False, "error": "User not found"}

            college_code = user.get("college_code")

            # 2. Check college license
            if college_code:
                license_doc = await licenses_collection.find_one({
                    "college_id": college_code,
                    "status": "active"
                })

                if not license_doc:
                    return {
                        "allowed": False,
                        "error": "No active institutional license. Contact your admin.",
                        "error_code": "LICENSE_INACTIVE",
                    }

                # Check expiry
                if datetime.now(timezone.utc) > SubscriptionService._ensure_utc(license_doc["expiry_date"]):
                    return {
                        "allowed": False,
                        "error": "Institutional license has expired. Contact your admin.",
                        "error_code": "LICENSE_EXPIRED",
                    }

            # 3. Check EduCredits
            credit_doc = await edu_credits_collection.find_one({"user_id": user_id})
            if not credit_doc:
                credit_doc = await SubscriptionService._init_edu_credits(user_id)

            if credit_doc["available_credits"] < required_credits:
                return {
                    "allowed": False,
                    "error": f"Insufficient EduCredits. Need {required_credits}, have {credit_doc['available_credits']}.",
                    "error_code": "INSUFFICIENT_CREDITS",
                    "available": credit_doc["available_credits"],
                    "required": required_credits,
                }

            return {
                "allowed": True,
                "available_credits": credit_doc["available_credits"],
                "cost": required_credits,
            }
        except Exception as e:
            logger.error(f"Subscription check error: {e}")
            return {"allowed": False, "error": str(e)}

    # ===================== HELPERS =====================

    @staticmethod
    async def _init_edu_credits(user_id: str, credits: int = 500) -> Dict:
        """Initialize EduCredits for a new student"""
        now = datetime.now(timezone.utc)
        credit_doc = {
            "user_id": user_id,
            "total_credits": credits,
            "used_credits": 0,
            "available_credits": credits,
            "monthly_allocation": credits,
            "last_refill_date": now,
            "next_refill_date": now + timedelta(days=30),
            "consumption_history": [],
            "refill_history": [{"amount": credits, "source": "initial_allocation", "date": now}],
            "created_at": now,
            "updated_at": now,
        }
        await edu_credits_collection.update_one(
            {"user_id": user_id},
            {"$setOnInsert": credit_doc},
            upsert=True,
        )
        return credit_doc

    @staticmethod
    def _get_tier_features(tier: str) -> Dict:
        """Get features for a license tier"""
        features = {
            "starter": {
                "ai_roleplay": True,
                "mock_interview": True,
                "code_compilation": True,
                "daily_quiz": True,
                "ai_tutor": False,
                "speech_analysis": False,
                "gpu_cluster": False,
                "priority_support": False,
                "custom_branding": False,
                "api_access": False,
            },
            "professional": {
                "ai_roleplay": True,
                "mock_interview": True,
                "code_compilation": True,
                "daily_quiz": True,
                "ai_tutor": True,
                "speech_analysis": True,
                "gpu_cluster": False,
                "priority_support": True,
                "custom_branding": False,
                "api_access": True,
            },
            "enterprise": {
                "ai_roleplay": True,
                "mock_interview": True,
                "code_compilation": True,
                "daily_quiz": True,
                "ai_tutor": True,
                "speech_analysis": True,
                "gpu_cluster": True,
                "priority_support": True,
                "custom_branding": True,
                "api_access": True,
            },
        }
        return features.get(tier, features["professional"])
