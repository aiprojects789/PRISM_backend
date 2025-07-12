# app/routers/conversations.py - Fixed to avoid Firestore index issues

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime, timedelta

from app.core.security import get_current_user
from app.core.firebase import get_firestore_client

router = APIRouter()

# Pydantic models for conversations
class ConversationMessage(BaseModel):
    message_id: str
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime
    session_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ConversationSession(BaseModel):
    session_id: str
    user_id: str
    session_type: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int
    is_active: bool
    last_message_preview: Optional[str] = None

class SaveMessageRequest(BaseModel):
    session_id: str
    role: str
    content: str
    session_type: Optional[str] = "general"
    title: Optional[str] = None

# Helper function to save conversation messages
def save_conversation_message(
    user_id: str, 
    session_id: str, 
    role: str, 
    content: str, 
    session_type: str = "general",
    title: str = None
):
    """Save a conversation message to Firestore - optimized to avoid index issues"""
    try:
        db = get_firestore_client()
        
        # Generate message ID
        message_id = str(uuid.uuid4())
        
        # Create message document
        message_data = {
            "message_id": message_id,
            "session_id": session_id,
            "user_id": user_id,
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow(),
            "session_type": session_type,
            "is_active": True,
            "created_at": datetime.utcnow()
        }
        
        # Save message to user-specific subcollection to avoid complex queries
        db.collection("user_conversations").document(user_id).collection("messages").document(message_id).set(message_data)
        
        # Also save to a backup location for debugging (can be removed later)
        db.collection("conversations").document(message_id).set(message_data)
        
        # Update or create session summary
        session_ref = db.collection("user_conversations").document(user_id).collection("sessions").document(session_id)
        session_doc = session_ref.get()
        
        if session_doc.exists:
            # Update existing session
            session_ref.update({
                "updated_at": datetime.utcnow(),
                "message_count": session_doc.to_dict().get("message_count", 0) + 1,
                "last_message_preview": content[:100] + "..." if len(content) > 100 else content,
                "last_message_role": role
            })
        else:
            # Create new session
            session_data = {
                "session_id": session_id,
                "user_id": user_id,
                "session_type": session_type,
                "title": title or f"{session_type.title()} Session {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "message_count": 1,
                "is_active": True,
                "last_message_preview": content[:100] + "..." if len(content) > 100 else content,
                "last_message_role": role
            }
            session_ref.set(session_data)
        
        print(f"✅ Saved conversation message for user {user_id}, session {session_id}")
        print(f"🔍 Message ID: {message_id}, Role: {role}, Content length: {len(content)}")
        return True
        
    except Exception as e:
        print(f"❌ Error saving conversation message: {e}")
        return False

