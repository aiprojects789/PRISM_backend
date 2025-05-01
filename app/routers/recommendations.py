from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user
from app.models.interview import RecommendationQuery
from app.services.recommendation_engine import RecommendationEngine
from app.core.firebase import get_firestore_client
from typing import Dict, Any, List
import uuid
from datetime import datetime

router = APIRouter()
recommendation_engine = RecommendationEngine()


@router.post("/generate")
async def generate_recommendations(
    query: RecommendationQuery, current_user: Any = Depends(get_current_user)
):
    """
    Generates personalized recommendations for the authenticated user based on their digital profile.

    This endpoint retrieves the user's profile from Firestore and uses it to generate context-aware
    recommendations tailored to a specific category and optional search query. The generated
    recommendations are also stored in Firestore for historical tracking.

    Args:
        query (RecommendationQuery): The category and optional search query for recommendation generation.
        current_user (Any): The authenticated user's ID, extracted from the JWT access token.

    Returns:
        dict: A dictionary containing the recommendation ID, input parameters, and a list of generated recommendations.

    Raises:
        HTTPException (404): If the user's profile does not exist in Firestore.
        HTTPException (500): If any internal error occurs during the recommendation generation or storage process.
    """
    try:
        # Get user profile from Firestore
        db = get_firestore_client()
        profile_doc = db.collection("profiles").document(current_user).get()

        if not profile_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found. Please complete the interview first.",
            )

        user_profile = profile_doc.to_dict()

        # Generate recommendations
        recommendations = recommendation_engine.generate_recommendations(
            user_profile, category=query.category, query=query.query
        )

        # Store recommendations in Firestore
        recommendation_id = str(uuid.uuid4())
        db.collection("recommendations").document(recommendation_id).set(
            {
                "user_id": current_user,
                "category": query.category,
                "query": query.query,
                "recommendations": recommendations,
                "created_at": datetime.utcnow(),
            }
        )

        return {
            "recommendation_id": recommendation_id,
            "category": query.category,
            "query": query.query,
            "recommendations": recommendations,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendations: {str(e)}",
        )


@router.get("/history")
async def get_recommendation_history(current_user: Any = Depends(get_current_user)):
    """
    Retrieves the recommendation history for the authenticated user.

    This endpoint queries the Firestore 'recommendations' collection for records
    associated with the current user, returning a list of all past recommendation
    requests including their category, query, and creation timestamp.

    Args:
        current_user (Any): The authenticated user's ID extracted from the JWT token.

    Returns:
        dict: A dictionary containing a list of historical recommendation entries, each with:
            - recommendation_id (str): Unique Firestore document ID for the recommendation.
            - category (str): The category of the recommendation.
            - query (str): The search query used (if any).
            - created_at (datetime): Timestamp of when the recommendation was created.

    Raises:
        HTTPException (500): If an internal error occurs while fetching data from Firestore.
    """
    try:
        db = get_firestore_client()
        recommendations = (
            db.collection("recommendations")
            .where("user_id", "==", current_user)
            .stream()
        )

        result = []
        for rec in recommendations:
            rec_data = rec.to_dict()
            result.append(
                {
                    "recommendation_id": rec.id,
                    "category": rec_data.get("category"),
                    "query": rec_data.get("query"),
                    "created_at": rec_data.get("created_at"),
                }
            )

        return {"history": result}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve recommendation history: {str(e)}",
        )


@router.get("/{recommendation_id}")
async def get_recommendation_details(
    recommendation_id: str, current_user: Any = Depends(get_current_user)
):
    """
    Retrieves detailed information about a specific recommendation for the authenticated user.

    This endpoint fetches a recommendation document from Firestore by its ID and ensures
    that the requesting user is authorized to access it. If the document exists and belongs
    to the user, detailed information about the recommendation is returned.

    Args:
        recommendation_id (str): The unique Firestore document ID for the recommendation.
        current_user (Any): The authenticated user's ID extracted from the JWT token.

    Returns:
        dict: A dictionary containing:
            - recommendation_id (str): The document ID.
            - category (str): The category of the recommendation.
            - query (str): The original query (if any).
            - recommendations (list): The list of generated recommendations.
            - created_at (datetime): The timestamp when the recommendation was created.

    Raises:
        HTTPException (404): If the recommendation does not exist.
        HTTPException (403): If the user does not have permission to view this recommendation.
        HTTPException (500): If an internal error occurs while accessing Firestore.
    """
    try:
        db = get_firestore_client()
        rec_doc = db.collection("recommendations").document(recommendation_id).get()

        if not rec_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found"
            )

        rec_data = rec_doc.to_dict()

        # Verify user owns this recommendation
        if rec_data["user_id"] != current_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this recommendation",
            )

        return {
            "recommendation_id": recommendation_id,
            "category": rec_data.get("category"),
            "query": rec_data.get("query"),
            "recommendations": rec_data.get("recommendations"),
            "created_at": rec_data.get("created_at"),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve recommendation details: {str(e)}",
        )


@router.get("/categories")
async def get_recommendation_categories():
    """
    Retrieves a predefined list of available recommendation categories.

    This endpoint returns a static list of categories that users can choose from when
    generating personalized recommendations. Each category includes an ID, a display name,
    and an icon identifier that can be used in the frontend UI.

    Returns:
        dict: A dictionary containing a list of category objects, each with:
            - id (str): The unique identifier for the category.
            - name (str): A user-friendly name for the category.
            - icon (str): An icon name representing the category (e.g., for use with FontAwesome).

    Example Response:
        {
            "categories": [
                {"id": "movies", "name": "Movies & TV Shows", "icon": "film"},
                {"id": "books", "name": "Books & Reading", "icon": "book"},
                ...
            ]
        }
    """
    # You can expand this list based on your application needs
    categories = [
        {"id": "movies", "name": "Movies & TV Shows", "icon": "film"},
        {"id": "books", "name": "Books & Reading", "icon": "book"},
        {"id": "music", "name": "Music", "icon": "music"},
        {"id": "food", "name": "Food & Dining", "icon": "utensils"},
        {"id": "travel", "name": "Travel Destinations", "icon": "plane"},
        {"id": "fitness", "name": "Fitness & Wellness", "icon": "dumbbell"},
    ]

    return {"categories": categories}
