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
    query: RecommendationQuery, current_user: str = Depends(get_current_user)
):
    """
    Generate personalized recommendations using the updated RecommendationEngine.
    
    Args:
        query (RecommendationQuery): The recommendation query with category and search terms.
        current_user (str): The authenticated user ID.
        
    Returns:
        dict: Generated recommendations with metadata.
    """
    try:
        # Get user profile from Firestore (the engine will load from master profile)
        db = get_firestore_client()
        profile_doc = db.collection("profiles").document(current_user).get()
        
        user_profile = None
        if profile_doc.exists:
            user_profile = profile_doc.to_dict()
        
        # Generate recommendations based on category
        if hasattr(query, 'category') and query.category:
            recommendations = recommendation_engine.generate_category_recommendations(
                category=query.category,
                user_query=query.query or "",
                user_profile=user_profile
            )
        else:
            # General recommendations
            recommendations = recommendation_engine.generate_recommendations(
                user_query=query.query or "",
                user_profile=user_profile
            )
        
        # Generate metadata
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        category_name = getattr(query, 'category', 'general').capitalize()
        name = f"{category_name} Recommendations - {timestamp}"
        
        # Store recommendations in Firestore
        recommendation_id = str(uuid.uuid4())
        db.collection("recommendations").document(recommendation_id).set({
            "user_id": current_user,
            "category": getattr(query, 'category', 'general'),
            "query": query.query or "",
            "name": name,
            "recommendations": recommendations,
            "created_at": datetime.utcnow(),
        })
        
        return {
            "recommendation_id": recommendation_id,
            "name": name,
            "category": getattr(query, 'category', 'general'),
            "query": query.query or "",
            "recommendations": recommendations,
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Recommendation generation failed: {str(e)}"
        )


@router.post("/generate/simple")
async def generate_simple_recommendations(
    query_data: Dict[str, str], current_user: str = Depends(get_current_user)
):
    """
    Generate recommendations with a simple query string.
    
    Args:
        query_data (Dict[str, str]): Should contain 'query' key with search terms.
        current_user (str): The authenticated user ID.
        
    Returns:
        dict: Generated recommendations.
    """
    try:
        user_query = query_data.get("query", "")
        
        if not user_query:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query is required"
            )
        
        # Get user profile from Firestore
        db = get_firestore_client()
        profile_doc = db.collection("profiles").document(current_user).get()
        
        user_profile = None
        if profile_doc.exists:
            user_profile = profile_doc.to_dict()
        
        # Generate recommendations
        recommendations = recommendation_engine.generate_recommendations(
            user_query=user_query,
            user_profile=user_profile
        )
        
        # Generate metadata
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        name = f"General Recommendations - {timestamp}"
        
        # Store recommendations in Firestore
        recommendation_id = str(uuid.uuid4())
        db.collection("recommendations").document(recommendation_id).set({
            "user_id": current_user,
            "category": "general",
            "query": user_query,
            "name": name,
            "recommendations": recommendations,
            "created_at": datetime.utcnow(),
        })
        
        return {
            "recommendation_id": recommendation_id,
            "name": name,
            "category": "general",
            "query": user_query,
            "recommendations": recommendations,
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Recommendation generation failed: {str(e)}"
        )


@router.get("/history")
async def get_recommendation_history(current_user: str = Depends(get_current_user)):
    """
    Get recommendation history for the authenticated user.
    
    Args:
        current_user (str): The authenticated user ID.
        
    Returns:
        dict: List of historical recommendations.
    """
    try:
        db = get_firestore_client()
        recommendations = (
            db.collection("recommendations")
            .where("user_id", "==", current_user)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .stream()
        )
        
        result = []
        for rec in recommendations:
            rec_data = rec.to_dict()
            result.append({
                "recommendation_id": rec.id,
                "name": rec_data.get("name"),
                "category": rec_data.get("category"),
                "query": rec_data.get("query"),
                "created_at": rec_data.get("created_at"),
                "recommendation_count": len(rec_data.get("recommendations", [])),
            })
        
        return {"history": result}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve recommendation history: {str(e)}",
        )


@router.get("/{recommendation_id}")
async def get_recommendation_details(
    recommendation_id: str, current_user: str = Depends(get_current_user)
):
    """
    Get detailed information about a specific recommendation.
    
    Args:
        recommendation_id (str): The recommendation ID.
        current_user (str): The authenticated user ID.
        
    Returns:
        dict: Detailed recommendation information.
    """
    try:
        db = get_firestore_client()
        rec_doc = db.collection("recommendations").document(recommendation_id).get()
        
        if not rec_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Recommendation not found"
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
            "name": rec_data.get("name"),
            "category": rec_data.get("category"),
            "query": rec_data.get("query"),
            "recommendations": rec_data.get("recommendations", []),
            "created_at": rec_data.get("created_at"),
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve recommendation details: {str(e)}",
        )


