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
    Starts a new interview session for the authenticated user.

    Args:
        current_user (UserResponse): The currently authenticated user, extracted from the JWT token.

    Returns:
        InterviewResponse: Contains the session ID, first question, and status flag.

    Raises:
        HTTPException: If interview session creation or Firestore write fails.
    """
    try:
        # Create new session
        session = interview_agent.create_session(current_user)

        # Get the first question
        question_data = interview_agent.get_current_question(0, 0)

        # Save session to Firestore
        db = get_firestore_client()
        session_id = str(uuid.uuid4())

        db.collection("interview_sessions").document(session_id).set(
            {
                "user_id": current_user,
                "current_phase": 0,
                "current_question": 0,
                "follow_up_count": 0,
                "conversation": [],
                "started_at": datetime.utcnow(),
                "completed_at": None,
            }
        )

        total_questions = sum(
            len(phase["questions"]) for phase in interview_agent.phases
        )

        return InterviewResponse(
            session_id=session_id,
            question=question_data["question"],
            is_complete=False,
            progress={"answered": 0, "total": total_questions},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start interview: {str(e)}",
        )


@router.post(
    "/foundation/start", response_model=InterviewResponse
)  # Keep if most responses follow this shape
async def start_foundation(current_user: str = Depends(get_current_user)):
    try:
        db = get_firestore_client()
        existing_sessions = (
            db.collection("interview_sessions")
            .where("user_id", "==", current_user)
            .stream()
        )

        session_doc = None
        for doc in existing_sessions:
            session_data = doc.to_dict()
            if session_data["current_phase"] == 0 and session_data[
                "current_question"
            ] < len(interview_agent.phases[0]["questions"]):
                session_doc = doc
                session_id = doc.id
                current_question = session_data["current_question"]
                break
            elif session_data["current_phase"] > 0:
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content={
                        "message": "Foundational phase already completed. Proceed to /main/start.",
                        "session_id": doc.id,
                        "is_complete": True,
                    },
                )

        if not session_doc:
            session_id = str(uuid.uuid4())
            db.collection("interview_sessions").document(session_id).set(
                {
                    "user_id": current_user,
                    "current_phase": 0,
                    "current_question": 0,
                    "follow_up_count": 0,
                    "conversation": [],
                    "started_at": datetime.utcnow(),
                    "completed_at": None,
                    "answered_questions_count": 0,
                }
            )
            current_question = 0

        first_question = interview_agent.get_current_question(0, current_question)

        return InterviewResponse(
            session_id=session_id,
            question=first_question["question"],
            is_complete=False,
            progress={
                "answered": current_question,
                "total": len(interview_agent.phases[0]["questions"]),
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start foundational interview: {str(e)}",
        )


@router.post("/foundation/{session_id}/answer", response_model=InterviewResponse)
async def answer_foundation_question(
    session_id: str,
    answer_data: UserAnswer,
    current_user: str = Depends(get_current_user),
):
    """
    Handles only the Foundational phase (phase 0) of the interview process.
    It processes user answers, adds follow-up logic, and advances through the foundational questions.
    """
    try:
        # Step 1: Fetch session
        db = get_firestore_client()
        doc_ref = db.collection("interview_sessions").document(session_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail="Interview session not found")

        session = clean_session_data(doc.to_dict())

        if session["user_id"] != current_user:
            raise HTTPException(status_code=403, detail="Unauthorized")

        current_phase = session["current_phase"]
        current_question = session["current_question"]
        follow_up_count = session.get("follow_up_count", 0)
        answered_questions_count = session.get("answered_questions_count", 0)

        # Only allow foundational phase
        if current_phase != 0:
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Foundational phase already completed.",
                    "is_complete": True,
                },
            )

        # Step 2: Get current foundational question
        question_text = interview_agent.phases[0]["questions"][current_question]

        # Step 3: Save current answer
        session["conversation"].append(
            {
                "question": question_text,
                "answer": answer_data.answer,
                "phase": 0,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # Step 4: Check for follow-up
        needs_followup = interview_agent.evaluate_answer_quality(answer_data.answer)

        if needs_followup and follow_up_count < 2:
            follow_up = interview_agent.generate_follow_up(
                question_text, answer_data.answer
            )

            doc_ref.update(
                {
                    "follow_up_count": follow_up_count + 1,
                    "conversation": session["conversation"],
                }
            )

            return InterviewResponse(
                session_id=session_id,
                question=question_text,
                follow_up=follow_up,
                is_complete=False,
                progress={
                    "answered": answered_questions_count,
                    "total": len(interview_agent.phases[0]["questions"]),
                },
            )

        # Step 5: Move to next foundational question
        next_question = current_question + 1
        is_complete = next_question >= len(interview_agent.phases[0]["questions"])

        update_data = {
            "current_question": next_question,
            "follow_up_count": 0,
            "conversation": session["conversation"],
            "answered_questions_count": answered_questions_count + 1,
        }

        if is_complete:
            update_data["current_phase"] = 1
            update_data["completed_at"] = datetime.utcnow().isoformat()

        doc_ref.update(update_data)

        # Step 6: Return next question or finish
        if not is_complete:
            next_question_text = interview_agent.phases[0]["questions"][next_question]
        else:
            next_question_text = ""

        return InterviewResponse(
            session_id=session_id,
            question=next_question_text,
            is_complete=is_complete,
            progress={
                "answered": answered_questions_count + 1,
                "total": len(interview_agent.phases[0]["questions"]),
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to process answer: {str(e)}"
        )


@router.post("/{session_id}/answer", response_model=InterviewResponse)
async def answer_question(
    session_id: str,
    answer_data: UserAnswer,
    current_user: Any = Depends(get_current_user),
):
    """
    Process user's answer to the current question in an interview session and return the next question
    or a follow-up question. This endpoint updates the interview session and conversation history in
    Firestore.

    Request Parameters:
    - session_id (str): The unique identifier of the interview session.
    - answer_data (UserAnswer): The user's response to the current question in the interview.

    **Dependencies:**
    - `current_user` (str): The user ID of the authenticated user, retrieved from the JWT token.

    **Functionality:**
    1. Verifies that the interview session exists in Firestore.
    2. Ensures the user making the request is the owner of the session (authorized).
    3. Retrieves the current question for the user from the interview phases.
    4. Appends the user's answer to the conversation history.
    5. Evaluates whether a follow-up question is needed based on the user's answer.
    6. If follow-up is needed (and below the limit), generates and returns the follow-up question.
    7. If no follow-up is required, moves to the next question or phase in the interview.
    8. Marks the interview as complete when all phases are finished and saves the user's profile to Firestore.

    **Response:**
    - The response will include:
      - `session_id` (str): The interview session ID.
      - `question` (str): The next question or the follow-up question.
      - `is_complete` (bool): Indicates whether the interview is complete.
      - `follow_up` (Optional[str]): The follow-up question if applicable.

    **Errors:**
    - `404 Not Found`: If the interview session doesn't exist.
    - `403 Forbidden`: If the user is not authorized to access the session.
    - `500 Internal Server Error`: If any unexpected errors occur while processing the answer.

    **Example Usage:**
    A user makes a POST request to `/start/{session_id}/answer` with their response, and the system:
    - Checks if the session exists and belongs to the user.
    - Evaluates their answer and decides whether a follow-up is needed.
    - Returns the next question or follow-up question.
    """
    try:
        # Get session from Firestore
        db = get_firestore_client()
        session_doc = db.collection("interview_sessions").document(session_id).get()

        if not session_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview session not found",
            )

        session = clean_session_data(session_doc.to_dict())

        # Verify user owns this session
        if session["user_id"] != current_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this session",
            )

        # Get current question
        current_phase = session["current_phase"]
        current_question = session["current_question"]
        follow_up_count = session["follow_up_count"]
        answered_questions_count = session.get("answered_questions_count", 0)

        question_data = interview_agent.get_current_question(
            current_phase, current_question
        )
        current_question_text = question_data["question"]

        # Store the answer
        conversation = session.get("conversation", [])
        conversation.append(
            {
                "question": current_question_text,
                "answer": answer_data.answer,
                "phase": question_data["phase"],
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

        # Check if we need follow-up
        needs_followup = interview_agent.evaluate_answer_quality(answer_data.answer)
        total_questions = sum(len(p["questions"]) for p in interview_agent.phases)

        if needs_followup and follow_up_count < 2:
            # Generate follow-up
            follow_up = interview_agent.generate_follow_up(
                current_question_text, answer_data.answer
            )

            # Update session
            update_data = {
                "follow_up_count": follow_up_count + 1,
                "conversation": conversation,
            }

            db.collection("interview_sessions").document(session_id).update(update_data)

            return InterviewResponse(
                session_id=session_id,
                question=current_question_text,
                follow_up=follow_up,
                is_complete=False,
                progress={
                    "answered": answered_questions_count,
                    "total": total_questions,
                },
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

            if not is_complete:
                next_question_data = interview_agent.get_current_question(
                    next_phase, next_question
                )
                next_question_text = next_question_data["question"]
            else:
                next_question_text = ""

            # Increment answered count for original questions only
            answered_questions_count += 1

            # Update session
            update_data = {
                "current_phase": next_phase,
                "current_question": next_question,
                "follow_up_count": 0,
                "conversation": conversation,
                "answered_questions_count": answered_questions_count,
            }

            if is_complete:
                update_data["completed_at"] = datetime.utcnow().isoformat()

                # Generate profile if interview is complete
                user_profile = profile_generator.generate_full_profile(conversation)

                # Save profile to Firestore
                db.collection("profiles").document(current_user).set(user_profile)

            db.collection("interview_sessions").document(session_id).update(update_data)

            return InterviewResponse(
                session_id=session_id,
                question=next_question_text,
                is_complete=is_complete,
                progress={
                    "answered": answered_questions_count,
                    "total": total_questions,
                },
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process answer: {str(e)}",
        )


@router.get("/sessions")
async def get_user_sessions(current_user: Any = Depends(get_current_user)):
    """
    Get all interview sessions for the authenticated user.

    Returns:
        A list of session summaries including progress and timestamps.
    """
    try:
        db = get_firestore_client()
        sessions = (
            db.collection("interview_sessions")
            .where("user_id", "==", current_user)
            .stream()
        )

        result = []
        for session in sessions:
            session_data = session.to_dict()
            result.append(
                {
                    "session_id": session.id,
                    "started_at": session_data.get("started_at"),
                    "completed_at": session_data.get("completed_at"),
                    "progress": {
                        "phase": session_data.get("current_phase"),
                        "question": session_data.get("current_question"),
                        "total_phases": len(interview_agent.phases),
                        "is_complete": session_data.get("completed_at") is not None,
                    },
                }
            )

        return {"sessions": result}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve sessions: {str(e)}",
        )


@router.get("/{session_id}")
async def get_session_details(
    session_id: str, current_user: Any = Depends(get_current_user)
):
    """
    Retrieve detailed information about a specific interview session.

    Args:
        session_id (str): The Firestore document ID of the interview session.
        current_user (str): The authenticated user's UID (from JWT).

    Returns:
        JSON: Session metadata including progress and conversation history.
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

        return {
            "session_id": session_id,
            "started_at": session.get("started_at"),
            "completed_at": session.get("completed_at"),
            "current_phase": session.get("current_phase"),
            "current_question": session.get("current_question"),
            "conversation": session.get("conversation"),
            "is_complete": session.get("completed_at") is not None,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve session details: {str(e)}",
        )


@router.delete("/{session_id}")
async def delete_session(
    session_id: str, current_user: Any = Depends(get_current_user)
):
    """
    Delete a specific interview session owned by the authenticated user.

    Args:
        session_id (str): The Firestore document ID of the interview session.
        current_user (Any): Authenticated user (expects a UID attribute).

    Returns:
        JSON: Success message on successful deletion.
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
                detail="Not authorized to delete this session",
            )

        # Delete the session
        db.collection("interview_sessions").document(session_id).delete()

        return {"message": "Session deleted successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}",
        )
