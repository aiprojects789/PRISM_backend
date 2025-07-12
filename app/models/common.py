from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from datetime import datetime

class APIResponse(BaseModel):
    """Standard API response model"""
    success: bool
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ErrorResponse(BaseModel):
    """Standard error response model"""
    success: bool = False
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class PaginationResponse(BaseModel):
    """Pagination metadata"""
    page: int
    page_size: int
    total_pages: int
    total_items: int
    has_next: bool
    has_previous: bool