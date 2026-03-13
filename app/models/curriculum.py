"""
EduSync Backend - Curriculum Models
Course, syllabus, academic calendar, and program structure models.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date


class CourseCreate(BaseModel):
    course_code: str = Field(..., min_length=2, max_length=20)
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    credits: int = Field(3, ge=1, le=10)
    department: str
    semester: int = Field(..., ge=1, le=8)
    year: int = Field(..., ge=1, le=4)
    course_type: str = Field("core", pattern="^(core|elective|lab|project|seminar)$")
    prerequisites: Optional[List[str]] = []
    learning_outcomes: Optional[List[str]] = []
    syllabus: Optional[List[Dict[str, Any]]] = []
    textbooks: Optional[List[str]] = []
    references: Optional[List[str]] = []


class SyllabusCreate(BaseModel):
    course_id: str
    week_number: int
    topic: str
    subtopics: List[str]
    learning_objectives: List[str]
    teaching_method: str
    assessment_method: str
    resources: List[str]


class AcademicCalendarCreate(BaseModel):
    event_name: str
    event_type: str = Field(..., pattern="^(academic|examination|holiday|event|meeting|workshop)$")
    start_date: date
    end_date: date
    description: Optional[str] = None
    venue: Optional[str] = None
    target_audience: Optional[List[str]] = []


class FacultyAssignment(BaseModel):
    course_id: str
    faculty_id: str
    role: str = Field(..., pattern="^(instructor|co-instructor|lab_assistant|tutor)$")
    section: Optional[str] = None
    schedule: Optional[Dict[str, Any]] = None


class ProgramStructure(BaseModel):
    program_name: str
    department: str
    duration_years: int = Field(4, ge=3, le=6)
    total_credits: int = Field(160, ge=120, le=240)
    core_credits: int
    elective_credits: int
    project_credits: int
    courses_by_semester: Dict[str, List[str]]


class SyllabusPDFUpload(BaseModel):
    course_id: str
    extract_units: bool = True
    unit_count: int = Field(5, ge=1, le=10)


class UnitCreate(BaseModel):
    course_id: str
    unit_number: int
    title: str
    description: str
    topics: List[str] = []
    learning_outcomes: List[str] = []
    references: List[str] = []
