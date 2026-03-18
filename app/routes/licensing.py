"""
EduSync Backend - Licensing & Subscription Routes (Admin Level)
License activation, bulk onboarding, validity tracking, renewal quotes, and usage analytics.
"""
import logging
import csv
import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query, Body
from fastapi.responses import JSONResponse

from app.dependencies import verify_token, require_admin
from app.services.subscription_service import SubscriptionService
from app.models.subscription import (
    LicenseActivation, LicenseCreate, LicenseRenew,
    CreditAllocation, CreditConsume, CreditRefillRequest,
    BulkCreditRefill, StudentBulkOnboard, RenewalQuote,
    UsageAnalyticsQuery, CREDIT_COSTS,
)

logger = logging.getLogger("edusync")

router = APIRouter(tags=["Licensing & Subscription"])


# ===================== LICENSE MANAGEMENT =====================

@router.post("/api/license/generate", tags=["Licensing & Subscription"])
async def generate_license(
    license_data: LicenseCreate,
    current_user: dict = Depends(require_admin),
):
    """Generate a new institutional license key (Super Admin only)"""
    try:
        result = await SubscriptionService.create_license(
            college_id=license_data.college_id,
            college_name=license_data.college_name,
            admin_email=license_data.admin_email,
            tier=license_data.tier.value,
            total_allowed_users=license_data.total_allowed_users,
            validity_days=license_data.validity_days,
            contact_phone=license_data.contact_phone,
            address=license_data.address,
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Generate license error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate license")


@router.post("/api/license/activate", tags=["Licensing & Subscription"])
async def activate_license(
    activation_data: LicenseActivation,
    current_user: dict = Depends(verify_token),
):
    """Activate an institutional license key (Admin panel)"""
    try:
        # Only admin/hod can activate
        if current_user.get("user_type") not in ["admin", "hod"]:
            raise HTTPException(status_code=403, detail="Admin access required to activate license")

        result = await SubscriptionService.activate_license(
            license_key=activation_data.license_key,
            admin_email=current_user.get("email") or "",
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Activate license error: {e}")
        raise HTTPException(status_code=500, detail="Failed to activate license")


@router.get("/api/license/status", tags=["Licensing & Subscription"])
async def get_license_status(
    college_id: Optional[str] = Query(None),
    current_user: dict = Depends(verify_token),
):
    """Get current license status for Validity Tracker (Admin/HOD dashboards)"""
    try:
        college_id = college_id or ""
        result = await SubscriptionService.get_license_status(college_id=college_id)
        return result
    except Exception as e:
        logger.error(f"License status error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get license status")


@router.get("/api/license/all", tags=["Licensing & Subscription"])
async def get_all_licenses(current_user: dict = Depends(verify_token)):
    """Get all licenses (Super Admin only)"""
    try:
        if current_user.get("role") != "super_admin":
            raise HTTPException(status_code=403, detail="Super Admin access required")
        result = await SubscriptionService.get_all_licenses()
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get all licenses error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get all licenses")


# ===================== BULK STUDENT ONBOARDING =====================

@router.post("/api/license/bulk-onboard", tags=["Licensing & Subscription"])
async def bulk_onboard_students(
    college_code: str = Form(...),
    csv_file: UploadFile = File(...),
    current_user: dict = Depends(verify_token),
):
    """Bulk create student accounts from CSV upload (Admin only)"""
    try:
        if current_user.get("user_type") not in ["admin", "hod"]:
            raise HTTPException(status_code=403, detail="Admin access required")

        # Validate file type
        filename = csv_file.filename or ""
        if not filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files are accepted")

        # Read & parse CSV
        content = await csv_file.read()
        text = content.decode("utf-8-sig")  # Handle BOM
        reader = csv.DictReader(io.StringIO(text))
        csv_data = list(reader)

        if not csv_data:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        if len(csv_data) > 5000:
            raise HTTPException(status_code=400, detail="Maximum 5000 students per upload")

        result = await SubscriptionService.bulk_onboard_students(
            csv_data=csv_data,
            college_code=college_code,
            created_by=str(current_user["_id"]),
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk onboard error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process CSV upload")


# ===================== EDUCREDIT ROUTES =====================

@router.get("/api/credits/edu-balance", tags=["EduCredits"])
async def get_edu_credit_balance(
    current_user: dict = Depends(verify_token),
):
    """Get student's EduCredit balance (used in profile.html and student dashboard)"""
    try:
        user_id = str(current_user["_id"])
        result = await SubscriptionService.get_student_edu_credits(user_id)
        return result
    except Exception as e:
        logger.error(f"Get credit balance error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get credit balance")


@router.post("/api/credits/consume", tags=["EduCredits"])
async def consume_edu_credits(
    consume_data: CreditConsume,
    current_user: dict = Depends(verify_token),
):
    """Consume EduCredits for an AI task (Mock interview, Code compilation, etc.)"""
    try:
        user_id = str(current_user["_id"])

        # First check subscription & credits
        check = await SubscriptionService.check_subscription_and_credits(
            user_id=user_id,
            required_credits=CREDIT_COSTS.get(consume_data.task_type, 10),
        )

        if not check["allowed"]:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": check["error"],
                    "error_code": check.get("error_code", "UNKNOWN"),
                    "available": check.get("available"),
                    "required": check.get("required"),
                }
            )

        # Consume credits
        metadata = consume_data.task_metadata or {}
        result = await SubscriptionService.consume_credits(
            user_id=user_id,
            task_type=consume_data.task_type,
            metadata=metadata,
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Consume credits error: {e}")
        raise HTTPException(status_code=500, detail="Failed to consume credits")


@router.post("/api/credits/request-refill", tags=["EduCredits"])
async def request_credit_refill(
    refill_request: CreditRefillRequest,
    current_user: dict = Depends(verify_token),
):
    """Student requests extra EduCredits (appears in Faculty/HOD dashboard)"""
    try:
        user_id = str(current_user["_id"])
        from app.services.subscription_service import credit_refill_requests_collection

        request_doc = {
            "user_id": user_id,
            "user_name": current_user.get("full_name", "Unknown"),
            "user_email": current_user.get("email"),
            "department": current_user.get("department"),
            "year": current_user.get("year"),
            "requested_credits": refill_request.requested_credits,
            "reason": refill_request.reason,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        await credit_refill_requests_collection.insert_one(request_doc)

        return {
            "success": True,
            "message": "Credit refill request submitted. Your faculty/HOD will review it.",
            "requested_credits": refill_request.requested_credits,
        }
    except Exception as e:
        logger.error(f"Request refill error: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit refill request")


@router.put("/api/credits/refill", tags=["EduCredits"])
async def bulk_refill_credits(
    refill_data: BulkCreditRefill,
    current_user: dict = Depends(verify_token),
):
    """HOD/Admin bulk assign EduCredits to students"""
    try:
        if current_user.get("user_type") not in ["admin", "hod", "faculty"]:
            raise HTTPException(status_code=403, detail="Faculty/HOD/Admin access required")

        result = await SubscriptionService.refill_credits(
            student_ids=refill_data.student_ids or [],
            department=refill_data.department or "",
            year=refill_data.year or 1,
            credits_amount=refill_data.credits_amount,
            reason=refill_data.reason,
            refilled_by=str(current_user["_id"]),
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Bulk refill error: {e}")
        raise HTTPException(status_code=500, detail="Failed to refill credits")


@router.get("/api/credits/refill-requests", tags=["EduCredits"])
async def get_refill_requests(
    status_filter: Optional[str] = Query("pending"),
    current_user: dict = Depends(verify_token),
):
    """Get pending credit refill requests (Faculty/HOD dashboard)"""
    try:
        if current_user.get("user_type") not in ["admin", "hod", "faculty"]:
            raise HTTPException(status_code=403, detail="Faculty/HOD/Admin access required")

        from app.services.subscription_service import credit_refill_requests_collection
        from app.dependencies import convert_objectid_to_str

        query = {}
        if status_filter and status_filter != "all":
            query["status"] = status_filter

        # Faculty sees only their department
        if current_user.get("user_type") == "faculty":
            query["department"] = current_user.get("department")

        requests = await credit_refill_requests_collection.find(query).sort(
            "created_at", -1
        ).limit(100).to_list(100)

        return {
            "success": True,
            "requests": convert_objectid_to_str(requests),
            "total": len(requests),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get refill requests error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get refill requests")


@router.post("/api/credits/approve-refill/{request_id}", tags=["EduCredits"])
async def approve_refill_request(
    request_id: str,
    current_user: dict = Depends(verify_token),
):
    """Approve a student's credit refill request"""
    try:
        if current_user.get("user_type") not in ["admin", "hod", "faculty"]:
            raise HTTPException(status_code=403, detail="Faculty/HOD/Admin access required")

        from app.services.subscription_service import credit_refill_requests_collection
        from bson import ObjectId

        request_doc = await credit_refill_requests_collection.find_one({"_id": ObjectId(request_id)})
        if not request_doc:
            raise HTTPException(status_code=404, detail="Request not found")

        if request_doc["status"] != "pending":
            raise HTTPException(status_code=400, detail="Request already processed")

        # Refill credits
        result = await SubscriptionService.refill_credits(
            student_ids=[request_doc["user_id"]],
            credits_amount=request_doc["requested_credits"],
            reason=f"Approved refill request: {request_doc['reason']}",
            refilled_by=str(current_user["_id"]),
        )

        # Update request status
        await credit_refill_requests_collection.update_one(
            {"_id": ObjectId(request_id)},
            {"$set": {
                "status": "approved",
                "approved_by": str(current_user["_id"]),
                "approved_by_name": current_user.get("full_name"),
                "updated_at": datetime.now(timezone.utc),
            }}
        )

        return {
            "success": True,
            "message": f"Approved {request_doc['requested_credits']} credits for {request_doc['user_name']}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Approve refill error: {e}")
        raise HTTPException(status_code=500, detail="Failed to approve refill")


# ===================== RENEWAL & BUDGET =====================

@router.post("/api/license/renewal-quote", tags=["Licensing & Subscription"])
async def generate_renewal_quote(
    quote_data: RenewalQuote,
    current_user: dict = Depends(verify_token),
):
    """Generate an auto-renewal budget proposal & quote"""
    try:
        if current_user.get("user_type") not in ["admin", "hod"]:
            raise HTTPException(status_code=403, detail="Admin/HOD access required")

        proposed_tier_val = quote_data.proposed_tier.value if quote_data.proposed_tier else "starter"
        proposed_users_val = quote_data.proposed_users or 100
        result = await SubscriptionService.generate_renewal_quote(
            license_key=quote_data.license_key,
            proposed_tier=proposed_tier_val,
            proposed_users=proposed_users_val,
            include_gpu_cluster=quote_data.include_gpu_cluster,
        )

        if not result["success"]:
            raise HTTPException(status_code=400, detail=result["error"])

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Renewal quote error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate renewal quote")


# ===================== USAGE ANALYTICS =====================

@router.get("/api/license/analytics", tags=["Licensing & Subscription"])
async def get_usage_analytics(
    college_id: Optional[str] = Query(None),
    period: str = Query("month"),
    current_user: dict = Depends(verify_token),
):
    """Get detailed usage analytics for ROI proof (Admin/HOD dashboards)"""
    try:
        if current_user.get("user_type") not in ["admin", "hod"]:
            raise HTTPException(status_code=403, detail="Admin/HOD access required")

        result = await SubscriptionService.get_usage_analytics(
            college_id=college_id,
            period=period,
        )

        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Analytics failed"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Usage analytics error: {e}")
        raise HTTPException(status_code=500, detail="Failed to get analytics")


# ===================== CREDIT COST INFO =====================

@router.get("/api/credits/costs", tags=["EduCredits"])
async def get_credit_costs():
    """Get EduCredit costs for each task type (public endpoint)"""
    return {
        "success": True,
        "costs": {
            task: {
                "cost": cost,
                "label": task.replace("_", " ").title(),
            }
            for task, cost in CREDIT_COSTS.items()
        },
    }
