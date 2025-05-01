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
    """Generate personalized recommendations based on user's digital twin"""
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
    """Get user's recommendation history"""
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
    """Get details of a specific recommendation"""
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
    """Get list of available recommendation categories"""
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
