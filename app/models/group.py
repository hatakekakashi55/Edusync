"""
EduSync Backend - Group & Project Models
Groups, messages, projects, and collaboration models.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=10, max_length=1000)
    department: str
    year: int = Field(..., ge=1, le=5)
    is_educational: bool = True
    max_members: int = Field(100, ge=2, le=500)
    privacy: str = Field("public", pattern="^(public|private|invite_only)$")


class MessageSend(BaseModel):
    group_id: str
    content: str = Field(..., min_length=1, max_length=2000)
    message_type: str = Field("text", pattern="^(text|file|image|audio|video|code)$")
    reply_to: Optional[str] = None
    file_url: Optional[str] = None
    file_name: Optional[str] = None


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
    filename: str
    content: str = ""
    language: str = "python"


class ProjectFileUpdate(BaseModel):
    content: str
    commit_message: str = "Updated file"


class ProjectVersionCreate(BaseModel):
    content: str
    commit_message: str


class FileCreate(BaseModel):
    """Model for creating a new file in a project"""
    filename: str = Field(..., min_length=1, max_length=255, description="Name of the file")
    content: Optional[str] = Field(default="", description="File content")
    language: Optional[str] = Field(default="python", description="Programming language")


class ProblemStatementCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    organization: Optional[str] = "EduSync AI"
    department: Optional[str] = "General"
    category: Optional[str] = "Web Development"
    theme: Optional[str] = "Smart Education"
    mode: str = Field("admin", pattern="^(admin|ai|manual)$")
    credits: int = Field(100, ge=50, le=1000)
    difficulty: Optional[str] = "Medium"
    constraints: Optional[List[str]] = []
    status: str = "open"


class ProblemStatementUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    organization: Optional[str] = None
    department: Optional[str] = None
    category: Optional[str] = None
    theme: Optional[str] = None
    mode: Optional[str] = None
    credits: Optional[int] = None
    status: Optional[str] = None


class ProjectCompletionSubmission(BaseModel):
    project_id: str
    problem_id: str
    files: List[str]
