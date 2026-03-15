"""
EduSync Backend - Auth Models
User registration, login, update, and type enums.
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from enum import Enum


class UserType(str, Enum):
    STUDENT = "student"
    FACULTY = "faculty"
    HOD = "hod"
    ADMIN = "admin"


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: str = Field(..., min_length=2, max_length=100)
    user_type: UserType
    department: Optional[str] = None
    year: Optional[int] = Field(None, ge=1, le=5)
    roll_number: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    parent_email: Optional[EmailStr] = None
    parent_phone: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str
    device_info: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    profile_picture: Optional[str] = None
    bio: Optional[str] = None
    skills: Optional[List[str]] = None
    interests: Optional[List[str]] = None
    weak_areas: Optional[List[str]] = None
    career_goals: Optional[List[str]] = None
    theme: Optional[str] = None
