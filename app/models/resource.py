"""
EduSync Backend - Resource Models
Resource management, software licenses, maintenance models.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class ResourceType(str, Enum):
    COMPUTERS = "computers"
    NETWORKING = "networking"
    LAB_EQUIPMENT = "lab-equipment"
    SOFTWARE = "software"
    FURNITURE = "furniture"
    OTHER = "other"


class ResourceStatus(str, Enum):
    AVAILABLE = "available"
    IN_USE = "in-use"
    MAINTENANCE = "maintenance"
    DAMAGED = "damaged"
    RESERVED = "reserved"


class ResourceLocation(str, Enum):
    LAB_101 = "lab-101"
    LAB_102 = "lab-102"
    SERVER_ROOM = "server-room"
    FACULTY_ROOM = "faculty-room"
    DEPARTMENT_OFFICE = "department-office"
    OTHER = "other"


class ResourceCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    category: ResourceType
    model: Optional[str] = None
    serial_number: Optional[str] = None
    location: ResourceLocation
    status: ResourceStatus = ResourceStatus.AVAILABLE
    description: Optional[str] = None
    purchase_date: Optional[str] = None
    warranty_expiry: Optional[str] = None
    purchase_cost: Optional[float] = None
    vendor: Optional[str] = None
    notes: Optional[str] = None


class SoftwareLicenseCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=200)
    version: Optional[str] = None
    license_type: str = Field("perpetual", pattern="^(perpetual|annual|subscription)$")
    license_key: Optional[str] = None
    max_users: Optional[int] = None
    expiry_date: Optional[str] = None
    vendor: Optional[str] = None
    cost: Optional[float] = None
    notes: Optional[str] = None


class ResourceRequestCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=1000)
    requested_resource: Optional[str] = None
    priority: str = Field("medium", pattern="^(low|medium|high|urgent)$")
    duration: Optional[str] = None
    purpose: str = Field(..., min_length=10, max_length=500)


class MaintenanceCreate(BaseModel):
    resource_id: str
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=500)
    scheduled_date: str
    maintenance_type: str = Field("routine", pattern="^(routine|repair|upgrade|calibration)$")
    estimated_hours: int = Field(1, ge=1, le=24)
    assigned_to: Optional[str] = None
