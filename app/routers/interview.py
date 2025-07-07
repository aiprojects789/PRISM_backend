# from fastapi import APIRouter, Depends, HTTPException, status
# from app.core.security import get_current_user
# from app.models.interview import InterviewSession, InterviewResponse, UserAnswer
# from app.services.interview_agent import InterviewAgent
# from app.services.profile_generator import ProfileGenerator
# from app.core.firebase import get_firestore_client
# from typing import Dict, Any, List
# import uuid
# from datetime import datetime
# from app.utils.utils import clean_session_data
# from typing import Union
# from fastapi.responses import JSONResponse

# router = APIRouter()
# interview_agent = InterviewAgent()
# profile_generator = ProfileGenerator()


# @router.post("/start", response_model=Union[InterviewResponse, dict])
# async def start_interview(current_user: str = Depends(get_current_user)):
#     """
#     Starts a new interview session with dynamic questions from Firestore.
    
#     Args:
#         current_user (str): The currently authenticated user ID.
        
#     Returns:
#         InterviewResponse: Contains the session ID, first question, and status.
#     """
#     try:
#         # Get pending questions from tier1
#         pending_questions = interview_agent.get_pending_questions_by_field("tier1")
        
#         if not pending_questions:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="No pending questions available for interview"
#             )
        
#         # Create session with dynamic questions
#         session_data = interview_agent.create_session(current_user, pending_questions)
        
#         # Get first question
#         first_question_data = interview_agent.get_current_question(session_data)
        
#         if not first_question_data:
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail="Failed to get first question"
#             )
        
#         # Save session to Firestore
#         db = get_firestore_client()
#         session_id = session_data["session_id"]
        
#         db.collection("interview_sessions").document(session_id).set({
#             "user_id": current_user,
#             "current_phase": session_data["current_phase"],
#             "current_question": session_data["current_question"],
#             "follow_up_depth": session_data["follow_up_depth"],
#             "conversation": session_data["conversation"],
#             "phases": session_data["phases"],
#             "started_at": datetime.utcnow(),
#             "completed_at": None,
#         })
        
#         total_questions = len(pending_questions)
        
#         return InterviewResponse(
#             session_id=session_id,
#             question=first_question_data["question"],
#             is_complete=False,
#             progress={"answered": 0, "total": total_questions},
#         )
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to start interview: {str(e)}",
#         )


# @router.post("/{session_id}/answer", response_model=InterviewResponse)
# async def answer_question(
#     session_id: str,
#     answer_data: UserAnswer,
#     current_user: str = Depends(get_current_user),
# ):
#     """
#     Process user's answer and return next question or follow-up.
    
#     Args:
#         session_id (str): The interview session ID.
#         answer_data (UserAnswer): The user's response.
#         current_user (str): The authenticated user ID.
        
#     Returns:
#         InterviewResponse: Next question or completion status.
#     """
#     try:
#         # Get session from Firestore
#         db = get_firestore_client()
#         session_doc = db.collection("interview_sessions").document(session_id).get()
        
#         if not session_doc.exists:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Interview session not found"
#             )
        
#         session_data = clean_session_data(session_doc.to_dict())
        
#         # Verify user owns session
#         if session_data["user_id"] != current_user:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail="Not authorized to access this session"
#             )
        
#         # Get current question data
#         current_question_data = interview_agent.get_current_question(session_data)
        
#         if not current_question_data:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail="No current question available"
#             )
        
#         # Check if we need follow-up
#         needs_followup = interview_agent.evaluate_answer_quality(answer_data.answer)
#         current_depth = session_data.get("follow_up_depth", 0)
        
#         if needs_followup and current_depth < 2:
#             # Generate follow-up question
#             follow_up = interview_agent.generate_follow_up(
#                 current_question_data["question"], 
#                 answer_data.answer
#             )
            
#             # Add answer to conversation
#             session_data["conversation"].append({
#                 "question": current_question_data["question"],
#                 "answer": answer_data.answer,
#                 "field": current_question_data["field"],
#                 "phase": current_question_data["phase"],
#                 "timestamp": datetime.utcnow().isoformat(),
#             })
            
#             # Update follow-up depth
#             session_data["follow_up_depth"] = current_depth + 1
            
