"""
EduSync Backend - HOD Models
Faculty management, department stats, approvals, and HOD-specific models.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from enum import Enum


class FacultyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    specialization: str
    designation: str = Field(..., pattern="^(Professor|Associate Professor|Assistant Professor|Lecturer)$")
    department: str


class DepartmentStats(BaseModel):
    department: str
    academic_year: str = Field(default_factory=lambda: f"{datetime.now().year}-{datetime.now().year + 1}")
    period: str = Field("monthly", pattern="^(daily|weekly|monthly|yearly)$")


class FacultyPerformanceRequest(BaseModel):
    faculty_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    metrics: List[str] = ["attendance", "rating", "research", "workload"]


# =============== APPROVAL MODELS ===============

class ApprovalType(str, Enum):
    FACULTY_COMMUNITY = "faculty_community"
    FACULTY_LEAVE = "faculty_leave"
    FACULTY_RESEARCH = "faculty_research"
    RESOURCE_REQUEST = "resource_request"
    CURRICULUM_CHANGE = "curriculum_change"
    BUDGET_ALLOCATION = "budget_allocation"
    EVENT_PERMISSION = "event_permission"
    STUDENT_REQUEST = "student_request"
    OTHER = "other"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"


class ApprovalPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ApprovalRequest(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    approval_type: ApprovalType
    priority: ApprovalPriority = ApprovalPriority.MEDIUM
    department: str
    requested_by: str
    requested_by_name: str
    due_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = {}
    attachments: Optional[List[str]] = []
    approvers: Optional[List[str]] = []
    comments: Optional[List[Dict[str, Any]]] = []


class ApprovalAction(BaseModel):
    approval_id: str
    action: ApprovalStatus
    comments: Optional[str] = None
    notify_requester: bool = True
    notify_approvers: bool = True


class FacultyCommunityRequest(BaseModel):
    community_name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=10, max_length=1000)
    community_type: str = Field(..., pattern="^(classroom|research|professional|social|project)$")
    privacy: str = Field(..., pattern="^(public|private|restricted)$")
    members: List[str] = []
    duration_days: int = Field(30, ge=1, le=365)
    purpose: str = Field(..., min_length=10, max_length=1000)


class FacultyLeaveRequest(BaseModel):
    leave_type: str = Field(..., pattern="^(casual|medical|earned|maternity|paternity|academic|other)$")
    start_date: date
    end_date: date
    reason: str = Field(..., min_length=10, max_length=1000)
    emergency_contact: Optional[str] = None
    attachments: Optional[List[str]] = []
    assign_substitute: Optional[bool] = False
    substitute_faculty_id: Optional[str] = None


class ResourceRequest(BaseModel):
    resource_type: str = Field(..., pattern="^(equipment|software|book|laboratory|room|other)$")
    item_name: str
    quantity: int = Field(1, ge=1, le=100)
    purpose: str
    urgency: str = Field("normal", pattern="^(normal|urgent|critical)$")
    estimated_cost: Optional[float] = None
    vendor_details: Optional[Dict[str, Any]] = None
    attachments: Optional[List[str]] = []


class BudgetAllocationRequest(BaseModel):
    purpose: str
    amount: float = Field(..., gt=0)
    category: str = Field(..., pattern="^(research|infrastructure|training|event|equipment|other)$")
    justification: str
    timeline_months: int = Field(3, ge=1, le=12)
    expected_outcomes: List[str] = []
    supporting_docs: Optional[List[str]] = []
