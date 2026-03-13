from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class ProjectCompletionSubmission(BaseModel):
    project_id: str
    problem_id: str
    files: List[str]  # List of file IDs or names to evaluate


class FileCreate(BaseModel):
    """Model for creating a new file in a project"""
    filename: str = Field(..., min_length=1, max_length=255, description="Name of the file")
    content: Optional[str] = Field(default="", description="File content")
    language: Optional[str] = Field(default="python", description="Programming language")


class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=20, max_length=5000)
    project_type: str = Field(..., pattern="^(academic|research|hackathon|startup|personal)$")
    tech_stack: List[str] = []
    github_repo: Optional[str] = None
    website: Optional[str] = None
    tags: List[str] = []
    required_skills: List[str] = []
    timeline_days: int = Field(30, ge=1, le=365)
    # ADD THIS LINE for attachments
    attachments: Optional[List[str]] = []


class ProjectCreateForm(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    project_type: str = Field(..., pattern="^(academic|research|hackathon|startup|personal)$")
    tech_stack: str = ""
    tags: str = ""
    timeline_days: int = Field(30, ge=1, le=365)
    attachments: Optional[List[str]] = []


class ProjectFileCreate(BaseModel):
    project_id: str
    file_name: str = Field(..., min_length=1, max_length=200)
    file_path: str = Field(..., min_length=1, max_length=500)
    content: str = ""
    language: str = Field("python", pattern="^(python|javascript|java|c|cpp|html|css|markdown|text)$")


class ProjectFileUpdate(BaseModel):
    file_id: str
    content: str
    change_description: Optional[str] = None


class ProjectVersionCreate(BaseModel):
    project_id: str
    version_name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    files_snapshot: List[Dict[str, Any]] = []