#             # Save updated session
#             db.collection("interview_sessions").document(session_id).update({
#                 "follow_up_depth": session_data["follow_up_depth"],
#                 "conversation": session_data["conversation"],
#             })
            
#             return InterviewResponse(
#                 session_id=session_id,
#                 question=current_question_data["question"],
#                 follow_up=follow_up,
#                 is_complete=False,
#                 progress={
#                     "answered": len([q for q in session_data["conversation"] if q.get("field")]),
#                     "total": len(session_data["phases"][0]["questions"]),
#                 },
#             )
        
#         # Submit answer and advance to next question
#         result = interview_agent.submit_answer(session_data, answer_data.answer)
        
#         if not result["success"]:
#             raise HTTPException(
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                 detail=result.get("message", "Failed to submit answer")
#             )
        
#         updated_session = result["session_data"]
#         is_complete = result["is_complete"]
        
#         # Get next question if not complete
#         next_question = ""
#         if not is_complete:
#             next_question_data = interview_agent.get_current_question(updated_session)
#             if next_question_data:
#                 next_question = next_question_data["question"]
        
#         # Update session in Firestore
#         update_data = {
#             "current_phase": updated_session["current_phase"],
#             "current_question": updated_session["current_question"],
#             "follow_up_depth": 0,  # Reset follow-up depth
#             "conversation": updated_session["conversation"],
#         }
        
#         if is_complete:
#             update_data["completed_at"] = datetime.utcnow().isoformat()
            
#             # Generate profile if interview is complete
#             user_profile = profile_generator.generate_full_profile(updated_session["conversation"])
            
#             # Save profile to Firestore
#             db.collection("profiles").document(current_user).set(user_profile)
        
#         db.collection("interview_sessions").document(session_id).update(update_data)
        
#         return InterviewResponse(
#             session_id=session_id,
#             question=next_question,
#             is_complete=is_complete,
#             progress={
#                 "answered": len([q for q in updated_session["conversation"] if q.get("field")]),
#                 "total": len(updated_session["phases"][0]["questions"]),
#             },
#         )
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to process answer: {str(e)}",
#         )


# @router.get("/sessions")
# async def get_user_sessions(current_user: str = Depends(get_current_user)):
#     """
#     Get all interview sessions for the authenticated user.
    
#     Returns:
#         A list of session summaries including progress and timestamps.
#     """
#     try:
#         db = get_firestore_client()
#         sessions = (
#             db.collection("interview_sessions")
#             .where("user_id", "==", current_user)
#             .stream()
#         )
        
#         result = []
#         for session in sessions:
#             session_data = session.to_dict()
            
#             # Calculate progress
#             total_questions = 0
#             answered_questions = len([q for q in session_data.get("conversation", []) if q.get("field")])
            
#             if session_data.get("phases"):
#                 total_questions = len(session_data["phases"][0].get("questions", []))
            
#             result.append({
#                 "session_id": session.id,
#                 "started_at": session_data.get("started_at"),
#                 "completed_at": session_data.get("completed_at"),
#                 "progress": {
#                     "phase": session_data.get("current_phase", 0),
#                     "question": session_data.get("current_question", 0),
#                     "answered": answered_questions,
#                     "total": total_questions,
#                     "is_complete": session_data.get("completed_at") is not None,
#                 },
#             })
        
#         return {"sessions": result}
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to retrieve sessions: {str(e)}",
#         )


# @router.get("/{session_id}")
# async def get_session_details(
#     session_id: str, current_user: str = Depends(get_current_user)
# ):
#     """
#     Retrieve detailed information about a specific interview session.
    
#     Args:
#         session_id (str): The session ID.
#         current_user (str): The authenticated user ID.
        
#     Returns:
#         JSON: Session metadata and conversation history.
#     """
#     try:
#         db = get_firestore_client()
#         session_doc = db.collection("interview_sessions").document(session_id).get()
        
#         if not session_doc.exists:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Interview session not found",
#             )
        
#         session = session_doc.to_dict()
        
#         # Verify user owns this session
#         if session["user_id"] != current_user:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail="Not authorized to access this session",
#             )
        
