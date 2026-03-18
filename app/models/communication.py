"""
EduSync Backend - Communication Models
Voice challenges, writing challenges, communication submissions, etc.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone


class VoiceChallengeSentence(BaseModel):
    """Model for voice/read challenge sentences"""
    sentence: str = Field(..., min_length=10, max_length=500)
    difficulty: str = Field(..., pattern="^(easy|medium|hard)$")
    category: str = Field(default="general", pattern="^(general|technical|business|academic|conversational)$")
    language: str = Field(default="en", pattern="^(en|ta)$")
    source: str = Field(default="admin", pattern="^(admin|ai)$")
    is_active: bool = Field(default=True)
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WritingChallenge(BaseModel):
    """Model for writing challenges"""
    topic: str = Field(..., min_length=5, max_length=200)
    description: str = Field(..., min_length=10, max_length=1000)
    difficulty: str = Field(..., pattern="^(easy|medium|hard)$")
    category: str = Field(default="essay", pattern="^(essay|email|report|technical|creative|summary)$")
    word_limit: int = Field(default=300, ge=50, le=2000)
    time_limit: int = Field(default=30, ge=5, le=120)
    source: str = Field(default="admin", pattern="^(admin|ai)$")
    is_active: bool = Field(default=True)
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CommunicationSubmission(BaseModel):
    """Model for communication challenge submissions"""
    user_id: str
    challenge_type: str = Field(..., pattern="^(read|write)$")
    challenge_id: str
    submission_text: str
    time_taken: int
    score: Optional[int] = Field(None, ge=0, le=100)
    feedback: Optional[str] = None
    mistakes: Optional[List[str]] = []
    credits_earned: Optional[int] = 0
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SentenceRequest(BaseModel):
    difficulty: Optional[str] = "medium"
    category: Optional[str] = "general"


class GrammarAnalysisRequest(BaseModel):
    text: str
    context: Optional[str] = None


class CommunicationChatRequest(BaseModel):
    message: str
    mode: Optional[str] = "general"  # grammar, pronunciation, conversation, general
    context: Optional[str] = "general"
    language: Optional[str] = "en"
    chat_history: Optional[List[dict]] = []


class PronunciationAnalysisRequest(BaseModel):
    user_text: str  # What the user said (transcribed)
    reference_text: str = ""  # The expected/correct text
    text: Optional[str] = None  # Alias for user_text (backward compat)
    audio_text: Optional[str] = None
    language: Optional[str] = "en"


class ListeningEvaluationRequest(BaseModel):
    user_answer: str
    actual_sentence: str
    challenge_id: Optional[str] = None
    time_taken: Optional[int] = 0


class ListeningMCQEvaluationRequest(BaseModel):
    selected_index: int
    correct_index: int
    challenge_id: Optional[str] = None
    difficulty: Optional[str] = "medium"


class ListeningGapEvaluationRequest(BaseModel):
    user_answers: List[str]
    correct_answers: List[str]
    challenge_id: Optional[str] = None


class ListeningToneEvaluationRequest(BaseModel):
    selected_tone: str
    correct_tone: str
    challenge_id: Optional[str] = None


class ListeningDirectionEvaluationRequest(BaseModel):
    clicked_point_id: str
    correct_point_id: str
    challenge_id: Optional[str] = None

