"""
EduSync Backend - Compiler Models
Code execution and submission models.
"""
from pydantic import BaseModel, Field
from typing import Optional


class CodeSubmission(BaseModel):
    language: str = Field(..., pattern="^(c|cpp|python)$")
    code: str
    module_id: str
    submitted_at: str


class CourseStart(BaseModel):
    language: str = Field(..., pattern="^(c|cpp|python)$")
    started_at: str


class CourseProgress(BaseModel):
    language: str = Field(..., pattern="^(c|cpp|python)$")
    current_module: int = Field(0, ge=0, le=50)
    completed_modules: list = []
    completed_exercises: int = Field(0, ge=0)
    total_credits: int = Field(0, ge=0)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    active: bool = False
    completed: bool = False
    progress: int = Field(0, ge=0, le=100)


class CodeExecution(BaseModel):
    code: str
    language: str
    input_data: Optional[str] = ""
    test_cases: Optional[list] = []


class FileCreate(BaseModel):
    filename: str
    content: Optional[str] = ""
    language: Optional[str] = "python"
