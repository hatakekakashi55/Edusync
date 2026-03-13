"""
EduSync Backend - Classroom Models
Classroom creation, announcements, assignments, attendance, etc.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date


class ClassroomCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=200)
    department: str
    semester: str
    description: Optional[str] = None
    schedule: Optional[str] = None
    location: Optional[str] = None
    max_students: int = Field(default=50, ge=1, le=500)
    settings: Optional[Dict[str, bool]] = None


class AnnouncementCreate(BaseModel):
    """Model for creating announcements"""
    classroom_id: str
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=1, max_length=5000)


class AssignmentCreateForm(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    classroom_id: str
    type: str = Field("programming", pattern="^(programming|research|quiz|project|presentation|essay|lab|other)$")
    due_date: datetime
    points: int = Field(100, ge=1, le=1000)
    instructions: str
    submission_type: str = Field("file", pattern="^(file|text|code|voice|link)$")
    requirements: Optional[List[str]] = []
    attachments: Optional[List[str]] = []


class AssignmentCreate(BaseModel):
    title: str
    description: str
    classroom_id: str
    due_date: str
    max_score: int = Field(100, ge=1, le=1000)
    submission_type: str = Field("file", pattern="^(file|text|code|link)$")
    attachments: Optional[List[str]] = []


class AssignmentSubmitForm(BaseModel):
    """Model for student submission"""
    assignment_id: str
    submission_text: Optional[str] = None
    submission_code: Optional[str] = None
    submission_link: Optional[str] = None
    notes: Optional[str] = ""


class GradeSubmissionForm(BaseModel):
    """Model for faculty grading"""
    submission_id: str
    score: int = Field(..., ge=0, le=1000)
    feedback: str = Field(default="", max_length=2000)


class StudentCreate(BaseModel):
    first_name: str
    last_name: str
    student_id: str
    email: str  # Using str instead of EmailStr for flexibility
    classrooms: List[str] = []
    department: str
    year: int = Field(1, ge=1, le=5)
    phone: Optional[str] = None
    notes: Optional[str] = None


class AttendanceRecord(BaseModel):
    classroom_id: str
    date: date
    session: str
    period: Optional[str] = None
    students: List[Dict[str, Any]]


class ScheduleCreate(BaseModel):
    classroom_id: str
    subject: str
    day: str
    start_time: str
    end_time: str
    type: str = Field("regular", pattern="^(regular|lab|tutorial|seminar|exam|meeting)$")
    location: Optional[str] = None
    recurrence: str = Field("weekly", pattern="^(weekly|biweekly|monthly|once)$")
    description: Optional[str] = None


class CommunityCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: str
    type: str = Field("general", pattern="^(general|classroom|custom)$")
    classroom_id: Optional[str] = None
    members: Optional[List[str]] = []
    privacy: str = Field("public", pattern="^(public|private|restricted)$")


class ProjectCompletionSubmission(BaseModel):
    problem_id: str
    files: List[str]
