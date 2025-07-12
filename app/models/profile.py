from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime

class ProfileCreateRequest(BaseModel):
    profile_name: str
    profile_data: Dict[str, Any]
    description: Optional[str] = None

class ProfileUpdateRequest(BaseModel):
    profile_data: Dict[str, Any]
    description: Optional[str] = None

class ProfileResponse(BaseModel):
    profile_id: str
    profile_name: str
    description: Optional[str]
    profile_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    user_id: str

class ProfileListResponse(BaseModel):
    profiles: List[Dict[str, Any]]
    total_count: int
    user_id: str