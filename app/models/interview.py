from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime

class Question(BaseModel):
    text: str
    phase: str
    order: int

class Answer(BaseModel):
    question_id: str
    text: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class InterviewSession(BaseModel):
    user_id: str
    current_phase: int
    current_question: int
    follow_up_count: int
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    conversation: List[Dict[str, Any]] = []

class InterviewResponse(BaseModel):
    session_id: str
    question: str
    follow_up: Optional[str] = None
    is_complete: bool = False
    progress: Optional[Dict[str, int]] = None 

class UserAnswer(BaseModel):
    answer: str

class RecommendationQuery(BaseModel):
    category: str
    query: str

class Recommendation(BaseModel):
    title: str
    description: str
    reasons: List[str]
    category: str
