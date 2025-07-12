from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import uuid

from app.core.security import get_current_user
from app.core.firebase import get_firestore_client
from app.core.config import get_settings

router = APIRouter()

# Pydantic models for conversation history
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

class SessionRenameRequest(BaseModel):
    new_name: str

class SearchRequest(BaseModel):
    query: str
    session_type: Optional[str] = None
    limit: int = 20

def save_conversation_message(
    user_id: str, 
    session_id: str, 
    role: str, 
    content: str, 
    session_type: str = "interview",
    session_name: str = None,
    metadata: Dict[str, Any] = None
):
    """Helper function to save a conversation message"""
    try:
        db = get_firestore_client()
        message_id = str(uuid.uuid4())
        timestamp = datetime.utcnow()
        
        # Create message document
        message_doc = {
            "message_id": message_id,
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "timestamp": timestamp,
            "metadata": metadata or {}
        }
        
        # Save message to user's conversation collection
        db.collection("user_conversations").document(user_id).collection("messages").document(message_id).set(message_doc)
        
        # Update or create session document
        session_ref = db.collection("user_conversations").document(user_id).collection("sessions").document(session_id)
        session_doc = session_ref.get()
        
        if session_doc.exists:
            # Update existing session
            session_data = session_doc.to_dict()
            session_ref.update({
                "updated_at": timestamp,
                "message_count": session_data.get("message_count", 0) + 1,
                "last_message": content[:100] + "..." if len(content) > 100 else content,
                "last_message_role": role
            })
        else:
            # Create new session
            session_doc_data = {
                "session_id": session_id,
                "user_id": user_id,
                "session_name": session_name or f"{session_type.title()} Session {timestamp.strftime('%Y-%m-%d %H:%M')}",
                "session_type": session_type,
                "created_at": timestamp,
                "updated_at": timestamp,
                "message_count": 1,
                "is_active": True,
                "last_message": content[:100] + "..." if len(content) > 100 else content,
                "last_message_role": role,
                "metadata": metadata or {}
            }
            session_ref.set(session_doc_data)
        
        return message_id
        
    except Exception as e:
        print(f"Error saving conversation message: {e}")
        return None

