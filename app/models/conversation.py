from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime

class ConversationMessage(BaseModel):
    message_id: str
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

class ConversationSession(BaseModel):
    session_id: str
    session_name: str
    session_type: str  # 'interview', 'recommendation', 'general'
    created_at: datetime
    updated_at: datetime
    message_count: int
    is_active: bool
    metadata: Optional[Dict[str, Any]] = None

class ConversationHistoryResponse(BaseModel):
    sessions: List[ConversationSession]
    total_sessions: int
    total_messages: int
    user_id: str

class ConversationDetailResponse(BaseModel):
    session: ConversationSession
    messages: List[ConversationMessage]
    user_id: str
