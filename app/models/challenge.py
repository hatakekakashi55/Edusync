"""
EduSync Backend - Challenge Models
Challenge creation, stages, difficulty, and code execution models.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class Stage(str, Enum):
    FRESHIE = "freshie"
    SOPHOMORE = "sophomore"
    JUNIOR = "junior"
    FINAL_YEAR = "final_year"
    ALUMNI = "alumni"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class ChallengeCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=2000)
    stage: Stage
    challenge_type: str = Field(..., pattern="^(coding|quiz|project|interview_prep|data_analysis|system_design|debugging|optimization|api_design|code_review|voice|presentation|essay|group_discussion|aptitude|listening|reading|writing)$")
    difficulty: Difficulty
    credits_reward: int = Field(100, ge=10, le=10000)
    time_limit: int = Field(30, ge=5, le=120)
    language: str = Field("python", pattern="^(python|javascript|java|c|cpp|go|rust|any)$")
    code_template: Optional[str] = None
    test_cases: Optional[List[Dict[str, Any]]] = []
    requirements: Optional[List[str]] = []
    tags: Optional[List[str]] = []
    acceptance_criteria: Optional[List[str]] = []
    resources: Optional[List[str]] = []
    hints: Optional[List[str]] = []
    learning_objectives: Optional[List[str]] = []
    company_name: Optional[str] = None
    role_description: Optional[str] = None


class CodeExecution(BaseModel):
    code: str = Field(..., min_length=1)
    language: str = Field("python", pattern="^(python|javascript|java|c|cpp|go|rust)$")
    input_data: Optional[str] = ""
    test_cases: Optional[List[Dict[str, Any]]] = None


class VoiceChallengeSubmit(BaseModel):
    challenge_id: str
    audio_text: str
    original_text: str
    time_taken: Optional[int] = 0
