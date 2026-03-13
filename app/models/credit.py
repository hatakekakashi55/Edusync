"""
EduSync Backend - Credit Models
Credit awards, transactions, and leaderboard models.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any
from datetime import datetime


class CreditAward(BaseModel):
    task_type: Optional[str] = Field(None, pattern="^(daily_login|voice_challenge|coding_challenge|project_completion|badge_earned|streak_extension|lesson_completion|quiz_completion|peer_review|profile_completion|listening_challenge|reading_challenge|writing_challenge)$")
    task_data: Dict[str, Any] = Field(default={})
    timestamp: Optional[datetime] = None
    
    # Legacy fields for backward compatibility
    credits: Optional[int] = None
    source: Optional[str] = None
    details: Optional[str] = None
    
    @field_validator('task_type', mode='before')
    @classmethod
    def set_task_type(cls, v, info):
        if not v and info.data.get('source'):
            source_map = {
                'listening_challenge': 'listening_challenge',
                'reading_challenge': 'reading_challenge',
                'writing_challenge': 'writing_challenge',
                'voice_challenge': 'voice_challenge',
                'coding_challenge': 'coding_challenge'
            }
            return source_map.get(info.data.get('source'), 'coding_challenge')
        return v or 'coding_challenge'


class CreditTransaction(BaseModel):
    user_id: str
    amount: int
    transaction_type: str = Field(..., pattern="^(award|penalty|purchase|refund|transfer)$")
    source: str
    description: str
    metadata: Optional[Dict[str, Any]] = {}


class LeaderboardFilter(BaseModel):
    period: str = Field("weekly", pattern="^(daily|weekly|monthly|all_time)$")
    limit: int = Field(20, ge=1, le=100)
