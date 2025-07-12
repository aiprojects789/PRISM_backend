from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None

class UserResponse(BaseModel):
    user_id: str
    email: EmailStr
    display_name: Optional[str] = None
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class UserProfile(BaseModel):
    user_id: str
    profile_data: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime] = None

class UserProfileUpdate(BaseModel):
    profile_data: Dict[str, Any]