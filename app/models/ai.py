"""
EduSync Backend - AI Models
AI chat, code review, code help, pair programming, learning path, forum models.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any


class AIChatMessage(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    context: Optional[str] = None
    chat_history_id: Optional[str] = None
    stream: bool = False


class CodeReviewRequest(BaseModel):
    code: str
    language: str
    context: Optional[str] = None
    requirements: Optional[List[str]] = None


class AICodeHelpRequest(BaseModel):
    code: Optional[str] = None
    error: Optional[str] = None
    requirement: Optional[str] = None
    language: str = "python"
    context: Optional[str] = None


class PairProgrammingRequest(BaseModel):
    partner_id: str
    language: str = "python"
    session_duration: int = Field(30, ge=10, le=120)


class LearningPathRequest(BaseModel):
    focus_areas: List[str] = Field(..., min_length=1)
    duration_days: int = Field(30, ge=7, le=365)
    goals: List[str] = Field(default_factory=list)

    @field_validator('focus_areas')
    @classmethod
    def validate_focus_areas(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one focus area is required")
        return v


class ForumPostCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    content: str = Field(..., min_length=10, max_length=5000)
    tags: List[str] = []
    category: str = Field(..., pattern="^(question|discussion|help|announcement|project)$")
    is_anonymous: bool = False


class ForumCommentCreate(BaseModel):
    post_id: str
    content: str = Field(..., min_length=1, max_length=1000)
    parent_comment_id: Optional[str] = None


class VoiceChatRequest(BaseModel):
    text: str


class HODAICommand(BaseModel):
    command: str
    context: Optional[str] = None
    department: Optional[str] = None


class FacultyAICommand(BaseModel):
    command: str
    context: Optional[str] = None
    classroom_id: Optional[str] = None
