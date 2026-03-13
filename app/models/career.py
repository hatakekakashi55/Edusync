"""
EduSync Backend - Career Models
Interview, resume, portfolio, and job-related models.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.models.challenge import Difficulty


class InterviewRequest(BaseModel):
    company: str
    role: str
    difficulty: Difficulty = Difficulty.MEDIUM
    duration: int = Field(15, ge=5, le=60)
    interview_type: str = Field("technical", pattern="^(technical|hr|mixed)$")


class ResumeUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    summary: Optional[str] = None
    education: Optional[List[Dict[str, Any]]] = None
    experience: Optional[List[Dict[str, Any]]] = None
    skills: Optional[List[str]] = None
    projects: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[str]] = None
    languages: Optional[List[str]] = None
