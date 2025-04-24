from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user
from app.models.interview import InterviewSession, InterviewResponse, UserAnswer
from app.services.interview_agent import InterviewAgent
from app.services.profile_generator import ProfileGenerator
from app.core.firebase import get_firestore_client
from typing import Dict, Any, List
import uuid
from datetime import datetime
import json

router = APIRouter()
interview_agent = InterviewAgent()
profile_generator = ProfileGenerator()

@router.post("/start", response_model=InterviewResponse)
async def start_interview(current_user: Any = Depends(get_current_user)):
    """Start a new interview session"""
    try:
        # Create new session
        session = interview_agent.create_session(current_user.uid)
        
        # Get the first question
        question_data = interview_agent.get_current_question(0, 0)
        
        # Save session to Firestore
        db = get_firestore_client()
        session_id = str(uuid.uuid4())
        
        db.collection("interview_sessions").document(session_id).set({
            "user_id": current_user.uid,
            "current_phase": 0,
            "current_question": 0,
            "follow_up_count": 0,
            "conversation": [],
            "started_at": datetime.utcnow(),
            "completed_at": None
        })
        
        return InterviewResponse(
            session_id=session_id,
            question=question_data["question"],
            is_complete=False
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start interview: {str(e)}"
        )

@router.post("/{session_id}/answer", response_model=InterviewResponse)
async def answer_question(
    session_id: str, 
    answer_data: UserAnswer, 
    current_user: Any = Depends(get_current_user)
):
    """Process user's answer and return next question or follow-up"""
    try:
        # Get session from Firestore
        db = get_firestore_client()
        session_doc = db.collection("interview_sessions").document(session_id).get()
        
        if not session_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview session not found"
            )
        
        session = session_doc.to_dict()
        
        # Verify user owns this session
        if session["user_id"] != current_user.uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this session"
            )
        
        # Get current question
        current_phase = session["current_phase"]
        current_question = session["current_question"]
        follow_up_count = session["follow_up_count"]
        
        question_data = interview_agent.get_current_question(current_phase, current_question)
        current_question_text = question_data["question"]
        
        # Store the answer
        conversation = session.get("conversation", [])
        conversation.append({
            "question": current_question_text,
            "answer": answer_data.answer,
            "phase": question_data["phase"],
            "timestamp": datetime.utcnow()
        })
        
        # Check if we need follow-up
        needs_followup = interview_agent.evaluate_answer_quality(answer_data.answer)
        
        if needs_followup and follow_up_count < 2:
            # Generate follow-up
            follow_up = interview_agent.generate_follow_up(current_question_text, answer_data.answer)
            
            # Update session
            db.collection("interview_sessions").document(session_id).update({
                "follow_up_count": follow_up_count + 1,
                "conversation": conversation
            })
            
            return InterviewResponse(
                session_id=session_id,
                question=current_question_text,
                follow_up=follow_up,
                is_complete=False
            )
        else:
            # Move to next question
            next_question = current_question + 1
            next_phase = current_phase
            
            # Check if we need to move to next phase
            phases = interview_agent.phases
            if next_question >= len(phases[current_phase]["questions"]):
                next_question = 0
                next_phase = current_phase + 1
            
            # Check if interview is complete
            is_complete = next_phase >= len(phases)
            
            # Get next question
            next_question_data = interview_agent.get_current_question(next_phase, next_question)
            
            # Update session
            update_data = {
                "current_phase": next_phase,
                "current_question": next_question,
                "follow_up_count": 0,
                "conversation": conversation
            }
            
            if is_complete:
                update_data["completed_at"] = datetime.utcnow()
                
                # Generate profile if interview is complete
                user_profile = profile_generator.generate_full_profile(conversation)
                
                # Save profile to Firestore
                db.collection("profiles").document(current_user.uid).set(user_profile)
            
            db.collection("interview_sessions").document(session_id).update(update_data)
            
            return InterviewResponse(
                session_id=session_id,
                question=next_question_data["question"] if not is_complete else "",
                is_complete=is_complete
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process answer: {str(e)}"
        )

@router.get("/sessions")
async def get_user_sessions(current_user: Any = Depends(get_current_user)):
    """Get all interview sessions for current user"""
    try:
        db = get_firestore_client()
        sessions = db.collection("interview_sessions").where("user_id", "==", current_user.uid).stream()
        
        result = []
        for session in sessions:
            session_data = session.to_dict()
            result.append({
                "session_id": session.id,
                "started_at": session_data.get("started_at"),
                "completed_at": session_data.get("completed_at"),
                "progress": {
                    "phase": session_data.get("current_phase"),
                    "question": session_data.get("current_question"),
                    "total_phases": len(interview_agent.phases),
                    "is_complete": session_data.get("completed_at") is not None
                }
            })
        
        return {"sessions": result}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve sessions: {str(e)}"
        )

@router.get("/{session_id}")
async def get_session_details(session_id: str, current_user: Any = Depends(get_current_user)):
    """Get details of a specific interview session"""
    try:
        db = get_firestore_client()
        session_doc = db.collection("interview_sessions").document(session_id).get()
        
        if not session_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview session not found"
            )
        
        session = session_doc.to_dict()
        
        # Verify user owns this session
        if session["user_id"] != current_user.uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this session"
            )
        
        return {
            "session_id": session_id,
            "started_at": session.get("started_at"),
            "completed_at": session.get("completed_at"),
            "current_phase": session.get("current_phase"),
            "current_question": session.get("current_question"),
            "conversation": session.get("conversation"),
            "is_complete": session.get("completed_at") is not None
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve session details: {str(e)}"
        )

@router.delete("/{session_id}")
async def delete_session(session_id: str, current_user: Any = Depends(get_current_user)):
    """Delete an interview session"""
    try:
        db = get_firestore_client()
        session_doc = db.collection("interview_sessions").document(session_id).get()
        
        if not session_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview session not found"
            )
        
        session = session_doc.to_dict()
        
        # Verify user owns this session
        if session["user_id"] != current_user.uid:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this session"
            )
        
        # Delete the session
        db.collection("interview_sessions").document(session_id).delete()
        
        return {"message": "Session deleted successfully"}
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )                 