"""
EduSync Backend - Stage 1 Models
Models for AI Roleplay Sessions, Speech Analysis, and Shadowing Practice.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone


# ==================== ROLEPLAY MODELS ====================

class RoleplayStartRequest(BaseModel):
    """Request to start a new roleplay session."""
    scenario_type: str = Field(..., description="interview, sales, team_lead, customer_support")
    difficulty: str = Field(default="easy", description="easy, medium, hard")


class RoleplayMessageRequest(BaseModel):
    """Request to send a message in a roleplay session."""
    session_id: str = Field(..., description="The active session ID")
    message: str = Field(..., min_length=1, max_length=2000)


class RoleplayEndRequest(BaseModel):
    """Request to end a roleplay session and get evaluation."""
    session_id: str = Field(..., description="The active session ID")


class RoleplayMessage(BaseModel):
    """A single message in a roleplay conversation."""
    role: str = Field(..., description="user or assistant")
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    tone_analysis: Optional[Dict] = None


class RoleplaySession(BaseModel):
    """Full roleplay session tracking model (stored in MongoDB)."""
    session_id: str
    user_id: str
    scenario_type: str
    difficulty: str
    scenario_name: str
    messages: List[Dict] = []
    current_turn: int = 0
    max_turns: int = 8
    status: str = Field(default="active", description="active, completed, abandoned")
    evaluation: Optional[Dict] = None
    credits_earned: int = 0
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None


# ==================== SPEECH ANALYSIS MODELS ====================

class SpeechAnalysisRequest(BaseModel):
    """Request for filler word and pace analysis from audio."""
    transcript: Optional[str] = None  # If already transcribed
    audio_duration_seconds: Optional[float] = None  # Duration of the audio in seconds


class SpeechAnalysisResult(BaseModel):
    """Result of filler word and pace analysis."""
    transcript: str
    total_words: int
    audio_duration_seconds: float
    wpm: float = Field(description="Words per minute")
    pace_rating: str = Field(description="too_slow, slow, good, fast, too_fast")
    pace_feedback: str
    filler_words_found: List[Dict] = Field(description="List of {word, count}")
    filler_word_count: int
    filler_word_percentage: float
    filler_feedback: str
    clarity_score: int = Field(ge=0, le=100)
    overall_fluency_score: int = Field(ge=0, le=100)


# ==================== SHADOWING / PHONEME MODELS ====================

class ShadowPracticeRequest(BaseModel):
    """Request for shadowing practice evaluation."""
    reference_text: str = Field(..., min_length=5, description="The original correct text")
    user_text: Optional[str] = None  # If already transcribed


class ShadowPracticeResult(BaseModel):
    """Result of shadowing practice with similarity scoring."""
    reference_text: str
    user_text: str
    similarity_score: float = Field(ge=0, le=100, description="Levenshtein-based similarity percentage")
    word_accuracy: float = Field(ge=0, le=100, description="Word-level accuracy percentage")
    matching_words: List[str] = []
    missing_words: List[str] = []
    extra_words: List[str] = []
    mispronounced_words: List[Dict] = Field(default=[], description="[{expected, actual, similarity}]")
    phoneme_feedback: str = ""
    overall_score: int = Field(ge=0, le=100)
    tips: List[str] = []


# ==================== TONE ANALYSIS MODEL ====================

class ToneAnalysisRequest(BaseModel):
    """Request for tone analysis of a text message."""
    text: str = Field(..., min_length=1, max_length=2000)
    context: Optional[str] = "general"


class ToneAnalysisResult(BaseModel):
    """Result of tone analysis."""
    tone: str
    formality_level: str
    confidence_level: int
    politeness_score: int
    clarity_score: int
    assertiveness_score: int
    suggestions: List[str] = []
    improved_version: str = ""