@router.get("/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    current_user: str = Depends(get_current_user),
    session_type: Optional[str] = Query(None, description="Filter by session type"),
    limit: int = Query(50, description="Number of sessions to return"),
    offset: int = Query(0, description="Number of sessions to skip")
):
    """Get conversation history for the current user (ChatGPT-like)"""
    try:
        db = get_firestore_client()
        
        # Get sessions with optional filtering
        sessions_ref = db.collection("user_conversations").document(current_user).collection("sessions")
        
        query = sessions_ref.where("is_active", "==", True)
        if session_type:
            query = query.where("session_type", "==", session_type)
        
        # Order by updated_at descending and apply pagination
        sessions = query.order_by("updated_at", direction="DESCENDING").limit(limit).offset(offset).stream()
        
        session_list = []
        total_messages = 0
        
        for session in sessions:
            session_data = session.to_dict()
            total_messages += session_data.get("message_count", 0)
            
            session_list.append(ConversationSession(
                session_id=session_data["session_id"],
                session_name=session_data["session_name"],
                session_type=session_data["session_type"],
                created_at=session_data["created_at"],
                updated_at=session_data["updated_at"],
                message_count=session_data.get("message_count", 0),
                is_active=session_data.get("is_active", True),
                metadata=session_data.get("metadata", {})
            ))
        
        return ConversationHistoryResponse(
            sessions=session_list,
            total_sessions=len(session_list),
            total_messages=total_messages,
            user_id=current_user
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conversation history: {str(e)}")

@router.get("/session/{session_id}", response_model=ConversationDetailResponse)
async def get_conversation_details(
    session_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get detailed conversation for a specific session"""
    try:
        db = get_firestore_client()
        
        # Get session info
        session_doc = db.collection("user_conversations").document(current_user).collection("sessions").document(session_id).get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_data = session_doc.to_dict()
        
        # Get all messages for this session
        messages_ref = db.collection("user_conversations").document(current_user).collection("messages")
        messages = messages_ref.where("session_id", "==", session_id).order_by("timestamp").stream()
        
        message_list = []
        for message in messages:
            message_data = message.to_dict()
            message_list.append(ConversationMessage(
                message_id=message_data["message_id"],
                role=message_data["role"],
                content=message_data["content"],
                timestamp=message_data["timestamp"],
                metadata=message_data.get("metadata", {})
            ))
        
        return ConversationDetailResponse(
            session=ConversationSession(
                session_id=session_data["session_id"],
                session_name=session_data["session_name"],
                session_type=session_data["session_type"],
                created_at=session_data["created_at"],
                updated_at=session_data["updated_at"],
                message_count=session_data.get("message_count", 0),
                is_active=session_data.get("is_active", True),
                metadata=session_data.get("metadata", {})
            ),
            messages=message_list,
            user_id=current_user
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conversation details: {str(e)}")

@router.put("/session/{session_id}/rename")
async def rename_conversation_session(
    session_id: str,
    request: SessionRenameRequest,
    current_user: str = Depends(get_current_user)
):
    """Rename a conversation session"""
    try:
        db = get_firestore_client()
        
        # Get and update session
        session_ref = db.collection("user_conversations").document(current_user).collection("sessions").document(session_id)
        session_doc = session_ref.get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_ref.update({
            "session_name": request.new_name,
            "updated_at": datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": f"Session renamed to '{request.new_name}'",
            "session_id": session_id,
            "new_name": request.new_name
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to rename session: {str(e)}")

@router.delete("/session/{session_id}")
async def delete_conversation_session(
    session_id: str,
    current_user: str = Depends(get_current_user)
):
    """Delete a conversation session (soft delete)"""
    try:
        db = get_firestore_client()
        
        # Soft delete session
        session_ref = db.collection("user_conversations").document(current_user).collection("sessions").document(session_id)
        session_doc = session_ref.get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_ref.update({
            "is_active": False,
            "deleted_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": f"Session {session_id} deleted successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")

@router.post("/search")
async def search_conversations(
    request: SearchRequest,
    current_user: str = Depends(get_current_user)
):
    """Search through conversation messages"""
    try:
        db = get_firestore_client()
        
        # Note: Firestore doesn't support full-text search natively
        # This is a basic implementation - for production, consider using Algolia or Elasticsearch
        
        # Get all messages for the user
        messages_ref = db.collection("user_conversations").document(current_user).collection("messages")
        messages = messages_ref.order_by("timestamp", direction="DESCENDING").limit(500).stream()
        
        search_results = []
        query_lower = request.query.lower()
        
        for message in messages:
            message_data = message.to_dict()
            
            # Basic text search in content
            if query_lower in message_data["content"].lower():
                # Get session info for context
                session_doc = db.collection("user_conversations").document(current_user).collection("sessions").document(message_data["session_id"]).get()
                session_data = session_doc.to_dict() if session_doc.exists else {}
                
                # Filter by session type if specified
                if request.session_type and session_data.get("session_type") != request.session_type:
                    continue
                
                search_results.append({
                    "message_id": message_data["message_id"],
                    "session_id": message_data["session_id"],
                    "session_name": session_data.get("session_name", "Unknown Session"),
                    "session_type": session_data.get("session_type", "unknown"),
                    "role": message_data["role"],
                    "content": message_data["content"],
                    "timestamp": message_data["timestamp"],
                    "relevance_snippet": _get_relevant_snippet(message_data["content"], request.query, 150)
                })
                
                if len(search_results) >= request.limit:
                    break
        
        return {
            "success": True,
            "query": request.query,
            "results": search_results,
            "total_found": len(search_results),
            "user_id": current_user
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search conversations: {str(e)}")

@router.get("/stats")
async def get_conversation_stats(
    current_user: str = Depends(get_current_user),
    days: int = Query(30, description="Number of days to analyze")
):
    """Get conversation statistics for the user"""
    try:
        db = get_firestore_client()
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get sessions in date range
        sessions_ref = db.collection("user_conversations").document(current_user).collection("sessions")
        sessions = sessions_ref.where("created_at", ">=", start_date).where("is_active", "==", True).stream()
        
        stats = {
            "total_sessions": 0,
            "total_messages": 0,
            "session_types": {},
            "daily_activity": {},
            "average_messages_per_session": 0,
            "most_active_day": None,
            "longest_session": None
        }
        
        longest_session = {"session_id": None, "message_count": 0, "session_name": ""}
        daily_counts = {}
        
        for session in sessions:
            session_data = session.to_dict()
            stats["total_sessions"] += 1
            
            message_count = session_data.get("message_count", 0)
            stats["total_messages"] += message_count
            
            # Track session types
            session_type = session_data.get("session_type", "unknown")
            stats["session_types"][session_type] = stats["session_types"].get(session_type, 0) + 1
            
            # Track daily activity
            created_date = session_data["created_at"].date() if hasattr(session_data["created_at"], 'date') else datetime.fromisoformat(str(session_data["created_at"])).date()
            date_str = created_date.isoformat()
            daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
            
            # Track longest session
            if message_count > longest_session["message_count"]:
                longest_session = {
                    "session_id": session_data["session_id"],
                    "message_count": message_count,
                    "session_name": session_data.get("session_name", ""),
                    "session_type": session_type
                }
        
        # Calculate averages and most active day
        if stats["total_sessions"] > 0:
            stats["average_messages_per_session"] = round(stats["total_messages"] / stats["total_sessions"], 2)
        
        if daily_counts:
            most_active_date = max(daily_counts, key=daily_counts.get)
            stats["most_active_day"] = {
                "date": most_active_date,
                "session_count": daily_counts[most_active_date]
            }
        
        stats["daily_activity"] = daily_counts
        stats["longest_session"] = longest_session if longest_session["session_id"] else None
        
        return {
            "success": True,
            "stats": stats,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days": days
            },
            "user_id": current_user
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get conversation stats: {str(e)}")

@router.get("/export/{session_id}")
async def export_conversation(
    session_id: str,
    current_user: str = Depends(get_current_user),
    format: str = Query("json", description="Export format: json, txt, or csv")
):
    """Export a conversation session in various formats"""
    try:
        db = get_firestore_client()
        
        # Get session and messages
        session_doc = db.collection("user_conversations").document(current_user).collection("sessions").document(session_id).get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_data = session_doc.to_dict()
        
        # Get all messages for this session
        messages_ref = db.collection("user_conversations").document(current_user).collection("messages")
        messages = messages_ref.where("session_id", "==", session_id).order_by("timestamp").stream()
        
        message_list = []
        for message in messages:
            message_data = message.to_dict()
            message_list.append({
                "timestamp": message_data["timestamp"].isoformat() if hasattr(message_data["timestamp"], 'isoformat') else str(message_data["timestamp"]),
                "role": message_data["role"],
                "content": message_data["content"],
                "metadata": message_data.get("metadata", {})
            })
        
        export_data = {
            "session_info": {
                "session_id": session_data["session_id"],
                "session_name": session_data["session_name"],
                "session_type": session_data["session_type"],
                "created_at": session_data["created_at"].isoformat() if hasattr(session_data["created_at"], 'isoformat') else str(session_data["created_at"]),
                "message_count": session_data.get("message_count", 0)
            },
            "messages": message_list
        }
        
        if format.lower() == "json":
            return {
                "success": True,
                "export_data": export_data,
                "format": "json",
                "filename": f"conversation_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            }
        elif format.lower() == "txt":
            # Convert to plain text format
            text_content = f"Conversation: {session_data['session_name']}\n"
            text_content += f"Type: {session_data['session_type']}\n"
            text_content += f"Created: {session_data['created_at']}\n"
            text_content += "=" * 50 + "\n\n"
            
            for msg in message_list:
                text_content += f"[{msg['timestamp']}] {msg['role'].upper()}:\n"
                text_content += f"{msg['content']}\n\n"
            
            return {
                "success": True,
                "export_data": text_content,
                "format": "txt",
                "filename": f"conversation_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            }
        elif format.lower() == "csv":
            # Convert to CSV format data
            csv_data = []
            csv_data.append(["Timestamp", "Role", "Content", "Session_Name", "Session_Type"])
            
            for msg in message_list:
                csv_data.append([
                    msg['timestamp'],
                    msg['role'],
                    msg['content'].replace('\n', ' ').replace('"', '""'),  # Escape for CSV
                    session_data['session_name'],
                    session_data['session_type']
                ])
            
            return {
                "success": True,
                "export_data": csv_data,
                "format": "csv",
                "filename": f"conversation_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        else:
            raise HTTPException(status_code=400, detail="Unsupported format. Use json, txt, or csv")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export conversation: {str(e)}")

@router.post("/archive/{session_id}")
async def archive_conversation(
    session_id: str,
    current_user: str = Depends(get_current_user)
):
    """Archive a conversation session (keeps it but marks as archived)"""
    try:
        db = get_firestore_client()
        
        # Get and update session
        session_ref = db.collection("user_conversations").document(current_user).collection("sessions").document(session_id)
        session_doc = session_ref.get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_ref.update({
            "is_archived": True,
            "archived_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": f"Session {session_id} archived successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to archive session: {str(e)}")

@router.post("/restore/{session_id}")
async def restore_conversation(
    session_id: str,
    current_user: str = Depends(get_current_user)
):
    """Restore an archived conversation session"""
    try:
        db = get_firestore_client()
        
        # Get and update session
        session_ref = db.collection("user_conversations").document(current_user).collection("sessions").document(session_id)
        session_doc = session_ref.get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_ref.update({
            "is_archived": False,
            "restored_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": f"Session {session_id} restored successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to restore session: {str(e)}")

def _get_relevant_snippet(text: str, query: str, max_length: int = 150) -> str:
    """Extract a relevant snippet around the search query"""
    query_lower = query.lower()
    text_lower = text.lower()
    
    # Find the position of the query in the text
    pos = text_lower.find(query_lower)
    if pos == -1:
        return text[:max_length] + "..." if len(text) > max_length else text
    
    # Calculate snippet boundaries
    start = max(0, pos - max_length // 2)
    end = min(len(text), start + max_length)
    
    snippet = text[start:end]
    
    # Add ellipsis if we're not at the beginning/end
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    
    return snippet