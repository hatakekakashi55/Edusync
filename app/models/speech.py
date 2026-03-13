"""
EduSync Backend - Speech Models
Speech request and voice chat models.
"""
from pydantic import BaseModel
from typing import Optional


class SpeechRequest(BaseModel):
    text: str
    lang: str = "en"
    language: Optional[str] = "en"