@router.delete("/{recommendation_id}")
async def delete_recommendation(
    recommendation_id: str, current_user: str = Depends(get_current_user)
):
    """
    Delete a specific recommendation.
    
    Args:
        recommendation_id (str): The recommendation ID.
        current_user (str): The authenticated user ID.
        
    Returns:
        dict: Success message.
    """
    try:
        db = get_firestore_client()
        rec_doc = db.collection("recommendations").document(recommendation_id).get()
        
        if not rec_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recommendation not found"
            )
        
        rec_data = rec_doc.to_dict()
        
        # Verify user owns this recommendation
        if rec_data["user_id"] != current_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this recommendation",
            )
        
        # Delete the recommendation
        db.collection("recommendations").document(recommendation_id).delete()
        
        return {"message": "Recommendation deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete recommendation: {str(e)}",
        )


@router.get("/categories")
async def get_recommendation_categories():
    """
    Get available recommendation categories.
    
    Returns:
        dict: List of available categories.
    """
    categories = [
        {"id": "movies", "name": "Movies & TV Shows", "icon": "film"},
        {"id": "books", "name": "Books & Reading", "icon": "book"},
        {"id": "music", "name": "Music", "icon": "music"},
        {"id": "food", "name": "Food & Dining", "icon": "utensils"},
        {"id": "travel", "name": "Travel Destinations", "icon": "plane"},
        {"id": "fitness", "name": "Fitness & Wellness", "icon": "dumbbell"},
        {"id": "technology", "name": "Technology & Gadgets", "icon": "laptop"},
        {"id": "fashion", "name": "Fashion & Style", "icon": "tshirt"},
        {"id": "games", "name": "Games & Entertainment", "icon": "gamepad"},
        {"id": "education", "name": "Learning & Education", "icon": "graduation-cap"},
    ]
    
    return {"categories": categories}


@router.post("/batch")
async def generate_batch_recommendations(
    batch_data: Dict[str, Any], current_user: str = Depends(get_current_user)
):
    """
    Generate recommendations for multiple categories or queries at once.
    
    Args:
        batch_data (Dict[str, Any]): Contains list of queries/categories.
        current_user (str): The authenticated user ID.
        
    Returns:
        dict: Batch recommendation results.
    """
    try:
        queries = batch_data.get("queries", [])
        
        if not queries:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one query is required"
            )
        
        # Get user profile
        db = get_firestore_client()
        profile_doc = db.collection("profiles").document(current_user).get()
        
        user_profile = None
        if profile_doc.exists:
            user_profile = profile_doc.to_dict()
        
        results = []
        
        for query_item in queries:
            try:
                category = query_item.get("category")
                query_text = query_item.get("query", "")
                
                if category:
                    recommendations = recommendation_engine.generate_category_recommendations(
                        category=category,
                        user_query=query_text,
                        user_profile=user_profile
                    )
                else:
                    recommendations = recommendation_engine.generate_recommendations(
                        user_query=query_text,
                        user_profile=user_profile
                    )
                
                # Store each batch item separately
                timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
                category_name = category.capitalize() if category else "General"
                name = f"{category_name} Recommendations - {timestamp}"
                
                recommendation_id = str(uuid.uuid4())
                db.collection("recommendations").document(recommendation_id).set({
                    "user_id": current_user,
                    "category": category or "general",
                    "query": query_text,
                    "name": name,
                    "recommendations": recommendations,
                    "created_at": datetime.utcnow(),
                    "batch_id": batch_data.get("batch_id"),
                })
                
                results.append({
                    "recommendation_id": recommendation_id,
                    "category": category or "general",
                    "query": query_text,
                    "recommendations": recommendations,
                    "status": "success"
                })
                
            except Exception as e:
                results.append({
                    "category": query_item.get("category"),
                    "query": query_item.get("query"),
                    "error": str(e),
                    "status": "failed"
                })
        
        return {
            "batch_id": batch_data.get("batch_id", str(uuid.uuid4())),
            "results": results,
            "total": len(queries),
            "successful": len([r for r in results if r.get("status") == "success"]),
            "failed": len([r for r in results if r.get("status") == "failed"]),
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch recommendation generation failed: {str(e)}"
        )