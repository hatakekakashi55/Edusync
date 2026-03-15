"""
EduSync Backend - Subscription & Licensing Models
License key activation, EduCredits system, validity tracking, and usage analytics.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class LicenseStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    PENDING = "pending"


class LicenseTier(str, Enum):
    STARTER = "starter"        # Up to 100 users
    PROFESSIONAL = "professional"  # Up to 500 users
    ENTERPRISE = "enterprise"  # Unlimited users


# ===================== LICENSE MODELS =====================

class LicenseActivation(BaseModel):
    """Model for activating an institutional license key"""
    license_key: str = Field(..., min_length=16, max_length=64)
    college_name: Optional[str] = None
    admin_email: Optional[EmailStr] = None


class LicenseCreate(BaseModel):
    """Model for generating a new institutional license (Super Admin only)"""
    college_id: str = Field(..., min_length=2, max_length=50)
    college_name: str = Field(..., min_length=2, max_length=200)
    admin_email: EmailStr
    tier: LicenseTier = LicenseTier.PROFESSIONAL
    total_allowed_users: int = Field(500, ge=10, le=10000)
    validity_days: int = Field(365, ge=30, le=1825)  # 30 days to 5 years
    contact_phone: Optional[str] = None
    address: Optional[str] = None


class LicenseRenew(BaseModel):
    """Model for renewing a license"""
    license_key: str
    additional_days: int = Field(365, ge=30, le=1825)
    additional_users: Optional[int] = Field(None, ge=0)


# ===================== EDUCREDIT MODELS =====================

class CreditAllocation(BaseModel):
    """Model for allocating monthly EduCredits to students"""
    college_id: str
    credits_per_student: int = Field(500, ge=50, le=5000)
    target_department: Optional[str] = None
    target_year: Optional[int] = Field(None, ge=1, le=5)


class CreditConsume(BaseModel):
    """Model for consuming EduCredits for AI tasks"""
    task_type: str = Field(..., pattern="^(ai_roleplay|mock_interview|code_compilation|daily_quiz|ai_tutor|speech_analysis|code_review|project_assist)$")
    task_metadata: Optional[Dict[str, Any]] = {}


class CreditRefillRequest(BaseModel):
    """Model for students requesting extra credits"""
    reason: str = Field(..., min_length=10, max_length=500)
    requested_credits: int = Field(100, ge=50, le=1000)


class BulkCreditRefill(BaseModel):
    """Model for HOD/Admin bulk credit refill"""
    student_ids: Optional[List[str]] = None
    department: Optional[str] = None
    year: Optional[int] = Field(None, ge=1, le=5)
    credits_amount: int = Field(500, ge=50, le=5000)
    reason: str = Field("Monthly refill", min_length=2, max_length=200)


# ===================== STUDENT ONBOARDING MODELS =====================

class StudentBulkOnboard(BaseModel):
    """Model for CSV bulk student creation"""
    college_code: str = Field(..., min_length=4, max_length=20)


# ===================== VALIDITY & ALERTS MODELS =====================

class RenewalQuote(BaseModel):
    """Model for auto-renewal budget proposal"""
    license_key: str
    proposed_tier: Optional[LicenseTier] = None
    proposed_users: Optional[int] = None
    include_gpu_cluster: bool = False


# ===================== USAGE ANALYTICS MODELS =====================

class UsageAnalyticsQuery(BaseModel):
    """Model for querying detailed usage analytics"""
    college_id: Optional[str] = None
    period: str = Field("month", pattern="^(day|week|month|quarter|year)$")
    metric_type: str = Field("all", pattern="^(engagement|skill_growth|resource_utilization|all)$")


# Credit consumption costs (in EduCredits)
CREDIT_COSTS = {
    "ai_roleplay": 50,
    "mock_interview": 50,
    "code_compilation": 5,
    "daily_quiz": 10,
    "ai_tutor": 25,
    "speech_analysis": 30,
    "code_review": 15,
    "project_assist": 40,
}