#         return {
#             "session_id": session_id,
#             "started_at": session.get("started_at"),
#             "completed_at": session.get("completed_at"),
#             "current_phase": session.get("current_phase"),
#             "current_question": session.get("current_question"),
#             "conversation": session.get("conversation", []),
#             "phases": session.get("phases", []),
#             "is_complete": session.get("completed_at") is not None,
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to retrieve session details: {str(e)}",
#         )


# @router.delete("/{session_id}")
# async def delete_session(
#     session_id: str, current_user: str = Depends(get_current_user)
# ):
#     """
#     Delete a specific interview session.
    
#     Args:
#         session_id (str): The session ID.
#         current_user (str): The authenticated user ID.
        
#     Returns:
#         JSON: Success message.
#     """
#     try:
#         db = get_firestore_client()
#         session_doc = db.collection("interview_sessions").document(session_id).get()
        
#         if not session_doc.exists:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="Interview session not found",
#             )
        
#         session = session_doc.to_dict()
        
#         # Verify user owns this session
#         if session["user_id"] != current_user:
#             raise HTTPException(
#                 status_code=status.HTTP_403_FORBIDDEN,
#                 detail="Not authorized to delete this session",
#             )
        
#         # Delete the session
#         db.collection("interview_sessions").document(session_id).delete()
        
#         return {"message": "Session deleted successfully"}
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to delete session: {str(e)}",
#         )


# @router.get("/questions/pending")
# async def get_pending_questions(
#     current_user: str = Depends(get_current_user),
#     tier: str = "tier1"
# ):
#     """
#     Get all pending questions for a specific tier.
    
#     Args:
#         current_user (str): The authenticated user ID.
#         tier (str): The tier name (default: "tier1").
        
#     Returns:
#         JSON: List of pending questions.
#     """
#     try:
#         pending_questions = interview_agent.get_pending_questions_by_field(tier)
        
#         return {
#             "tier": tier,
#             "pending_questions": pending_questions,
#             "count": len(pending_questions)
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to retrieve pending questions: {str(e)}",
#         )



from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user
from app.models.interview import InterviewSession, InterviewResponse, UserAnswer
from app.services.interview_agent import InterviewAgent
from app.services.profile_generator import ProfileGenerator
from app.core.firebase import get_firestore_client
from typing import Dict, Any, List
import uuid
from datetime import datetime
from app.utils.utils import clean_session_data
from typing import Union
from fastapi.responses import JSONResponse

router = APIRouter()
interview_agent = InterviewAgent()
profile_generator = ProfileGenerator()


