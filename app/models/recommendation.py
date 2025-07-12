# app/models/recommendation.py - Enhanced recommendation models

from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime

class RecommendationRequest(BaseModel):
    query: str
    category: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

class RecommendationItem(BaseModel):
    title: str
    description: Optional[str] = None
    reasons: List[str] = []
    category: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = None
    external_links: Optional[List[str]] = None

class RecommendationResponse(BaseModel):
    recommendation_id: str
    user_id: str
    query: str
    category: Optional[str] = None
    recommendations: List[RecommendationItem]
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[int] = None
    profile_version: Optional[str] = None
    search_context: Optional[List[Dict[str, Any]]] = None

class RecommendationHistory(BaseModel):
    recommendation_id: str
    user_id: str
    session_id: Optional[str] = None
    query: str
    category: Optional[str] = None
    recommendations_count: int
    created_at: datetime
    feedback: Optional[Dict[str, Any]] = None  # User feedback on recommendations
    clicked_items: List[str] = []  # Track which recommendations user clicked
    rating: Optional[int] = None  # 1-5 star rating
    is_bookmarked: bool = False
    tags: List[str] = []

class RecommendationFeedback(BaseModel):
    recommendation_id: str
    user_id: str
    feedback_type: str  # 'like', 'dislike', 'not_relevant', 'helpful'
    rating: Optional[int] = None  # 1-5 stars
    comment: Optional[str] = None
    clicked_items: List[str] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

class RecommendationAnalytics(BaseModel):
    user_id: str
    total_recommendations: int
    categories_explored: List[str]
    most_common_query_type: str
    average_rating: float
    total_feedback_count: int
    favorite_categories: List[Dict[str, Any]]  # [{"category": "movies", "count": 15}]
    recommendation_frequency: Dict[str, int]  # {"daily": 5, "weekly": 20}
    period_start: datetime
    period_end: datetime