@router.get("/history")
async def get_conversation_history(
    current_user: str = Depends(get_current_user),
    session_type: Optional[str] = Query(None, description="Filter by session type"),
    limit: int = Query(50, description="Number of sessions to return"),
    offset: int = Query(0, description="Number of sessions to skip")
):
    """Get conversation history for the current user - Firestore index friendly"""
    try:
        db = get_firestore_client()
        
        print(f"📋 Getting conversation history for user: {current_user}")
        
        # Use user-specific subcollection to avoid complex indexes
        sessions_ref = db.collection("user_conversations").document(current_user).collection("sessions")
        
        # Simple query without complex filtering to avoid index requirements
        sessions_query = sessions_ref.where("is_active", "==", True)
        
        # Get all sessions and filter/sort in Python
        all_sessions = list(sessions_query.stream())
        
        # Convert to list and filter by session_type if specified
        sessions_list = []
        for session_doc in all_sessions:
            session_data = session_doc.to_dict()
            
            # Apply session_type filter in Python
            if session_type and session_data.get("session_type") != session_type:
                continue
                
            sessions_list.append(session_data)
        
        # Sort by updated_at descending (most recent first) in Python
        sessions_list.sort(key=lambda x: x.get("updated_at", datetime.min), reverse=True)
        
        # Apply pagination in Python
        paginated_sessions = sessions_list[offset:offset + limit]
        
        # Format response
        conversation_sessions = []
        for session_data in paginated_sessions:
            conversation_sessions.append({
                "session_id": session_data["session_id"],
                "user_id": session_data["user_id"],
                "session_type": session_data.get("session_type", "general"),
                "title": session_data.get("title", "Untitled Session"),
                "created_at": session_data["created_at"].isoformat() if hasattr(session_data["created_at"], 'isoformat') else str(session_data["created_at"]),
                "updated_at": session_data["updated_at"].isoformat() if hasattr(session_data["updated_at"], 'isoformat') else str(session_data["updated_at"]),
                "message_count": session_data.get("message_count", 0),
                "is_active": session_data.get("is_active", True),
                "last_message_preview": session_data.get("last_message_preview", ""),
                "last_message_role": session_data.get("last_message_role", "user")
            })
        
        print(f"✅ Found {len(conversation_sessions)} conversation sessions for user {current_user}")
        
        return {
            "success": True,
            "sessions": conversation_sessions,
            "total_sessions": len(sessions_list),  # Total before pagination
            "returned_sessions": len(conversation_sessions),  # After pagination
            "user_id": current_user,
            "filters": {
                "session_type": session_type,
                "limit": limit,
                "offset": offset
            },
            "storage_type": "user_specific_subcollections"
        }
        
    except Exception as e:
        print(f"❌ Error getting conversation history for user {current_user}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get conversation history: {str(e)}"
        )