@router.post("/start", response_model=Union[InterviewResponse, dict])
async def start_interview(current_user: str = Depends(get_current_user)):
    """
    Starts a new interview session with dynamic questions from Firestore.
    
    Args:
        current_user (str): The currently authenticated user ID.
        
    Returns:
        InterviewResponse: Contains the session ID, first question, and detailed metadata.
    """
    try:
        # Get pending questions from tier1
        pending_questions = interview_agent.get_pending_questions_by_field("tier1")
        
        if not pending_questions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No pending questions available for interview"
            )
        
        # Create session with dynamic questions
        session_data = interview_agent.create_session(current_user, pending_questions)
        
        # Get first question
        first_question_data = interview_agent.get_current_question(session_data)
        
        if not first_question_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get first question"
            )
        
        # Save session to Firestore
        db = get_firestore_client()
        session_id = session_data["session_id"]
        
        db.collection("interview_sessions").document(session_id).set({
            "user_id": current_user,
            "current_phase": session_data["current_phase"],
            "current_question": session_data["current_question"],
            "follow_up_depth": session_data["follow_up_depth"],
            "conversation": session_data["conversation"],
            "phases": session_data["phases"],
            "started_at": datetime.utcnow(),
            "completed_at": None,
        })
        
        total_questions = len(pending_questions)
        
        # Enhanced response with detailed information
        return {
            "session_id": session_id,
            "question": first_question_data["question"],
            "question_details": {
                "field": first_question_data.get("field"),
                "tier": first_question_data.get("tier_name", "tier1"),
                "phase": first_question_data.get("phase"),
                "question_number": session_data["current_question"] + 1,
                "total_questions": total_questions
            },
            "tier_info": {
                "current_tier": "tier1",
                "tier_status": "in_progress",
                "total_tiers": len(interview_agent.tier_questions),
                "available_tiers": list(interview_agent.tier_questions.keys())
            },
            "session_metadata": {
                "user_id": current_user,
                "started_at": datetime.utcnow().isoformat(),
                "current_phase": session_data["current_phase"],
                "follow_up_depth": session_data["follow_up_depth"],
                "phases_info": [
                    {
                        "name": phase["name"],
                        "total_questions": len(phase["questions"]),
                        "tier_name": phase.get("tier_name", "unknown")
                    }
                    for phase in session_data["phases"]
                ]
            },
            "is_complete": False,
            "progress": {
                "answered": 0,
                "total": total_questions,
                "percentage": 0,
                "phase_progress": f"1/{len(session_data['phases'])}"
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start interview: {str(e)}",
        )


# Add debugging to the answer_question endpoint
@router.post("/{session_id}/answer", response_model=dict)
async def answer_question(
    session_id: str,
    answer_data: UserAnswer,
    current_user: str = Depends(get_current_user),
):
    try:
        # Get session from Firestore
        db = get_firestore_client()
        session_doc = db.collection("interview_sessions").document(session_id).get()
        
        if not session_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview session not found"
            )
        
        session_data = clean_session_data(session_doc.to_dict())
        
        # DEBUG: Log session state
        print(f"DEBUG - Session state:")
        print(f"  Current phase: {session_data.get('current_phase', 'None')}")
        print(f"  Current question: {session_data.get('current_question', 'None')}")
        print(f"  Phases count: {len(session_data.get('phases', []))}")
        print(f"  Follow up depth: {session_data.get('follow_up_depth', 0)}")
        
        if session_data.get('phases'):
            current_phase = session_data.get('current_phase', 0)
            if current_phase < len(session_data['phases']):
                phase = session_data['phases'][current_phase]
                print(f"  Questions in current phase: {len(phase.get('questions', []))}")
                print(f"  Current question index: {session_data.get('current_question', 0)}")
        
        # Verify user owns session
        if session_data["user_id"] != current_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this session"
            )
        
        # Get current question data with better error handling
        current_question_data = interview_agent.get_current_question(session_data)
        
        if not current_question_data:
            # DEBUG: More detailed error information
            print(f"DEBUG - Failed to get current question:")
            print(f"  Session phases: {session_data.get('phases', [])}")
            print(f"  Current phase index: {session_data.get('current_phase', 0)}")
            print(f"  Current question index: {session_data.get('current_question', 0)}")
            
            # Check if we're at the end of questions
            current_phase = session_data.get('current_phase', 0)
            current_question = session_data.get('current_question', 0)
            
            if current_phase >= len(session_data.get('phases', [])):
                # Interview is complete
                return {
                    "session_id": session_id,
                    "question": "",
                    "is_complete": True,
                    "message": "Interview completed successfully"
                }
            
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No current question available. Phase: {current_phase}, Question: {current_question}"
            )
        
        # Rest of your existing code...
        
    except Exception as e:
        print(f"DEBUG - Exception in answer_question: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process answer: {str(e)}",
        )
