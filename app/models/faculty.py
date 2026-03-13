"""
EduSync Backend - Faculty Models (non-classroom)
Faculty-specific models for profile and management.
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class ExamCreate(BaseModel):
    title: str
    subject: str
    duration_minutes: int = Field(60, ge=10, le=300)
    questions: List[dict]
    department: str
    year: int
    passing_score: int = Field(40, ge=0, le=100)
    max_attempts: int = Field(1, ge=1, le=10)
    instructions: Optional[str] = None


class QuizCreate(BaseModel):
    title: str
    subject: str
    questions: List[dict]
    time_per_question: int = Field(30, ge=10, le=300)
    difficulty: str
    tags: List[str] = []


class CodeRepositoryCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=10, max_length=1000)
    project_id: Optional[str] = None
    is_public: Optional[bool] = True
    language: str = Field("python", pattern="^(python|javascript|java|c|cpp|go|rust|typescript)$")

    @classmethod
    def validate_language(cls, v):
        return v.lower() if v else "python"


class CommitCreate(BaseModel):
    repository_id: str
    message: str = Field(..., min_length=3, max_length=200)
    files: List[dict] = []
    branch: str = "main"