@router.get("/session/{session_id}")
async def get_session_messages(
    session_id: str,
    current_user: str = Depends(get_current_user),
    limit: int = Query(100, description="Number of messages to return"),
    offset: int = Query(0, description="Number of messages to skip")
):
    """Get all messages for a specific session - Enhanced with smart reconstruction for all session types"""
    try:
        db = get_firestore_client()
        
        print(f"📋 Getting messages for session: {session_id} (user: {current_user})")
        
        # Get session info from multiple possible locations
        session_data = None
        session_locations = [
            ("user_conversations", current_user, "sessions", session_id),
            ("sessions", None, None, session_id),
            ("conversation_sessions", None, None, session_id),
            ("user_sessions", None, None, session_id),
            ("interview_sessions", None, None, session_id)
        ]
        
        for location in session_locations:
            try:
                if location[1]:  # User-specific subcollection
                    session_ref = db.collection(location[0]).document(location[1]).collection(location[2]).document(location[3])
                else:  # Top-level collection
                    session_ref = db.collection(location[0]).document(location[3])
                
                session_doc = session_ref.get()
                if session_doc.exists:
                    session_data = session_doc.to_dict()
                    if session_data.get("user_id") == current_user:
                        print(f"✅ Found session in {location[0]}")
                        break
            except Exception as e:
                print(f"❌ Error checking {location[0]}: {e}")
        
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Verify ownership
        if session_data.get("user_id") != current_user:
            raise HTTPException(status_code=403, detail="Access denied to this session")
        
        session_type = session_data.get("session_type", "general")
        print(f"✅ Session found. Type: {session_type}, Expected message count: {session_data.get('message_count', 0)}")
        
        # Try to find stored messages first
        messages_list = []
        message_search_locations = [
            ("user_conversations", current_user, "messages"),
            ("conversations", None, None),
            ("session_messages", None, None),
            ("user_messages", None, None),
            ("conversation_messages", None, None),
            ("interview_messages", None, None),
            ("recommendation_messages", None, None)
        ]
        
        for location in message_search_locations:
            try:
                if location[1]:  # User-specific subcollection
                    messages_ref = db.collection(location[0]).document(location[1]).collection(location[2])
                else:  # Top-level collection
                    messages_ref = db.collection(location[0])
                
                # Try multiple query approaches
                query_approaches = [
                    ("session_id", session_id),
                    ("user_id", current_user)  # For broader search
                ]
                
                for field, value in query_approaches:
                    try:
                        if field == "session_id":
                            query = messages_ref.where(field, "==", value)
                        else:
                            # For user_id queries, also filter by session_id if possible
                            query = messages_ref.where(field, "==", value)
                        
                        docs = list(query.stream())
                        
                        for doc in docs:
                            message_data = doc.to_dict()
                            # Check if this message belongs to our session
                            if (message_data.get("session_id") == session_id and 
                                message_data.get("user_id") == current_user and
                                message_data.get("is_active", True)):
                                
                                # Avoid duplicates
                                if not any(msg.get("message_id") == message_data.get("message_id") for msg in messages_list):
                                    messages_list.append(message_data)
                                    
                    except Exception as e:
                        print(f"❌ Error querying {location[0]} by {field}: {e}")
                        
            except Exception as e:
                print(f"❌ Error accessing {location[0]}: {e}")
        
        print(f"🔍 Found {len(messages_list)} stored messages")
        
        # If no stored messages found, try to reconstruct based on session type
        if not messages_list:
            print(f"🔧 No stored messages found, attempting reconstruction for {session_type} session")
            
            if session_type == "recommendation":
                # Try to reconstruct from recommendation data
                try:
                    rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(session_id).get()
                    if rec_doc.exists:
                        recommendation_data = rec_doc.to_dict()
                        print(f"✅ Found recommendation data, reconstructing conversation")
                        
                        # Create user message
                        user_message = {
                            "message_id": f"{session_id}_user_query",
                            "session_id": session_id,
                            "user_id": current_user,
                            "role": "user",
                            "content": f"What would you like {recommendation_data.get('category', '').lower()} recommendations for? {recommendation_data.get('query', '')}",
                            "timestamp": recommendation_data.get("generated_at"),
                            "session_type": "recommendation",
                            "is_active": True
                        }
                        
                        # Create assistant message
                        recommendations = recommendation_data.get("recommendations", [])
                        assistant_content = f"Here are your {recommendation_data.get('category', '').lower()} recommendations:\n\n"
                        
                        for i, rec in enumerate(recommendations, 1):
                            title = rec.get("title", "<no title>")
                            description = rec.get("description", "<no description>")
                            reasons = rec.get("reasons", [])
                            
                            assistant_content += f"**{i}. {title}**\n"
                            assistant_content += f"{description}\n"
                            if reasons:
                                for reason in reasons:
                                    assistant_content += f"• {reason}\n"
                            assistant_content += "\n"
                        
                        assistant_message = {
                            "message_id": f"{session_id}_assistant_response",
                            "session_id": session_id,
                            "user_id": current_user,
                            "role": "assistant",
                            "content": assistant_content,
                            "timestamp": recommendation_data.get("generated_at"),
                            "session_type": "recommendation",
                            "is_active": True,
                            "metadata": {
                                "recommendation_id": session_id,
                                "category": recommendation_data.get("category"),
                                "processing_time_ms": recommendation_data.get("processing_time_ms")
                            }
                        }
                        
                        messages_list = [user_message, assistant_message]
                        print(f"✅ Reconstructed {len(messages_list)} recommendation messages")
                        
                except Exception as e:
                    print(f"❌ Error reconstructing recommendation messages: {e}")
                    
            elif session_type == "interview":
                # Try to reconstruct from interview session data
                try:
                    # Look for interview session data
                    interview_doc = db.collection("interview_sessions").document(session_id).get()
                    if interview_doc.exists:
                        interview_data = interview_doc.to_dict()
                        agent_state = interview_data.get("agent_state", {})
                        conversation = agent_state.get("conversation", [])
                        
                        if conversation:
                            print(f"✅ Found interview conversation data with {len(conversation)} entries")
                            
                            # Convert interview conversation to messages
                            for i, conv_entry in enumerate(conversation):
                                # User message (question)
                                user_msg = {
                                    "message_id": f"{session_id}_q_{i}",
                                    "session_id": session_id,
                                    "user_id": current_user,
                                    "role": "assistant",  # Assistant asks the question
                                    "content": conv_entry.get("question", ""),
                                    "timestamp": conv_entry.get("timestamp", session_data.get("created_at")),
                                    "session_type": "interview",
                                    "is_active": True,
                                    "metadata": {
                                        "phase": conv_entry.get("phase"),
                                        "tier": conv_entry.get("tier"),
                                        "field": conv_entry.get("field")
                                    }
                                }
                                
                                # User response (answer)
                                answer_msg = {
                                    "message_id": f"{session_id}_a_{i}",
                                    "session_id": session_id,
                                    "user_id": current_user,
                                    "role": "user",  # User provides the answer
                                    "content": conv_entry.get("answer", ""),
                                    "timestamp": conv_entry.get("timestamp", session_data.get("created_at")),
                                    "session_type": "interview",
                                    "is_active": True,
                                    "metadata": {
                                        "answer_quality": conv_entry.get("answer_metadata", {}).get("answer_quality"),
                                        "word_count": conv_entry.get("answer_metadata", {}).get("word_count")
                                    }
                                }
                                
                                messages_list.extend([user_msg, answer_msg])
                            
                            print(f"✅ Reconstructed {len(messages_list)} interview messages")
                            
                except Exception as e:
                    print(f"❌ Error reconstructing interview messages: {e}")
        
        # Sort messages by timestamp
        messages_list.sort(key=lambda x: x.get("timestamp", datetime.min))
        
        # Apply pagination
        paginated_messages = messages_list[offset:offset + limit]
        
        # Format response
        conversation_messages = []
        for message_data in paginated_messages:
            timestamp_value = message_data.get("timestamp", "")
            if hasattr(timestamp_value, 'isoformat'):
                timestamp_str = timestamp_value.isoformat()
            else:
                timestamp_str = str(timestamp_value)
            
            conversation_messages.append({
                "message_id": message_data.get("message_id", "unknown"),
                "role": message_data.get("role", "unknown"),
                "content": message_data.get("content", ""),
                "timestamp": timestamp_str,
                "session_type": message_data.get("session_type", "general"),
                "metadata": message_data.get("metadata", {})
            })
        
        print(f"✅ Returning {len(conversation_messages)} messages")
        
        return {
            "success": True,
            "session_id": session_id,
            "session_info": {
                "title": session_data.get("title"),
                "session_type": session_data.get("session_type"),
                "created_at": session_data.get("created_at"),
                "updated_at": session_data.get("updated_at"),
                "message_count": session_data.get("message_count", len(messages_list))
            },
            "messages": conversation_messages,
            "total_messages": len(messages_list),
            "returned_messages": len(conversation_messages),
            "user_id": current_user,
            "source": "stored_messages" if any("stored" in str(msg.get("message_id", "")) for msg in messages_list) else "reconstructed",
            "debug_info": {
                "expected_message_count": session_data.get("message_count", 0),
                "actual_messages_found": len(messages_list),
                "session_type": session_type,
                "reconstruction_attempted": len(messages_list) > 0 and not any("stored" in str(msg.get("message_id", "")) for msg in messages_list),
                "message_source": "stored" if any("stored" in str(msg.get("message_id", "")) for msg in messages_list) else "reconstructed"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting session messages: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session messages: {str(e)}"
        )

@router.post("/save")
async def save_message(
    request: SaveMessageRequest,
    current_user: str = Depends(get_current_user)
):
    """Save a conversation message"""
    try:
        success = save_conversation_message(
            user_id=current_user,
            session_id=request.session_id,
            role=request.role,
            content=request.content,
            session_type=request.session_type or "general",
            title=request.title
        )
        
        if success:
            return {
                "success": True,
                "message": "Conversation message saved successfully",
                "session_id": request.session_id,
                "user_id": current_user
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to save conversation message"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save message: {str(e)}"
        )

@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    current_user: str = Depends(get_current_user)
):
    """Delete a conversation session and all its messages"""
    try:
        db = get_firestore_client()
        
        # Verify session belongs to user
        session_ref = db.collection("user_conversations").document(current_user).collection("sessions").document(session_id)
        session_doc = session_ref.get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_data = session_doc.to_dict()
        if session_data.get("user_id") != current_user:
            raise HTTPException(status_code=403, detail="Access denied to this session")
        
        # Soft delete session
        session_ref.update({
            "is_active": False,
            "deleted_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        
        # Soft delete all messages in this session
        messages_ref = db.collection("user_conversations").document(current_user).collection("messages")
        messages_query = messages_ref.where("session_id", "==", session_id)
        
        deleted_messages = 0
        for message_doc in messages_query.stream():
            message_doc.reference.update({
                "is_active": False,
                "deleted_at": datetime.utcnow()
            })
            deleted_messages += 1
        
        return {
            "success": True,
            "message": f"Session {session_id} and {deleted_messages} messages deleted successfully",
            "session_id": session_id,
            "deleted_messages": deleted_messages,
            "user_id": current_user
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete session: {str(e)}"
        )

@router.get("/types")
async def get_session_types(current_user: str = Depends(get_current_user)):
    """Get available session types for the user"""
    try:
        db = get_firestore_client()
        
        # Get unique session types for this user
        sessions_ref = db.collection("user_conversations").document(current_user).collection("sessions")
        sessions_query = sessions_ref.where("is_active", "==", True)
        
        session_types = set()
        for session_doc in sessions_query.stream():
            session_data = session_doc.to_dict()
            session_type = session_data.get("session_type", "general")
            session_types.add(session_type)
        
        # Add default types
        default_types = ["general", "interview", "recommendation"]
        for default_type in default_types:
            session_types.add(default_type)
        
        return {
            "success": True,
            "session_types": sorted(list(session_types)),
            "user_id": current_user
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session types: {str(e)}"
        )

@router.post("/session/{session_id}/title")
async def update_session_title(
    session_id: str,
    title_data: dict,
    current_user: str = Depends(get_current_user)
):
    """Update the title of a conversation session"""
    try:
        db = get_firestore_client()
        
        new_title = title_data.get("title")
        if not new_title:
            raise HTTPException(status_code=400, detail="Title is required")
        
        # Verify session belongs to user
        session_ref = db.collection("user_conversations").document(current_user).collection("sessions").document(session_id)
        session_doc = session_ref.get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_data = session_doc.to_dict()
        if session_data.get("user_id") != current_user:
            raise HTTPException(status_code=403, detail="Access denied to this session")
        
        # Update title
        session_ref.update({
            "title": new_title,
            "updated_at": datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": "Session title updated successfully",
            "session_id": session_id,
            "new_title": new_title,
            "user_id": current_user
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update session title: {str(e)}"
        )

@router.get("/debug/find-messages/{session_id}")
async def debug_find_messages(
    session_id: str,
    current_user: str = Depends(get_current_user)
):
    """Debug endpoint to find where messages for a session are actually stored"""
    try:
        db = get_firestore_client()
        
        print(f"🔍 DEBUG: Searching for messages in session {session_id} for user {current_user}")
        
        # Get session info to determine session type
        session_type = "recommendation"  # We know this from the previous response
        print(f"🏷️ Session type: {session_type}")
        
        # Get all collections in the database
        collections_to_search = [
            "conversations",
            "messages", 
            "session_messages",
            "user_messages",
            "conversation_messages",
            "chat_messages",
            "user_conversations",
            "recommendation_messages",
            "recommendation_conversations", 
            "recommendation_sessions",
            f"user_{current_user}",
            "sessions"
        ]
        
        found_messages = []
        search_results = {}
        
        for collection_name in collections_to_search:
            try:
                print(f"🔍 Searching collection: {collection_name}")
                
                # Try different query patterns including session_type
                query_patterns = [
                    # Direct session_id match
                    {"field": "session_id", "value": session_id},
                    # User + session combination
                    {"field": "user_id", "value": current_user},
                    # Session type match
                    {"field": "session_type", "value": session_type},
                    # Message type match (some systems use this)
                    {"field": "message_type", "value": session_type},
                    # Category match
                    {"field": "category", "value": session_type},
                    # Type match
                    {"field": "type", "value": session_type}
                ]
                
                collection_ref = db.collection(collection_name)
                collection_messages = []
                
                for pattern in query_patterns:
                    try:
                        query = collection_ref.where(pattern["field"], "==", pattern["value"])
                        docs = list(query.stream())
                        
                        for doc in docs:
                            data = doc.to_dict()
                            # Check if this document is related to our session
                            is_related = (
                                data.get("session_id") == session_id or 
                                (data.get("user_id") == current_user and session_id in str(data)) or
                                (data.get("session_type") == session_type and data.get("user_id") == current_user) or
                                (data.get("user_id") == current_user and data.get("session_type") == session_type)
                            )
                            
                            if is_related:
                                collection_messages.append({
                                    "doc_id": doc.id,
                                    "data": data,
                                    "collection": collection_name,
                                    "matched_pattern": pattern
                                })
                                
                    except Exception as e:
                        print(f"❌ Error querying {collection_name} with {pattern}: {e}")
                
                # Also try compound queries for better matching
                try:
                    # User + session_type combination
                    compound_query = collection_ref.where("user_id", "==", current_user).where("session_type", "==", session_type)
                    compound_docs = list(compound_query.stream())
                    
                    for doc in compound_docs:
                        data = doc.to_dict()
                        # Check if this is our session or related to it
                        if (data.get("session_id") == session_id or 
                            session_id in str(data) or
                            # If no specific session_id but matches user + type and time range
                            (not collection_messages and data.get("user_id") == current_user and data.get("session_type") == session_type)):
                            
                            collection_messages.append({
                                "doc_id": doc.id,
                                "data": data,
                                "collection": collection_name,
                                "matched_pattern": {"compound": "user_id + session_type"}
                            })
                            
                except Exception as e:
                    print(f"❌ Error with compound query on {collection_name}: {e}")
                
                if collection_messages:
                    search_results[collection_name] = collection_messages
                    found_messages.extend(collection_messages)
                    print(f"✅ Found {len(collection_messages)} documents in {collection_name}")
                
            except Exception as e:
                print(f"❌ Error accessing collection {collection_name}: {e}")
                search_results[collection_name] = f"Error: {str(e)}"
        
        # Also search subcollections with session_type awareness
        print(f"🔍 Searching user-specific subcollections for session_type: {session_type}...")
        user_subcollections = []
        
        try:
            # Check user_conversations subcollections
            user_doc_ref = db.collection("user_conversations").document(current_user)
            
            # Try to list subcollections (this might not work in all Firebase setups)
            subcollection_names = ["messages", "sessions", "chats", "history", "recommendations", "recommendation_messages"]
            
            for subcol_name in subcollection_names:
                try:
                    subcol_ref = user_doc_ref.collection(subcol_name)
                    
                    # Try multiple query approaches
                    query_approaches = [
                        ("session_id", session_id),
                        ("session_type", session_type),
                    ]
                    
                    for field, value in query_approaches:
                        try:
                            docs = list(subcol_ref.where(field, "==", value).stream())
                            
                            subcol_messages = []
                            for doc in docs:
                                data = doc.to_dict()
                                if (data.get("session_id") == session_id or 
                                    (data.get("session_type") == session_type and data.get("user_id") == current_user)):
                                    subcol_messages.append({
                                        "doc_id": doc.id,
                                        "data": data,
                                        "collection": f"user_conversations/{current_user}/{subcol_name}",
                                        "query_field": field
                                    })
                            
                            if subcol_messages:
                                user_subcollections.extend(subcol_messages)
                                found_messages.extend(subcol_messages)
                                print(f"✅ Found {len(subcol_messages)} in subcollection {subcol_name} via {field}")
                                
                        except Exception as e:
                            print(f"❌ Error querying subcollection {subcol_name} by {field}: {e}")
                            
                except Exception as e:
                    print(f"❌ Error searching subcollection {subcol_name}: {e}")
                    
        except Exception as e:
            print(f"❌ Error searching user subcollections: {e}")
        
        # Search for recommendation-specific patterns
        print(f"🔍 Searching recommendation-specific patterns...")
        recommendation_search_results = []
        
        recommendation_patterns = [
            f"recommendation_{current_user}",
            f"rec_{current_user}",
            f"recommendations_{session_id}",
            f"user_recommendations"
        ]
        
        for pattern in recommendation_patterns:
            try:
                # Check if this exists as a collection
                pattern_ref = db.collection(pattern)
                sample_docs = list(pattern_ref.limit(10).stream())
                
                for doc in sample_docs:
                    data = doc.to_dict()
                    if (session_id in str(data) or 
                        (data.get("user_id") == current_user and data.get("session_type") == session_type)):
                        recommendation_search_results.append({
                            "collection": pattern,
                            "doc_id": doc.id,
                            "data": data
                        })
                        
            except Exception as e:
                print(f"❌ Error searching pattern {pattern}: {e}")
        
        return {
            "success": True,
            "session_id": session_id,
            "user_id": current_user,
            "session_type": session_type,
            "search_summary": {
                "total_messages_found": len(found_messages),
                "collections_with_data": len([k for k, v in search_results.items() if isinstance(v, list) and len(v) > 0]),
                "collections_searched": len(collections_to_search),
                "recommendation_specific_results": len(recommendation_search_results)
            },
            "detailed_results": search_results,
            "user_subcollections": user_subcollections,
            "recommendation_search_results": recommendation_search_results,
            "found_messages": found_messages[:10],  # Limit to first 10 for readability
            "search_strategies_used": [
                "Direct session_id matching",
                "User ID + session_type compound queries", 
                "Session type filtering",
                "User-specific subcollections",
                "Recommendation-specific collection patterns",
                "Broad text search for session ID"
            ],
            "recommendations": [
                "Check detailed_results for exact collection locations",
                "Look at recommendation_search_results for recommendation-specific storage",
                "Check user_subcollections for user-specific data",
                "Update save_conversation_message to use the identified storage pattern"
            ]
        }
        
    except Exception as e:
        print(f"❌ Error in debug search: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to debug find messages: {str(e)}"
        )

@router.get("/debug/collections")
async def debug_list_collections(current_user: str = Depends(get_current_user)):
    """Debug endpoint to see what collections exist and their structure"""
    try:
        db = get_firestore_client()
        
        # Try to access some common collections and see their structure
        collections_info = {}
        
        common_collections = [
            "conversations", "messages", "sessions", "users", "user_conversations",
            "interview_sessions", "recommendation_sessions", "chat_sessions"
        ]
        
        for collection_name in common_collections:
            try:
                collection_ref = db.collection(collection_name)
                
                # Get a few sample documents
                sample_docs = list(collection_ref.limit(3).stream())
                
                collection_info = {
                    "exists": len(sample_docs) > 0,
                    "sample_count": len(sample_docs),
                    "sample_structures": []
                }
                
                for doc in sample_docs:
                    data = doc.to_dict()
                    # Get the structure (field names and types)
                    structure = {}
                    for key, value in data.items():
                        structure[key] = type(value).__name__
                    
                    collection_info["sample_structures"].append({
                        "doc_id": doc.id,
                        "field_structure": structure,
                        "user_id": data.get("user_id", "N/A"),
                        "session_id": data.get("session_id", "N/A")
                    })
                
                collections_info[collection_name] = collection_info
                
            except Exception as e:
                collections_info[collection_name] = {"error": str(e)}
        
        return {
            "success": True,
            "user_id": current_user,
            "collections_info": collections_info,
            "note": "This shows the structure of existing collections to help debug message storage"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list collections: {str(e)}"
        )