@router.get("/sessions")
async def get_user_sessions(current_user: str = Depends(get_current_user)):
    """
    Get all interview sessions for the authenticated user with detailed information.
    
    Returns:
        A list of session summaries including detailed progress, tier info, and timestamps.
    """
    try:
        db = get_firestore_client()
        sessions = (
            db.collection("interview_sessions")
            .where("user_id", "==", current_user)
            .order_by("started_at", direction="DESCENDING")
            .stream()
        )
        
        result = []
        for session in sessions:
            session_data = session.to_dict()
            
            # Calculate progress
            total_questions = 0
            answered_questions = len([q for q in session_data.get("conversation", []) if q.get("field")])
            
            if session_data.get("phases"):
                total_questions = len(session_data["phases"][0].get("questions", []))
            
            # Get tier information from conversation
            conversation = session_data.get("conversation", [])
            tiers_used = list(set([q.get("tier", "tier1") for q in conversation if q.get("tier")]))
            
            session_info = {
                "session_id": session.id,
                "started_at": session_data.get("started_at"),
                "completed_at": session_data.get("completed_at"),
                "session_metadata": {
                    "user_id": current_user,
                    "current_phase": session_data.get("current_phase", 0),
                    "follow_up_depth": session_data.get("follow_up_depth", 0),
                    "conversation_length": len(conversation),
                    "phases_info": [
                        {
                            "name": phase.get("name", "Unknown"),
                            "total_questions": len(phase.get("questions", [])),
                            "tier_name": phase.get("tier_name", "unknown")
                        }
                        for phase in session_data.get("phases", [])
                    ]
                },
                "tier_info": {
                    "tiers_used": tiers_used,
                    "primary_tier": tiers_used[0] if tiers_used else "tier1",
                    "tier_status": "completed" if session_data.get("completed_at") else "in_progress"
                },
                "progress": {
                    "phase": session_data.get("current_phase", 0),
                    "question": session_data.get("current_question", 0),
                    "answered": answered_questions,
                    "total": total_questions,
                    "percentage": round((answered_questions / total_questions) * 100, 2) if total_questions > 0 else 0,
                    "phase_progress": f"{session_data.get('current_phase', 0) + 1}/{len(session_data.get('phases', []))}",
                    "is_complete": session_data.get("completed_at") is not None,
                },
                "statistics": {
                    "total_answers": len(conversation),
                    "follow_up_questions": len([q for q in conversation if q.get("follow_up_depth", 0) > 0]),
                    "fields_covered": list(set([q.get("field") for q in conversation if q.get("field")])),
                    "average_answer_length": sum(len(q.get("answer", "").split()) for q in conversation) / len(conversation) if conversation else 0
                }
            }
            
            result.append(session_info)
        
        return {
            "sessions": result,
            "summary": {
                "total_sessions": len(result),
                "completed_sessions": len([s for s in result if s["progress"]["is_complete"]]),
                "in_progress_sessions": len([s for s in result if not s["progress"]["is_complete"]]),
                "total_questions_answered": sum(s["progress"]["answered"] for s in result)
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve sessions: {str(e)}",
        )


@router.get("/{session_id}")
async def get_session_details(
    session_id: str, current_user: str = Depends(get_current_user)
):
    """
    Retrieve comprehensive information about a specific interview session.
    
    Args:
        session_id (str): The session ID.
        current_user (str): The authenticated user ID.
        
    Returns:
        JSON: Complete session metadata, conversation history, and analytics.
    """
    try:
        db = get_firestore_client()
        session_doc = db.collection("interview_sessions").document(session_id).get()
        
        if not session_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview session not found",
            )
        
        session = session_doc.to_dict()
        
        # Verify user owns this session
        if session["user_id"] != current_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this session",
            )
        
        conversation = session.get("conversation", [])
        phases = session.get("phases", [])
        
        # Calculate detailed analytics
        tiers_used = list(set([q.get("tier", "tier1") for q in conversation if q.get("tier")]))
        fields_covered = list(set([q.get("field") for q in conversation if q.get("field")]))
        
        return {
            "session_id": session_id,
            "session_metadata": {
                "user_id": session["user_id"],
                "started_at": session.get("started_at"),
                "completed_at": session.get("completed_at"),
                "current_phase": session.get("current_phase"),
                "current_question": session.get("current_question"),
                "follow_up_depth": session.get("follow_up_depth", 0),
                "is_complete": session.get("completed_at") is not None,
            },
            "tier_info": {
                "tiers_used": tiers_used,
                "primary_tier": tiers_used[0] if tiers_used else "tier1",
                "tier_status": "completed" if session.get("completed_at") else "in_progress",
                "available_tiers": list(interview_agent.tier_questions.keys())
            },
            "phases_info": [
                {
                    "name": phase.get("name", "Unknown"),
                    "total_questions": len(phase.get("questions", [])),
                    "tier_name": phase.get("tier_name", "unknown"),
                    "instructions": phase.get("instructions", "")
                }
                for phase in phases
            ],
            "conversation": conversation,
            "progress": {
                "answered": len([q for q in conversation if q.get("field")]),
                "total": len(phases[0].get("questions", [])) if phases else 0,
                "percentage": round((len([q for q in conversation if q.get("field")]) / len(phases[0].get("questions", []))) * 100, 2) if phases and phases[0].get("questions") else 0,
                "phase_progress": f"{session.get('current_phase', 0) + 1}/{len(phases)}"
            },
            "analytics": {
                "total_answers": len(conversation),
                "follow_up_questions": len([q for q in conversation if q.get("follow_up_depth", 0) > 0]),
                "fields_covered": fields_covered,
                "phases_covered": list(set([q.get("phase") for q in conversation if q.get("phase")])),
                "average_answer_length": sum(len(q.get("answer", "").split()) for q in conversation) / len(conversation) if conversation else 0,
                "session_duration": self._calculate_session_duration(session.get("started_at"), session.get("completed_at")),
                "answer_distribution": self._get_answer_distribution(conversation)
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve session details: {str(e)}",
        )

# Add this endpoint to debug your session
@router.get("/{session_id}/debug")
async def debug_session(
    session_id: str, 
    current_user: str = Depends(get_current_user)
):
    """Debug endpoint to check session state"""
    try:
        db = get_firestore_client()
        session_doc = db.collection("interview_sessions").document(session_id).get()
        
        if not session_doc.exists:
            return {"error": "Session not found"}
        
        session_data = session_doc.to_dict()
        
        # Return complete session data for debugging
        return {
            "session_id": session_id,
            "raw_session_data": session_data,
            "analysis": {
                "current_phase": session_data.get('current_phase'),
                "current_question": session_data.get('current_question'),
                "phases_count": len(session_data.get('phases', [])),
                "conversation_length": len(session_data.get('conversation', [])),
                "follow_up_depth": session_data.get('follow_up_depth', 0),
                "has_phases": bool(session_data.get('phases')),
                "phase_0_questions": len(session_data.get('phases', [{}])[0].get('questions', [])) if session_data.get('phases') else 0,
                "is_complete": session_data.get('completed_at') is not None
            }
        }
        
    except Exception as e:
        return {"error": f"Debug failed: {str(e)}"}
    
@router.get("/questions/pending")
async def get_pending_questions(
    current_user: str = Depends(get_current_user),
    tier: str = "tier1"
):
    """
    Get all pending questions for a specific tier with comprehensive details.
    
    Args:
        current_user (str): The authenticated user ID.
        tier (str): The tier name (default: "tier1").
        
    Returns:
        JSON: Detailed list of pending questions with tier information.
    """
    try:
        pending_questions = interview_agent.get_pending_questions_by_field(tier)
        
        # Get tier information
        tier_data = interview_agent.tier_questions.get(tier, {})
        all_questions = tier_data.get("questions", [])
        
        # Calculate statistics
        total_questions = len(all_questions)
        answered_questions = len([q for q in all_questions if q.get("qest") == "answered"])
        pending_count = len(pending_questions)
        
        return {
            "tier": tier,
            "tier_info": {
                "status": tier_data.get("status", "unknown"),
                "description": tier_data.get("description", ""),
                "priority": tier_data.get("priority", 1),
                "category": tier_data.get("category", "general")
            },
            "statistics": {
                "total_questions": total_questions,
                "answered_questions": answered_questions,
                "pending_questions": pending_count,
                "completion_percentage": round((answered_questions / total_questions) * 100, 2) if total_questions > 0 else 0
            },
            "pending_questions": [
                {
                    "question": q.get("question"),
                    "field": q.get("field"),
                    "type": q.get("type", "text"),
                    "category": q.get("category", "general"),
                    "priority": q.get("priority", 1),
                    "expected_answer_type": q.get("expected_answer_type", "text"),
                    "hints": q.get("hints", []),
                    "validation_rules": q.get("validation_rules", {}),
                    "question_id": q.get("id", ""),
                    "status": q.get("qest", "pending")
                }
                for q in pending_questions
            ],
            "available_tiers": list(interview_agent.tier_questions.keys()),
            "total_tiers": len(interview_agent.tier_questions)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve pending questions: {str(e)}",
        )


# Helper methods for analytics
def _calculate_session_duration(started_at, completed_at):
    """Calculate session duration in minutes"""
    if not started_at or not completed_at:
        return None
    
    try:
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        if isinstance(completed_at, str):
            completed_at = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
        
        duration = completed_at - started_at
        return round(duration.total_seconds() / 60, 2)
    except Exception:
        return None


def _get_answer_distribution(conversation):
    """Get distribution of answers by field/category"""
    distribution = {}
    for item in conversation:
        field = item.get("field", "unknown")
        if field in distribution:
            distribution[field] += 1
        else:
            distribution[field] = 1
    return distribution

