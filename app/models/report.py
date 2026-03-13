"""
EduSync Backend - Report Models
Report generation, scheduling, and template models.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class ReportType(str, Enum):
    ACADEMIC = "academic"
    FACULTY = "faculty"
    ATTENDANCE = "attendance"
    FINANCIAL = "financial"
    RESOURCE = "resource"
    PLACEMENT = "placement"
    RESEARCH = "research"
    INVENTORY = "inventory"
    CUSTOM = "custom"


class ReportStatus(str, Enum):
    GENERATED = "generated"
    PENDING = "pending"
    SCHEDULED = "scheduled"
    FAILED = "failed"
    PROCESSING = "processing"


class ReportGenerate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    type: ReportType
    format: str = Field("pdf", pattern="^(pdf|excel|csv|html|json)$")
    date_range: str = Field("current_month", pattern="^(current_month|current_quarter|current_year|last_month|last_quarter|last_year|custom)$")
    sections: List[str] = []
    parameters: Optional[Dict[str, Any]] = {}
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ReportSchedule(BaseModel):
    template_id: str
    frequency: str = Field("monthly", pattern="^(daily|weekly|monthly|quarterly|yearly|custom)$")
    recipients: List[str] = []
    start_date: str
    end_date: Optional[str] = None
    day_of_week: Optional[str] = None
    time: Optional[str] = None


class ReportTemplateCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = None
    type: ReportType
    format: str = Field("pdf", pattern="^(pdf|excel|csv|html)$")
    sections: Optional[str] = None
    data_sources: List[str] = []
