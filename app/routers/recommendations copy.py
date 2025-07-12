# # # # # app/routers/recommendations.py - Enhanced with database persistence and FIXED ROUTE ORDER

# # # # from fastapi import APIRouter, Depends, HTTPException, status, Query
# # # # from pydantic import BaseModel
# # # # from typing import Dict, Any, List, Optional
# # # # import json
# # # # from openai import OpenAI
# # # # from duckduckgo_search import DDGS 
# # # # from duckduckgo_search.exceptions import DuckDuckGoSearchException
# # # # from itertools import islice
# # # # import time
# # # # import uuid
# # # # from datetime import datetime, timedelta

# # # # from app.core.security import get_current_user
# # # # from app.core.firebase import get_firestore_client
# # # # from app.core.config import get_settings
# # # # from app.routers.conversations import save_conversation_message

# # # # router = APIRouter()

# # # # # Enhanced Pydantic models
# # # # class RecommendationRequest(BaseModel):
# # # #     query: str
# # # #     category: Optional[str] = None
# # # #     user_id: Optional[str] = None
# # # #     context: Optional[Dict[str, Any]] = None

# # # # class RecommendationItem(BaseModel):
# # # #     title: str
# # # #     description: Optional[str] = None
# # # #     reasons: List[str] = []
# # # #     category: Optional[str] = None
# # # #     confidence_score: Optional[float] = None
# # # #     external_links: Optional[List[str]] = None

# # # # class RecommendationResponse(BaseModel):
# # # #     recommendation_id: str
# # # #     recommendations: List[RecommendationItem]
# # # #     query: str
# # # #     category: Optional[str] = None
# # # #     user_id: str
# # # #     generated_at: datetime
# # # #     processing_time_ms: Optional[int] = None

# # # # class RecommendationFeedback(BaseModel):
# # # #     recommendation_id: str
# # # #     feedback_type: str  # 'like', 'dislike', 'not_relevant', 'helpful'
# # # #     rating: Optional[int] = None  # 1-5 stars
# # # #     comment: Optional[str] = None
# # # #     clicked_items: List[str] = []

# # # # # Database helper functions
# # # # def save_recommendation_to_db(recommendation_data: Dict[str, Any], db) -> str:
# # # #     """Save recommendation to database and return recommendation_id"""
# # # #     try:
# # # #         recommendation_id = str(uuid.uuid4())
        
# # # #         # Prepare data for database
# # # #         db_data = {
# # # #             "recommendation_id": recommendation_id,
# # # #             "user_id": recommendation_data["user_id"],
# # # #             "query": recommendation_data["query"],
# # # #             "category": recommendation_data.get("category"),
# # # #             "recommendations": recommendation_data["recommendations"],
# # # #             "generated_at": datetime.utcnow(),
# # # #             "processing_time_ms": recommendation_data.get("processing_time_ms"),
# # # #             "search_context": recommendation_data.get("search_context", []),
# # # #             "profile_version": recommendation_data.get("profile_version"),
# # # #             "session_id": recommendation_data.get("session_id"),
# # # #             "is_active": True,
# # # #             "view_count": 0,
# # # #             "feedback_count": 0
# # # #         }
        
# # # #         # Save to user-specific collection
# # # #         db.collection("user_recommendations").document(recommendation_data["user_id"]).collection("recommendations").document(recommendation_id).set(db_data)
        
# # # #         # Also save to recommendation history for analytics
# # # #         history_data = {
# # # #             "recommendation_id": recommendation_id,
# # # #             "user_id": recommendation_data["user_id"],
# # # #             "query": recommendation_data["query"],
# # # #             "category": recommendation_data.get("category"),
# # # #             "recommendations_count": len(recommendation_data["recommendations"]),
# # # #             "created_at": datetime.utcnow(),
# # # #             "is_bookmarked": False,
# # # #             "tags": []
# # # #         }
        
# # # #         db.collection("recommendation_history").document(recommendation_id).set(history_data)
        
# # # #         return recommendation_id
        
# # # #     except Exception as e:
# # # #         print(f"Error saving recommendation: {e}")
# # # #         return None

# # # # def get_user_recommendation_history(user_id: str, db, limit: int = 20, offset: int = 0, category: str = None):
# # # #     """Get user's recommendation history from database"""
# # # #     try:
# # # #         query = db.collection("user_recommendations").document(user_id).collection("recommendations").where("is_active", "==", True)
        
# # # #         if category:
# # # #             query = query.where("category", "==", category)
        
# # # #         recommendations = query.order_by("generated_at", direction="DESCENDING").limit(limit).offset(offset).stream()
        
# # # #         history = []
# # # #         for rec in recommendations:
# # # #             rec_data = rec.to_dict()
# # # #             history.append({
# # # #                 "recommendation_id": rec_data["recommendation_id"],
# # # #                 "query": rec_data["query"],
# # # #                 "category": rec_data.get("category"),
# # # #                 "recommendations_count": len(rec_data.get("recommendations", [])),
# # # #                 "generated_at": rec_data["generated_at"],
# # # #                 "view_count": rec_data.get("view_count", 0),
# # # #                 "feedback_count": rec_data.get("feedback_count", 0),
# # # #                 "session_id": rec_data.get("session_id")
# # # #             })
        
# # # #         return history
        
# # # #     except Exception as e:
# # # #         print(f"Error getting recommendation history: {e}")
# # # #         return []

# # # # def save_recommendation_feedback(recommendation_id: str, user_id: str, feedback_data: Dict[str, Any], db):
# # # #     """Save user feedback for a recommendation"""
# # # #     try:
# # # #         feedback_id = str(uuid.uuid4())
        
# # # #         feedback_doc = {
# # # #             "feedback_id": feedback_id,
# # # #             "recommendation_id": recommendation_id,
# # # #             "user_id": user_id,
# # # #             "feedback_type": feedback_data["feedback_type"],
# # # #             "rating": feedback_data.get("rating"),
# # # #             "comment": feedback_data.get("comment"),
# # # #             "clicked_items": feedback_data.get("clicked_items", []),
# # # #             "created_at": datetime.utcnow()
# # # #         }
        
# # # #         # Save feedback
# # # #         db.collection("recommendation_feedback").document(feedback_id).set(feedback_doc)
        
# # # #         # Update recommendation with feedback count
# # # #         rec_ref = db.collection("user_recommendations").document(user_id).collection("recommendations").document(recommendation_id)
# # # #         rec_doc = rec_ref.get()
        
# # # #         if rec_doc.exists:
# # # #             current_feedback_count = rec_doc.to_dict().get("feedback_count", 0)
# # # #             rec_ref.update({"feedback_count": current_feedback_count + 1})
        
# # # #         return feedback_id
        
# # # #     except Exception as e:
# # # #         print(f"Error saving feedback: {e}")
# # # #         return None

# # # # # Recommendation Engine implementation
# # # # def load_user_profile(user_id: str = None) -> Dict[str, Any]:
# # # #     """Load USER-SPECIFIC profile from Firestore"""
# # # #     try:
# # # #         db = get_firestore_client()
        
# # # #         if not user_id:
# # # #             print("❌ No user_id provided for profile loading")
# # # #             return {}
        
# # # #         # Load user-specific profile structure
# # # #         profile_doc_id = f"{user_id}_profile_structure.json"
# # # #         profile_doc = db.collection("user_profiles").document(profile_doc_id).get()
        
# # # #         if profile_doc.exists:
# # # #             print(f"✅ Loaded user-specific profile for user: {user_id}")
# # # #             return profile_doc.to_dict()
# # # #         else:
# # # #             print(f"❌ No user-specific profile found for user: {user_id}")
            
# # # #             # Fallback: Try old location for backward compatibility
# # # #             fallback_doc = db.collection("user_collection").document(f"{user_id}_profile_structure.json").get()
# # # #             if fallback_doc.exists:
# # # #                 print(f"✅ Loaded profile from fallback location for user: {user_id}")
# # # #                 return fallback_doc.to_dict()
            
# # # #             print(f"❌ No profile found in any location for user: {user_id}")
# # # #             return {}
            
# # # #     except Exception as e:
# # # #         print(f"❌ Error loading user profile for {user_id}: {e}")
# # # #         return {}

# # # # def search_web(query, max_results=3, max_retries=3, base_delay=1.0):
# # # #     """Query DuckDuckGo via DDGS.text(), returning up to max_results items."""
# # # #     for attempt in range(1, max_retries + 1):
# # # #         try:
# # # #             with DDGS() as ddgs:
# # # #                 return list(islice(ddgs.text(query), max_results))
# # # #         except DuckDuckGoSearchException as e:
# # # #             msg = str(e)
# # # #             if "202" in msg:
# # # #                 wait = base_delay * (2 ** (attempt - 1))
# # # #                 print(f"[search_web] Rate‑limited (202). Retry {attempt}/{max_retries} in {wait:.1f}s…")
# # # #                 time.sleep(wait)
# # # #             else:
# # # #                 raise
# # # #         except Exception as e:
# # # #             print(f"[search_web] Unexpected error: {e}")
# # # #             break
    
# # # #     print(f"[search_web] Failed to fetch results after {max_retries} attempts.")
# # # #     return []

# # # # def generate_recommendations(user_profile, user_query, openai_key):
# # # #     """Generate 3 personalized recommendations using user profile and web search"""
# # # #     # Getting current web context
# # # #     search_results = search_web(f"{user_query} recommendations 2024")
    
# # # #     prompt = f"""
# # # #     **Task**: Generate exactly 3 highly personalized recommendations based on:
    
# # # #     **User Profile**:
# # # #     {json.dumps(user_profile, indent=2)}
    
# # # #     **User Query**:
# # # #     "{user_query}"
    
# # # #     **Web Context** (for reference only):
# # # #     {search_results}
    
# # # #     **Requirements**:
# # # #     1. Each recommendation must directly reference profile details
# # # #     2. Blend the user's core values and preferences
# # # #     3. Only suggest what is asked for suggest no extra advices.
# # # #     4. Format as JSON array with each recommendation having:
# # # #        - title: string
# # # #        - description: string (brief description)
# # # #        - reasons: array of strings (why it matches the user profile)
# # # #        - confidence_score: float (0.0-1.0)
    
# # # #     **Output Example**:
# # # #     [
# # # #       {{
# # # #          "title": "Creative Project Tool",
# # # #          "description": "Notion's creative templates for content planning",
# # # #          "reasons": ["Matches your love for storytelling and freelance work", "Supports your creative workflow"],
# # # #          "confidence_score": 0.9
# # # #       }},
# # # #       {{
# # # #          "title": "Historical Drama Series",
# # # #          "description": "Epic series focusing on leadership and personal struggles",
# # # #          "reasons": ["Resonates with your interest in historical figures", "Explores themes of resilience you value"],
# # # #          "confidence_score": 0.85
# # # #       }},
# # # #       {{
# # # #          "title": "Motivational Biopic",
# # # #          "description": "Inspiring story of overcoming personal difficulties",
# # # #          "reasons": ["Highlights overcoming personal difficulties", "Aligns with your experiences of resilience"],
# # # #          "confidence_score": 0.8
# # # #       }}
# # # #     ]
    
# # # #     Generate your response in JSON format only.
# # # #     """
    
# # # #     # Setting up LLM
# # # #     client = OpenAI(api_key=openai_key)

# # # #     response = client.chat.completions.create(
# # # #         model="gpt-4",
# # # #         messages=[
# # # #             {"role": "system", "content": "You're a recommendation engine that creates hyper-personalized suggestions. Output valid JSON only."},
# # # #             {"role": "user", "content": prompt}
# # # #         ],
# # # #         temperature=0.7  
# # # #     )
    
# # # #     return response.choices[0].message.content

# # # # # ROUTE DEFINITIONS - SPECIFIC ROUTES FIRST, PARAMETERIZED ROUTES LAST

# # # # # @router.get("/profile")
# # # # # async def get_user_profile(current_user: str = Depends(get_current_user)):
# # # # #     """Get the current user's SPECIFIC profile"""
# # # # #     try:
# # # # #         print(f"🔍 Getting profile for user: {current_user}")
# # # # #         profile = load_user_profile(current_user)
        
# # # # #         if not profile:
# # # # #             # Check if user has completed interview
# # # # #             db = get_firestore_client()
# # # # #             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user).where("status", "==", "completed").limit(1)
# # # # #             completed_sessions = list(sessions_ref.stream())
            
# # # # #             if not completed_sessions:
# # # # #                 raise HTTPException(
# # # # #                     status_code=404,
# # # # #                     detail="No profile found. Please complete an interview first to generate your profile."
# # # # #                 )
# # # # #             else:
# # # # #                 raise HTTPException(
# # # # #                     status_code=404,
# # # # #                     detail="Profile completed but not found in database. Please contact support."
# # # # #                 )
        
# # # # #         # Remove sensitive metadata for response
# # # # #         profile_response = {k: v for k, v in profile.items() if k not in ['user_id', 'created_at', 'updated_at']}
        
# # # # #         return {
# # # # #             "success": True,
# # # # #             "profile": profile_response,
# # # # #             "user_id": current_user,
# # # # #             "profile_type": "user_specific",
# # # # #             "profile_found": True
# # # # #         }
        
# # # # #     except HTTPException:
# # # # #         raise
# # # # #     except Exception as e:
# # # # #         print(f"❌ Error in get_user_profile: {e}")
# # # # #         raise HTTPException(
# # # # #             status_code=500,
# # # # #             detail=f"Failed to load profile: {str(e)}"
# # # # #         )
# # # # # Fixed load_user_profile function in recommendations.py

# # # # def load_user_profile(user_id: str = None) -> Dict[str, Any]:
# # # #     """Load USER-SPECIFIC profile from Firestore - FIXED VERSION"""
# # # #     try:
# # # #         db = get_firestore_client()
        
# # # #         if not user_id:
# # # #             print("❌ No user_id provided for profile loading")
# # # #             return {}
        
# # # #         print(f"🔍 Looking for profile for user: {user_id}")
        
# # # #         # Try multiple possible profile document locations
# # # #         profile_locations = [
# # # #             # Primary location - user-specific profiles
# # # #             {
# # # #                 "collection": "user_profiles",
# # # #                 "document": f"{user_id}_profile_structure.json",
# # # #                 "description": "Primary user_profiles collection"
# # # #             },
# # # #             # Fallback 1 - user_collection with user prefix
# # # #             {
# # # #                 "collection": "user_collection", 
# # # #                 "document": f"{user_id}_profile_structure.json",
# # # #                 "description": "Fallback user_collection with user prefix"
# # # #             },
# # # #             # Fallback 2 - check if there's a completed interview profile
# # # #             {
# # # #                 "collection": "interview_profiles",
# # # #                 "document": f"{user_id}_profile.json", 
# # # #                 "description": "Interview-generated profile"
# # # #             },
# # # #             # Fallback 3 - user-specific collection
# # # #             {
# # # #                 "collection": f"user_{user_id}",
# # # #                 "document": "profile_structure.json",
# # # #                 "description": "User-specific collection"
# # # #             }
# # # #         ]
        
# # # #         for location in profile_locations:
# # # #             try:
# # # #                 doc_ref = db.collection(location["collection"]).document(location["document"])
# # # #                 doc = doc_ref.get()
                
# # # #                 if doc.exists:
# # # #                     profile_data = doc.to_dict()
                    
# # # #                     # CRITICAL: Verify this profile actually belongs to the requested user
# # # #                     profile_user_ids = []
                    
# # # #                     # Check various ways user_id might be stored in the profile
# # # #                     if "user_id" in profile_data:
# # # #                         profile_user_ids.append(profile_data["user_id"])
                    
# # # #                     # Check nested user_id references
# # # #                     def find_user_ids_in_dict(data, path=""):
# # # #                         user_ids = []
# # # #                         if isinstance(data, dict):
# # # #                             for key, value in data.items():
# # # #                                 if key == "user_id" and isinstance(value, str):
# # # #                                     user_ids.append(value)
# # # #                                 elif isinstance(value, dict):
# # # #                                     user_ids.extend(find_user_ids_in_dict(value, f"{path}.{key}"))
# # # #                         return user_ids
                    
# # # #                     nested_user_ids = find_user_ids_in_dict(profile_data)
# # # #                     profile_user_ids.extend(nested_user_ids)
                    
# # # #                     # Verify profile ownership
# # # #                     if profile_user_ids:
# # # #                         # Check if ANY of the found user_ids match the requested user
# # # #                         if user_id in profile_user_ids:
# # # #                             print(f"✅ Found matching profile at {location['description']}")
# # # #                             print(f"✅ Profile belongs to user: {user_id}")
# # # #                             return profile_data
# # # #                         else:
# # # #                             print(f"⚠️ Found profile at {location['description']} but belongs to: {profile_user_ids}")
# # # #                             print(f"⚠️ Requested user: {user_id} - MISMATCH!")
# # # #                             continue
# # # #                     else:
# # # #                         # No user_id found in profile - this might be a generic profile
# # # #                         print(f"⚠️ Found profile at {location['description']} but no user_id found - might be generic")
# # # #                         # For now, skip profiles without clear ownership
# # # #                         continue
                        
# # # #             except Exception as e:
# # # #                 print(f"❌ Error checking {location['description']}: {e}")
# # # #                 continue
        
# # # #         # If no user-specific profile found, check for interview completion
# # # #         print(f"❌ No user-specific profile found for user: {user_id}")
        
# # # #         # Check if user has completed an interview but profile wasn't generated properly
# # # #         try:
# # # #             sessions_query = db.collection("interview_sessions").where("user_id", "==", user_id).where("status", "==", "completed").limit(1)
# # # #             completed_sessions = list(sessions_query.stream())
            
# # # #             if completed_sessions:
# # # #                 print(f"🔍 User {user_id} has completed interview but no profile found - this needs investigation")
# # # #                 # You might want to trigger profile generation here
# # # #                 return {
# # # #                     "error": "profile_generation_needed",
# # # #                     "message": "Interview completed but profile not generated",
# # # #                     "user_id": user_id,
# # # #                     "completed_sessions": len(completed_sessions)
# # # #                 }
# # # #             else:
# # # #                 print(f"📋 User {user_id} has not completed interview yet")
# # # #                 return {}
                
# # # #         except Exception as e:
# # # #             print(f"❌ Error checking interview status: {e}")
# # # #             return {}
            
# # # #     except Exception as e:
# # # #         print(f"❌ Error loading user profile for {user_id}: {e}")
# # # #         return {}


# # # # # Updated profile endpoint with better error handling
# # # # @router.get("/profile")
# # # # async def get_user_profile(current_user: str = Depends(get_current_user)):
# # # #     """Get the current user's SPECIFIC profile - FIXED VERSION"""
# # # #     try:
# # # #         print(f"🔍 Getting profile for user: {current_user}")
# # # #         profile = load_user_profile(current_user)
        
# # # #         # Handle special error cases
# # # #         if isinstance(profile, dict) and profile.get("error") == "profile_generation_needed":
# # # #             raise HTTPException(
# # # #                 status_code=404,
# # # #                 detail=f"Interview completed but profile not generated for user {current_user}. Please contact support or retry profile generation."
# # # #             )
        
# # # #         if not profile:
# # # #             # Check if user has completed interview
# # # #             db = get_firestore_client()
# # # #             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user).where("status", "==", "completed").limit(1)
# # # #             completed_sessions = list(sessions_ref.stream())
            
# # # #             if not completed_sessions:
# # # #                 raise HTTPException(
# # # #                     status_code=404,
# # # #                     detail="No profile found. Please complete an interview first to generate your profile."
# # # #                 )
# # # #             else:
# # # #                 raise HTTPException(
# # # #                     status_code=404,
# # # #                     detail="Profile completed but not found in database. Please contact support."
# # # #                 )
        
# # # #         # CRITICAL: Double-check that profile belongs to current_user
# # # #         profile_user_ids = []
        
# # # #         # Check for user_id in profile
# # # #         if "user_id" in profile:
# # # #             profile_user_ids.append(profile["user_id"])
        
# # # #         # Check nested structures for user_ids
# # # #         def extract_user_ids(data):
# # # #             user_ids = []
# # # #             if isinstance(data, dict):
# # # #                 for key, value in data.items():
# # # #                     if key == "user_id" and isinstance(value, str):
# # # #                         user_ids.append(value)
# # # #                     elif isinstance(value, dict):
# # # #                         user_ids.extend(extract_user_ids(value))
# # # #             return user_ids
        
# # # #         nested_user_ids = extract_user_ids(profile)
# # # #         profile_user_ids.extend(nested_user_ids)
        
# # # #         # Verify profile ownership
# # # #         if profile_user_ids and current_user not in profile_user_ids:
# # # #             print(f"🚨 SECURITY ALERT: Profile mismatch!")
# # # #             print(f"🚨 Requested user: {current_user}")
# # # #             print(f"🚨 Profile belongs to: {profile_user_ids}")
            
# # # #             raise HTTPException(
# # # #                 status_code=403,
# # # #                 detail="Profile ownership mismatch. Please contact support."
# # # #             )
        
# # # #         # Remove sensitive metadata for response
# # # #         profile_response = {k: v for k, v in profile.items() if k not in ['created_at', 'updated_at']}
        
# # # #         return {
# # # #             "success": True,
# # # #             "profile": profile_response,
# # # #             "user_id": current_user,
# # # #             "profile_type": "user_specific",
# # # #             "profile_found": True,
# # # #             "profile_user_ids_found": list(set(profile_user_ids))  # For debugging
# # # #         }
        
# # # #     except HTTPException:
# # # #         raise
# # # #     except Exception as e:
# # # #         print(f"❌ Error in get_user_profile: {e}")
# # # #         raise HTTPException(
# # # #             status_code=500,
# # # #             detail=f"Failed to load profile: {str(e)}"
# # # #         )
# # # # @router.get("/categories")
# # # # async def get_recommendation_categories():
# # # #     """Get available recommendation categories"""
# # # #     categories = [
# # # #         {
# # # #             "id": "movies",
# # # #             "name": "Movies & TV",
# # # #             "description": "Movie and TV show recommendations",
# # # #             "questions_file": "moviesAndTV_tiered_questions.json"
# # # #         },
# # # #         {
# # # #             "id": "food",
# # # #             "name": "Food & Dining",
# # # #             "description": "Restaurant and food recommendations",
# # # #             "questions_file": "foodAndDining_tiered_questions.json"
# # # #         },
# # # #         {
# # # #             "id": "travel",
# # # #             "name": "Travel",
# # # #             "description": "Travel destination recommendations",
# # # #             "questions_file": "travel_tiered_questions.json"
# # # #         },
# # # #         {
# # # #             "id": "books",
# # # #             "name": "Books & Reading",
# # # #             "description": "Book recommendations",
# # # #             "questions_file": "books_tiered_questions.json"
# # # #         },
# # # #         {
# # # #             "id": "music",
# # # #             "name": "Music",
# # # #             "description": "Music and artist recommendations",
# # # #             "questions_file": "music_tiered_questions.json"
# # # #         },
# # # #         {
# # # #             "id": "fitness",
# # # #             "name": "Fitness & Wellness",
# # # #             "description": "Fitness and wellness recommendations",
# # # #             "questions_file": "fitness_tiered_questions.json"
# # # #         }
# # # #     ]
    
# # # #     return {
# # # #         "categories": categories,
# # # #         "default_category": "movies"
# # # #     }

# # # # @router.get("/history")
# # # # async def get_recommendation_history(
# # # #     current_user: str = Depends(get_current_user),
# # # #     limit: int = Query(20, description="Number of recommendations to return"),
# # # #     offset: int = Query(0, description="Number of recommendations to skip")
# # # # ):
# # # #     """Get recommendation history for the user - simplified version"""
# # # #     try:
# # # #         db = get_firestore_client()
        
# # # #         # Simplified query - only filter by is_active
# # # #         query = db.collection("user_recommendations").document(current_user).collection("recommendations")
# # # #         query = query.where("is_active", "==", True)
# # # #         query = query.limit(limit).offset(offset)
        
# # # #         # Get all recommendations (without ordering initially)
# # # #         recommendations = list(query.stream())
        
# # # #         # Sort in Python instead of Firestore
# # # #         recommendations.sort(key=lambda x: x.to_dict().get("generated_at", datetime.min), reverse=True)
        
# # # #         history = []
# # # #         for rec in recommendations:
# # # #             rec_data = rec.to_dict()
# # # #             history.append({
# # # #                 "recommendation_id": rec_data["recommendation_id"],
# # # #                 "query": rec_data["query"],
# # # #                 "category": rec_data.get("category"),
# # # #                 "recommendations_count": len(rec_data.get("recommendations", [])),
# # # #                 "generated_at": rec_data["generated_at"],
# # # #                 "view_count": rec_data.get("view_count", 0),
# # # #                 "feedback_count": rec_data.get("feedback_count", 0),
# # # #                 "session_id": rec_data.get("session_id"),
# # # #                 "processing_time_ms": rec_data.get("processing_time_ms")
# # # #             })
        
# # # #         return {
# # # #             "success": True,
# # # #             "history": history,
# # # #             "total_count": len(history),
# # # #             "user_id": current_user,
# # # #             "note": "Using simplified query - create Firebase index for better performance"
# # # #         }
        
# # # #     except Exception as e:
# # # #         raise HTTPException(
# # # #             status_code=500,
# # # #             detail=f"Failed to get recommendation history: {str(e)}"
# # # #         )

# # # # @router.get("/analytics/summary")
# # # # async def get_recommendation_analytics(
# # # #     current_user: str = Depends(get_current_user),
# # # #     days: int = Query(30, description="Number of days to analyze")
# # # # ):
# # # #     """Get recommendation analytics for the user"""
# # # #     try:
# # # #         db = get_firestore_client()
        
# # # #         # Calculate date range
# # # #         end_date = datetime.utcnow()
# # # #         start_date = end_date - timedelta(days=days)
        
# # # #         # Get recommendations in date range
# # # #         recommendations_ref = db.collection("user_recommendations").document(current_user).collection("recommendations")
# # # #         recommendations = recommendations_ref.where("generated_at", ">=", start_date).where("is_active", "==", True).stream()
        
# # # #         analytics = {
# # # #             "total_recommendations": 0,
# # # #             "categories_explored": set(),
# # # #             "query_types": {},
# # # #             "total_views": 0,
# # # #             "total_feedback": 0,
# # # #             "average_processing_time": 0,
# # # #             "recommendations_by_day": {},
# # # #             "most_popular_category": None,
# # # #             "engagement_rate": 0
# # # #         }
        
# # # #         processing_times = []
# # # #         daily_counts = {}
# # # #         category_counts = {}
        
# # # #         for rec in recommendations:
# # # #             rec_data = rec.to_dict()
# # # #             analytics["total_recommendations"] += 1
            
# # # #             # Track categories
# # # #             category = rec_data.get("category", "general")
# # # #             analytics["categories_explored"].add(category)
# # # #             category_counts[category] = category_counts.get(category, 0) + 1
            
# # # #             # Track views and feedback
# # # #             analytics["total_views"] += rec_data.get("view_count", 0)
# # # #             analytics["total_feedback"] += rec_data.get("feedback_count", 0)
            
# # # #             # Track processing times
# # # #             if rec_data.get("processing_time_ms"):
# # # #                 processing_times.append(rec_data["processing_time_ms"])
            
# # # #             # Track daily activity
# # # #             rec_date = rec_data["generated_at"]
# # # #             if hasattr(rec_date, 'date'):
# # # #                 date_str = rec_date.date().isoformat()
# # # #             else:
# # # #                 date_str = datetime.fromisoformat(str(rec_date)).date().isoformat()
            
# # # #             daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
        
# # # #         # Calculate averages and insights
# # # #         if analytics["total_recommendations"] > 0:
# # # #             analytics["engagement_rate"] = round((analytics["total_views"] / analytics["total_recommendations"]) * 100, 2)
        
# # # #         if processing_times:
# # # #             analytics["average_processing_time"] = round(sum(processing_times) / len(processing_times), 2)
        
# # # #         if category_counts:
# # # #             analytics["most_popular_category"] = max(category_counts, key=category_counts.get)
        
# # # #         analytics["categories_explored"] = list(analytics["categories_explored"])
# # # #         analytics["recommendations_by_day"] = daily_counts
# # # #         analytics["category_breakdown"] = category_counts
        
# # # #         return {
# # # #             "success": True,
# # # #             "analytics": analytics,
# # # #             "period": {
# # # #                 "start_date": start_date.isoformat(),
# # # #                 "end_date": end_date.isoformat(),
# # # #                 "days": days
# # # #             },
# # # #             "user_id": current_user
# # # #         }
        
# # # #     except Exception as e:
# # # #         raise HTTPException(
# # # #             status_code=500,
# # # #             detail=f"Failed to get recommendation analytics: {str(e)}"
# # # #         )

# # # # @router.get("/debug/profile-location")
# # # # async def debug_profile_location(current_user: str = Depends(get_current_user)):
# # # #     """Debug endpoint to check where user profile is stored"""
# # # #     try:
# # # #         db = get_firestore_client()
        
# # # #         locations_checked = {
# # # #             "user_profiles": False,
# # # #             "user_collection": False,
# # # #             "fallback_locations": {}
# # # #         }
        
# # # #         # Check primary location
# # # #         profile_doc_id = f"{current_user}_profile_structure.json"
# # # #         profile_doc = db.collection("user_profiles").document(profile_doc_id).get()
# # # #         locations_checked["user_profiles"] = profile_doc.exists
        
# # # #         # Check fallback location
# # # #         fallback_doc = db.collection("user_collection").document(profile_doc_id).get()
# # # #         locations_checked["user_collection"] = fallback_doc.exists
        
# # # #         # Check other possible locations
# # # #         possible_docs = [
# # # #             "profile_strcuture.json",  # Original typo
# # # #             "profile_structure.json",
# # # #             f"{current_user}_profile.json"
# # # #         ]
        
# # # #         for doc_name in possible_docs:
# # # #             doc_exists = db.collection("user_collection").document(doc_name).get().exists
# # # #             locations_checked["fallback_locations"][doc_name] = doc_exists
        
# # # #         return {
# # # #             "success": True,
# # # #             "user_id": current_user,
# # # #             "locations_checked": locations_checked,
# # # #             "expected_document": profile_doc_id,
# # # #             "collections_searched": ["user_profiles", "user_collection"]
# # # #         }
        
# # # #     except Exception as e:
# # # #         return {
# # # #             "success": False,
# # # #             "error": str(e),
# # # #             "user_id": current_user
# # # #         }

# # # # @router.post("/generate", response_model=RecommendationResponse)
# # # # async def generate_user_recommendations(
# # # #     request: RecommendationRequest,
# # # #     current_user: str = Depends(get_current_user)
# # # # ):
# # # #     """Generate personalized recommendations based on USER-SPECIFIC profile and query"""
# # # #     try:
# # # #         start_time = datetime.utcnow()
# # # #         settings = get_settings()
# # # #         db = get_firestore_client()
        
# # # #         print(f"🚀 Generating recommendations for user: {current_user}")
# # # #         print(f"📝 Query: {request.query}")
        
# # # #         # Load USER-SPECIFIC profile
# # # #         user_profile = load_user_profile(current_user)
        
# # # #         if not user_profile:
# # # #             raise HTTPException(
# # # #                 status_code=404, 
# # # #                 detail="No profile found for this user. Please complete an interview first to generate your personalized profile."
# # # #             )
        
# # # #         print(f"✅ Loaded profile for user {current_user}")
        
# # # #         # Generate session ID for conversation tracking
# # # #         session_id = str(uuid.uuid4())
        
# # # #         # Save user query to conversation history
# # # #         save_conversation_message(
# # # #             current_user, 
# # # #             session_id, 
# # # #             "user", 
# # # #             f"Generate recommendations for: {request.query}", 
# # # #             "recommendation",
# # # #             f"Recommendation Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
# # # #         )
        
# # # #         # Generate recommendations using USER-SPECIFIC profile
# # # #         recs_json = generate_recommendations(
# # # #             user_profile, 
# # # #             request.query, 
# # # #             settings.OPENAI_API_KEY
# # # #         )
        
# # # #         try:
# # # #             recs = json.loads(recs_json)
            
# # # #             # Normalize to list
# # # #             if isinstance(recs, dict):
# # # #                 if "recommendations" in recs and isinstance(recs["recommendations"], list):
# # # #                     recs = recs["recommendations"]
# # # #                 else:
# # # #                     recs = [recs]
            
# # # #             if not isinstance(recs, list):
# # # #                 raise HTTPException(
# # # #                     status_code=500,
# # # #                     detail="Unexpected response format – expected a list of recommendations."
# # # #                 )
            
# # # #             # Calculate processing time
# # # #             processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
# # # #             # Prepare recommendation data for database
# # # #             recommendation_data = {
# # # #                 "user_id": current_user,
# # # #                 "query": request.query,
# # # #                 "category": request.category,
# # # #                 "recommendations": recs,
# # # #                 "processing_time_ms": int(processing_time),
# # # #                 "search_context": search_web(f"{request.query} recommendations 2024"),
# # # #                 "session_id": session_id,
# # # #                 "profile_version": user_profile.get("version", "1.0"),
# # # #                 "user_specific": True
# # # #             }
            
# # # #             # Save to database
# # # #             recommendation_id = save_recommendation_to_db(recommendation_data, db)
            
# # # #             if not recommendation_id:
# # # #                 print("⚠️ Warning: Failed to save recommendation to database")
# # # #                 recommendation_id = str(uuid.uuid4())  # Fallback
            
# # # #             # Format recommendations for conversation history
# # # #             recs_text = f"Here are your personalized recommendations based on your profile:\n\n"
# # # #             for i, rec in enumerate(recs, 1):
# # # #                 recs_text += f"{i}. **{rec.get('title', 'Recommendation')}**\n"
# # # #                 recs_text += f"   {rec.get('description', rec.get('reason', 'No description provided'))}\n"
# # # #                 if 'reasons' in rec and isinstance(rec['reasons'], list):
# # # #                     for reason in rec['reasons']:
# # # #                         recs_text += f"   • {reason}\n"
# # # #                 recs_text += "\n"
            
# # # #             # Save recommendations to conversation history
# # # #             save_conversation_message(
# # # #                 current_user, 
# # # #                 session_id, 
# # # #                 "assistant", 
# # # #                 recs_text, 
# # # #                 "recommendation"
# # # #             )
            
# # # #             # Convert to RecommendationItem objects
# # # #             recommendation_items = []
# # # #             for rec in recs:
# # # #                 recommendation_items.append(RecommendationItem(
# # # #                     title=rec.get('title', 'Recommendation'),
# # # #                     description=rec.get('description', rec.get('reason', '')),
# # # #                     reasons=rec.get('reasons', [rec.get('reason', '')] if rec.get('reason') else []),
# # # #                     category=request.category,
# # # #                     confidence_score=rec.get('confidence_score', 0.8)
# # # #                 ))
            
# # # #             return RecommendationResponse(
# # # #                 recommendation_id=recommendation_id,
# # # #                 recommendations=recommendation_items,
# # # #                 query=request.query,
# # # #                 category=request.category,
# # # #                 user_id=current_user,
# # # #                 generated_at=datetime.utcnow(),
# # # #                 processing_time_ms=int(processing_time)
# # # #             )
            
# # # #         except json.JSONDecodeError as e:
# # # #             error_msg = f"Failed to parse recommendations: {str(e)}"
            
# # # #             # Save error to conversation history
# # # #             save_conversation_message(
# # # #                 current_user, 
# # # #                 session_id, 
# # # #                 "assistant", 
# # # #                 f"Sorry, I encountered an error generating recommendations: {error_msg}", 
# # # #                 "recommendation"
# # # #             )
            
# # # #             raise HTTPException(
# # # #                 status_code=500,
# # # #                 detail=error_msg
# # # #             )
            
# # # #     except HTTPException:
# # # #         raise
# # # #     except Exception as e:
# # # #         print(f"❌ Error generating recommendations for user {current_user}: {e}")
# # # #         raise HTTPException(
# # # #             status_code=500,
# # # #             detail=f"Failed to generate recommendations: {str(e)}"
# # # #         )

# # # # @router.post("/category")
# # # # async def generate_category_recommendations(
# # # #     request: RecommendationRequest,
# # # #     current_user: str = Depends(get_current_user)
# # # # ):
# # # #     """Generate category-specific recommendations - redirect to main generate endpoint"""
# # # #     # This now uses the enhanced generate endpoint
# # # #     return await generate_user_recommendations(request, current_user)

# # # # @router.post("/{recommendation_id}/feedback")
# # # # async def submit_recommendation_feedback(
# # # #     recommendation_id: str,
# # # #     feedback: RecommendationFeedback,
# # # #     current_user: str = Depends(get_current_user)
# # # # ):
# # # #     """Submit feedback for a recommendation"""
# # # #     try:
# # # #         db = get_firestore_client()
        
# # # #         # Verify recommendation exists and belongs to user
# # # #         rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
# # # #         if not rec_doc.exists:
# # # #             raise HTTPException(status_code=404, detail="Recommendation not found")
        
# # # #         # Save feedback
# # # #         feedback_data = {
# # # #             "feedback_type": feedback.feedback_type,
# # # #             "rating": feedback.rating,
# # # #             "comment": feedback.comment,
# # # #             "clicked_items": feedback.clicked_items
# # # #         }
        
# # # #         feedback_id = save_recommendation_feedback(recommendation_id, current_user, feedback_data, db)
        
# # # #         if not feedback_id:
# # # #             raise HTTPException(status_code=500, detail="Failed to save feedback")
        
# # # #         return {
# # # #             "success": True,
# # # #             "message": "Feedback submitted successfully",
# # # #             "feedback_id": feedback_id,
# # # #             "recommendation_id": recommendation_id
# # # #         }
        
# # # #     except Exception as e:
# # # #         raise HTTPException(
# # # #             status_code=500,
# # # #             detail=f"Failed to submit feedback: {str(e)}"
# # # #         )

# # # # @router.delete("/{recommendation_id}")
# # # # async def delete_recommendation(
# # # #     recommendation_id: str,
# # # #     current_user: str = Depends(get_current_user)
# # # # ):
# # # #     """Delete a recommendation from history"""
# # # #     try:
# # # #         db = get_firestore_client()
        
# # # #         # Verify recommendation exists and belongs to user
# # # #         rec_ref = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id)
# # # #         rec_doc = rec_ref.get()
        
# # # #         if not rec_doc.exists:
# # # #             raise HTTPException(status_code=404, detail="Recommendation not found")
        
# # # #         # Soft delete
# # # #         rec_ref.update({
# # # #             "is_active": False,
# # # #             "deleted_at": datetime.utcnow()
# # # #         })
        
# # # #         # Also update in recommendation_history
# # # #         db.collection("recommendation_history").document(recommendation_id).update({
# # # #             "is_active": False,
# # # #             "deleted_at": datetime.utcnow()
# # # #         })
        
# # # #         return {
# # # #             "success": True,
# # # #             "message": f"Recommendation {recommendation_id} deleted successfully"
# # # #         }
        
# # # #     except Exception as e:
# # # #         raise HTTPException(
# # # #             status_code=500,
# # # #             detail=f"Failed to delete recommendation: {str(e)}"
# # # #         )

# # # # # IMPORTANT: Put parameterized routes LAST to avoid route conflicts
# # # # @router.get("/{recommendation_id}")
# # # # async def get_recommendation_details(
# # # #     recommendation_id: str,
# # # #     current_user: str = Depends(get_current_user)
# # # # ):
# # # #     """Get detailed information about a specific recommendation"""
# # # #     try:
# # # #         db = get_firestore_client()
        
# # # #         # Get recommendation details
# # # #         rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
# # # #         if not rec_doc.exists:
# # # #             raise HTTPException(status_code=404, detail="Recommendation not found")
        
# # # #         rec_data = rec_doc.to_dict()
        
# # # #         # Increment view count
# # # #         current_views = rec_data.get("view_count", 0)
# # # #         db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).update({
# # # #             "view_count": current_views + 1,
# # # #             "last_viewed": datetime.utcnow()
# # # #         })
        
# # # #         # Get feedback for this recommendation
# # # #         feedback_query = db.collection("recommendation_feedback").where("recommendation_id", "==", recommendation_id).where("user_id", "==", current_user)
# # # #         feedback_docs = feedback_query.stream()
        
# # # #         feedback_list = []
# # # #         for feedback_doc in feedback_docs:
# # # #             feedback_data = feedback_doc.to_dict()
# # # #             feedback_list.append({
# # # #                 "feedback_id": feedback_data["feedback_id"],
# # # #                 "feedback_type": feedback_data["feedback_type"],
# # # #                 "rating": feedback_data.get("rating"),
# # # #                 "comment": feedback_data.get("comment"),
# # # #                 "created_at": feedback_data["created_at"]
# # # #             })
        
# # # #         return {
# # # #             "success": True,
# # # #             "recommendation": {
# # # #                 "recommendation_id": rec_data["recommendation_id"],
# # # #                 "query": rec_data["query"],
# # # #                 "category": rec_data.get("category"),
# # # #                 "recommendations": rec_data["recommendations"],
# # # #                 "generated_at": rec_data["generated_at"],
# # # #                 "processing_time_ms": rec_data.get("processing_time_ms"),
# # # #                 "view_count": current_views + 1,
# # # #                 "search_context": rec_data.get("search_context", [])
# # # #             },
# # # #             "feedback": feedback_list,
# # # #             "user_id": current_user
# # # #         }
        
# # # #     except Exception as e:
# # # #         raise HTTPException(
# # # #             status_code=500,
# # # #             detail=f"Failed to get recommendation details: {str(e)}"
# # # #         )


# # # # app/routers/recommendations.py - Enhanced with profile validation and data integrity

# # # from fastapi import APIRouter, Depends, HTTPException, status, Query
# # # from pydantic import BaseModel
# # # from typing import Dict, Any, List, Optional
# # # import json
# # # from openai import OpenAI
# # # from duckduckgo_search import DDGS 
# # # from duckduckgo_search.exceptions import DuckDuckGoSearchException
# # # from itertools import islice
# # # import time
# # # import uuid
# # # from datetime import datetime, timedelta

# # # from app.core.security import get_current_user
# # # from app.core.firebase import get_firestore_client
# # # from app.core.config import get_settings
# # # from app.routers.conversations import save_conversation_message

# # # router = APIRouter()

# # # # Enhanced Pydantic models
# # # class RecommendationRequest(BaseModel):
# # #     query: str
# # #     category: Optional[str] = None
# # #     user_id: Optional[str] = None
# # #     context: Optional[Dict[str, Any]] = None

# # # class RecommendationItem(BaseModel):
# # #     title: str
# # #     description: Optional[str] = None
# # #     reasons: List[str] = []
# # #     category: Optional[str] = None
# # #     confidence_score: Optional[float] = None
# # #     external_links: Optional[List[str]] = None

# # # class RecommendationResponse(BaseModel):
# # #     recommendation_id: str
# # #     recommendations: List[RecommendationItem]
# # #     query: str
# # #     category: Optional[str] = None
# # #     user_id: str
# # #     generated_at: datetime
# # #     processing_time_ms: Optional[int] = None

# # # class RecommendationFeedback(BaseModel):
# # #     recommendation_id: str
# # #     feedback_type: str  # 'like', 'dislike', 'not_relevant', 'helpful'
# # #     rating: Optional[int] = None  # 1-5 stars
# # #     comment: Optional[str] = None
# # #     clicked_items: List[str] = []

# # # # Database helper functions
# # # def save_recommendation_to_db(recommendation_data: Dict[str, Any], db) -> str:
# # #     """Save recommendation to database and return recommendation_id"""
# # #     try:
# # #         recommendation_id = str(uuid.uuid4())
        
# # #         # Prepare data for database
# # #         db_data = {
# # #             "recommendation_id": recommendation_id,
# # #             "user_id": recommendation_data["user_id"],
# # #             "query": recommendation_data["query"],
# # #             "category": recommendation_data.get("category"),
# # #             "recommendations": recommendation_data["recommendations"],
# # #             "generated_at": datetime.utcnow(),
# # #             "processing_time_ms": recommendation_data.get("processing_time_ms"),
# # #             "search_context": recommendation_data.get("search_context", []),
# # #             "profile_version": recommendation_data.get("profile_version"),
# # #             "session_id": recommendation_data.get("session_id"),
# # #             "is_active": True,
# # #             "view_count": 0,
# # #             "feedback_count": 0
# # #         }
        
# # #         # Save to user-specific collection
# # #         db.collection("user_recommendations").document(recommendation_data["user_id"]).collection("recommendations").document(recommendation_id).set(db_data)
        
# # #         # Also save to recommendation history for analytics
# # #         history_data = {
# # #             "recommendation_id": recommendation_id,
# # #             "user_id": recommendation_data["user_id"],
# # #             "query": recommendation_data["query"],
# # #             "category": recommendation_data.get("category"),
# # #             "recommendations_count": len(recommendation_data["recommendations"]),
# # #             "created_at": datetime.utcnow(),
# # #             "is_bookmarked": False,
# # #             "tags": []
# # #         }
        
# # #         db.collection("recommendation_history").document(recommendation_id).set(history_data)
        
# # #         return recommendation_id
        
# # #     except Exception as e:
# # #         print(f"Error saving recommendation: {e}")
# # #         return None

# # # def get_user_recommendation_history(user_id: str, db, limit: int = 20, offset: int = 0, category: str = None):
# # #     """Get user's recommendation history from database"""
# # #     try:
# # #         query = db.collection("user_recommendations").document(user_id).collection("recommendations").where("is_active", "==", True)
        
# # #         if category:
# # #             query = query.where("category", "==", category)
        
# # #         recommendations = query.order_by("generated_at", direction="DESCENDING").limit(limit).offset(offset).stream()
        
# # #         history = []
# # #         for rec in recommendations:
# # #             rec_data = rec.to_dict()
# # #             history.append({
# # #                 "recommendation_id": rec_data["recommendation_id"],
# # #                 "query": rec_data["query"],
# # #                 "category": rec_data.get("category"),
# # #                 "recommendations_count": len(rec_data.get("recommendations", [])),
# # #                 "generated_at": rec_data["generated_at"],
# # #                 "view_count": rec_data.get("view_count", 0),
# # #                 "feedback_count": rec_data.get("feedback_count", 0),
# # #                 "session_id": rec_data.get("session_id")
# # #             })
        
# # #         return history
        
# # #     except Exception as e:
# # #         print(f"Error getting recommendation history: {e}")
# # #         return []

# # # def save_recommendation_feedback(recommendation_id: str, user_id: str, feedback_data: Dict[str, Any], db):
# # #     """Save user feedback for a recommendation"""
# # #     try:
# # #         feedback_id = str(uuid.uuid4())
        
# # #         feedback_doc = {
# # #             "feedback_id": feedback_id,
# # #             "recommendation_id": recommendation_id,
# # #             "user_id": user_id,
# # #             "feedback_type": feedback_data["feedback_type"],
# # #             "rating": feedback_data.get("rating"),
# # #             "comment": feedback_data.get("comment"),
# # #             "clicked_items": feedback_data.get("clicked_items", []),
# # #             "created_at": datetime.utcnow()
# # #         }
        
# # #         # Save feedback
# # #         db.collection("recommendation_feedback").document(feedback_id).set(feedback_doc)
        
# # #         # Update recommendation with feedback count
# # #         rec_ref = db.collection("user_recommendations").document(user_id).collection("recommendations").document(recommendation_id)
# # #         rec_doc = rec_ref.get()
        
# # #         if rec_doc.exists:
# # #             current_feedback_count = rec_doc.to_dict().get("feedback_count", 0)
# # #             rec_ref.update({"feedback_count": current_feedback_count + 1})
        
# # #         return feedback_id
        
# # #     except Exception as e:
# # #         print(f"Error saving feedback: {e}")
# # #         return None

# # # # ENHANCED Profile validation and loading functions
# # # def validate_profile_authenticity(profile_data: Dict[str, Any], user_id: str, db) -> Dict[str, Any]:
# # #     """Enhanced validation that strictly detects template data and unauthenticated responses"""
    
# # #     if not profile_data or not user_id:
# # #         return {"valid": False, "reason": "empty_profile_or_user"}
    
# # #     validation_result = {
# # #         "valid": True,
# # #         "warnings": [],
# # #         "user_id": user_id,
# # #         "profile_sections": {},
# # #         "authenticity_score": 0.0,
# # #         "template_indicators": []
# # #     }
    
# # #     try:
# # #         # Check interview completion status for this user
# # #         interview_sessions = db.collection("interview_sessions").where("user_id", "==", user_id).stream()
        
# # #         completed_phases = set()
# # #         in_progress_phases = set()
# # #         session_data = {}
# # #         total_questions_answered = 0
        
# # #         for session in interview_sessions:
# # #             session_dict = session.to_dict()
# # #             session_data[session.id] = session_dict
            
# # #             phase = session_dict.get("current_phase", "unknown")
            
# # #             if session_dict.get("status") == "completed":
# # #                 completed_phases.add(phase)
# # #                 total_questions_answered += session_dict.get("questions_answered", 0)
# # #             elif session_dict.get("status") == "in_progress":
# # #                 in_progress_phases.add(phase)
        
# # #         validation_result["completed_phases"] = list(completed_phases)
# # #         validation_result["in_progress_phases"] = list(in_progress_phases)
# # #         validation_result["total_questions_answered"] = total_questions_answered
# # #         validation_result["session_data"] = session_data
        
# # #         # Analyze profile sections
# # #         profile_sections = profile_data.get("recommendationProfiles", {})
# # #         general_profile = profile_data.get("generalprofile", {})
        
# # #         # Check recommendation profiles
# # #         total_detailed_responses = 0
# # #         total_authenticated_responses = 0
# # #         template_indicators = []
        
# # #         for section_name, section_data in profile_sections.items():
# # #             section_validation = {
# # #                 "has_data": bool(section_data),
# # #                 "interview_completed": section_name in completed_phases,
# # #                 "data_authenticity": "unknown",
# # #                 "detailed_response_count": 0,
# # #                 "authenticated_response_count": 0,
# # #                 "template_indicators": []
# # #             }
            
# # #             if section_data and isinstance(section_data, dict):
# # #                 def analyze_responses(data, path=""):
# # #                     nonlocal total_detailed_responses, total_authenticated_responses
                    
# # #                     if isinstance(data, dict):
# # #                         for key, value in data.items():
# # #                             current_path = f"{path}.{key}" if path else key
                            
# # #                             if isinstance(value, dict):
# # #                                 # Check if this is a response object with detailed content
# # #                                 if "value" in value and isinstance(value["value"], str) and len(value["value"].strip()) > 10:
# # #                                     section_validation["detailed_response_count"] += 1
# # #                                     total_detailed_responses += 1
                                    
# # #                                     # Check for authentication markers (user_id + updated_at)
# # #                                     if "user_id" in value and "updated_at" in value:
# # #                                         if value.get("user_id") == user_id:
# # #                                             section_validation["authenticated_response_count"] += 1
# # #                                             total_authenticated_responses += 1
# # #                                         else:
# # #                                             section_validation["template_indicators"].append(
# # #                                                 f"Foreign user_id in {current_path}: {value.get('user_id')}"
# # #                                             )
# # #                                             template_indicators.append(
# # #                                                 f"Foreign user data: {section_name}.{current_path}"
# # #                                             )
# # #                                     else:
# # #                                         # No authentication markers - this is template data
# # #                                         section_validation["template_indicators"].append(
# # #                                             f"No auth markers in {current_path} (detailed response without user_id/timestamp)"
# # #                                         )
# # #                                         template_indicators.append(
# # #                                             f"Unauthenticated detailed response: {section_name}.{current_path}"
# # #                                         )
                                
# # #                                 # Recursively check nested structures
# # #                                 analyze_responses(value, current_path)
                
# # #                 analyze_responses(section_data)
                
# # #                 # Determine authenticity for this section
# # #                 if section_validation["template_indicators"]:
# # #                     if section_validation["authenticated_response_count"] == 0:
# # #                         section_validation["data_authenticity"] = "template_data"
# # #                     else:
# # #                         section_validation["data_authenticity"] = "mixed_data"
# # #                 elif section_validation["detailed_response_count"] > 0:
# # #                     if section_validation["interview_completed"]:
# # #                         section_validation["data_authenticity"] = "authentic"
# # #                     else:
# # #                         section_validation["data_authenticity"] = "suspicious_no_interview"
# # #                         section_validation["template_indicators"].append(
# # #                             f"Detailed data without completed interview"
# # #                         )
# # #                         template_indicators.append(
# # #                             f"No interview completion: {section_name}"
# # #                         )
# # #                 else:
# # #                     section_validation["data_authenticity"] = "minimal_data"
            
# # #             validation_result["profile_sections"][section_name] = section_validation
        
# # #         # Check general profile for template indicators
# # #         general_template_indicators = []
# # #         general_detailed_responses = 0
        
# # #         def check_general_profile(data, path="generalprofile"):
# # #             nonlocal general_detailed_responses, general_template_indicators
            
# # #             if isinstance(data, dict):
# # #                 for key, value in data.items():
# # #                     current_path = f"{path}.{key}"
                    
# # #                     if isinstance(value, dict):
# # #                         if "value" in value and isinstance(value["value"], str) and len(value["value"].strip()) > 10:
# # #                             general_detailed_responses += 1
# # #                             # Check for authentication in general profile
# # #                             if "user_id" not in value or "updated_at" not in value:
# # #                                 general_template_indicators.append(
# # #                                     f"No auth markers in {current_path}"
# # #                                 )
# # #                         else:
# # #                             check_general_profile(value, current_path)
        
# # #         check_general_profile(general_profile)
        
# # #         # Calculate authenticity score
# # #         total_responses_with_general = total_detailed_responses + general_detailed_responses
# # #         if total_responses_with_general > 0:
# # #             auth_ratio = total_authenticated_responses / total_responses_with_general
# # #             interview_ratio = len(completed_phases) / max(len(profile_sections), 1)
# # #             question_ratio = min(total_questions_answered / max(total_responses_with_general, 1), 1.0)
            
# # #             validation_result["authenticity_score"] = (auth_ratio * 0.5 + interview_ratio * 0.3 + question_ratio * 0.2)
# # #         else:
# # #             validation_result["authenticity_score"] = 1.0  # No data to validate
        
# # #         validation_result["template_indicators"] = template_indicators + general_template_indicators
# # #         validation_result["total_detailed_responses"] = total_responses_with_general
# # #         validation_result["total_authenticated_responses"] = total_authenticated_responses
        
# # #         # STRICT validation logic - this will catch template data
# # #         if len(template_indicators + general_template_indicators) > 0:
# # #             validation_result["valid"] = False
# # #             validation_result["reason"] = "template_data_detected"
# # #         elif validation_result["authenticity_score"] < 0.3:  # Lowered threshold
# # #             validation_result["valid"] = False
# # #             validation_result["reason"] = "low_authenticity_score"
# # #         elif total_responses_with_general > 5 and len(completed_phases) == 0:
# # #             # If there are many detailed responses but no completed interviews
# # #             validation_result["valid"] = False
# # #             validation_result["reason"] = "extensive_data_without_interviews"
# # #         elif total_responses_with_general > 0 and total_authenticated_responses == 0:
# # #             # If there are responses but none are authenticated
# # #             validation_result["valid"] = False
# # #             validation_result["reason"] = "no_authenticated_responses"
        
# # #         # Add detailed diagnostics
# # #         validation_result["diagnostics"] = {
# # #             "has_extensive_data": total_responses_with_general > 10,
# # #             "has_completed_interviews": len(completed_phases) > 0,
# # #             "data_to_interview_ratio": total_responses_with_general / max(len(completed_phases), 1),
# # #             "authentication_percentage": (total_authenticated_responses / max(total_responses_with_general, 1)) * 100,
# # #             "profile_creation_pattern": "template_based" if total_responses_with_general > 0 and total_authenticated_responses == 0 else "interview_based"
# # #         }
        
# # #         return validation_result
        
# # #     except Exception as e:
# # #         return {
# # #             "valid": False, 
# # #             "reason": "validation_error", 
# # #             "error": str(e)
# # #         }

# # # def load_user_profile(user_id: str = None) -> Dict[str, Any]:
# # #     """Load and validate USER-SPECIFIC profile from Firestore"""
# # #     try:
# # #         db = get_firestore_client()
        
# # #         if not user_id:
# # #             print("❌ No user_id provided for profile loading")
# # #             return {}
        
# # #         print(f"🔍 Looking for profile for user: {user_id}")
        
# # #         # Try to find profile in multiple locations
# # #         profile_locations = [
# # #             {
# # #                 "collection": "user_profiles",
# # #                 "document": f"{user_id}_profile_structure.json",
# # #                 "description": "Primary user_profiles collection"
# # #             },
# # #             {
# # #                 "collection": "user_collection", 
# # #                 "document": f"{user_id}_profile_structure.json",
# # #                 "description": "Fallback user_collection with user prefix"
# # #             },
# # #             {
# # #                 "collection": "interview_profiles",
# # #                 "document": f"{user_id}_profile.json", 
# # #                 "description": "Interview-generated profile"
# # #             },
# # #             {
# # #                 "collection": f"user_{user_id}",
# # #                 "document": "profile_structure.json",
# # #                 "description": "User-specific collection"
# # #             }
# # #         ]
        
# # #         raw_profile = None
# # #         profile_source = None
        
# # #         for location in profile_locations:
# # #             try:
# # #                 doc_ref = db.collection(location["collection"]).document(location["document"])
# # #                 doc = doc_ref.get()
                
# # #                 if doc.exists:
# # #                     raw_profile = doc.to_dict()
# # #                     profile_source = f"{location['collection']}/{location['document']}"
# # #                     print(f"✅ Found profile at: {profile_source}")
# # #                     break
                    
# # #             except Exception as e:
# # #                 print(f"❌ Error checking {location['description']}: {e}")
# # #                 continue
        
# # #         if not raw_profile:
# # #             print(f"❌ No profile found for user: {user_id}")
# # #             return {}
        
# # #         # Validate profile authenticity with enhanced validation
# # #         validation = validate_profile_authenticity(raw_profile, user_id, db)
        
# # #         print(f"🔍 Profile validation result: {validation.get('valid')} - {validation.get('reason', 'OK')}")
# # #         print(f"🔍 Authenticity score: {validation.get('authenticity_score', 0.0):.2f}")
# # #         print(f"🔍 Total responses: {validation.get('total_detailed_responses', 0)}")
# # #         print(f"🔍 Authenticated responses: {validation.get('total_authenticated_responses', 0)}")
        
# # #         if validation.get("warnings"):
# # #             print(f"⚠️ Profile warnings: {validation['warnings']}")
        
# # #         if not validation.get("valid"):
# # #             print(f"🚨 INVALID PROFILE for user {user_id}: {validation.get('reason')}")
            
# # #             if validation.get("template_indicators"):
# # #                 print(f"🚨 Template indicators: {validation['template_indicators'][:3]}...")  # Show first 3
            
# # #             # Return error profile for any validation failure
# # #             return {
# # #                 "error": "contaminated_profile",
# # #                 "user_id": user_id,
# # #                 "validation": validation,
# # #                 "message": f"Profile validation failed: {validation.get('reason')}",
# # #                 "profile_source": profile_source
# # #             }
        
# # #         # If validation passed, return profile with validation info
# # #         profile_with_metadata = raw_profile.copy()
# # #         profile_with_metadata["_validation"] = validation
# # #         profile_with_metadata["_source"] = profile_source
        
# # #         return profile_with_metadata
        
# # #     except Exception as e:
# # #         print(f"❌ Error loading user profile for {user_id}: {e}")
# # #         return {}

# # # def search_web(query, max_results=3, max_retries=3, base_delay=1.0):
# # #     """Query DuckDuckGo via DDGS.text(), returning up to max_results items."""
# # #     for attempt in range(1, max_retries + 1):
# # #         try:
# # #             with DDGS() as ddgs:
# # #                 return list(islice(ddgs.text(query), max_results))
# # #         except DuckDuckGoSearchException as e:
# # #             msg = str(e)
# # #             if "202" in msg:
# # #                 wait = base_delay * (2 ** (attempt - 1))
# # #                 print(f"[search_web] Rate‑limited (202). Retry {attempt}/{max_retries} in {wait:.1f}s…")
# # #                 time.sleep(wait)
# # #             else:
# # #                 raise
# # #         except Exception as e:
# # #             print(f"[search_web] Unexpected error: {e}")
# # #             break
    
# # #     print(f"[search_web] Failed to fetch results after {max_retries} attempts.")
# # #     return []

# # # def generate_recommendations(user_profile, user_query, openai_key):
# # #     """Generate 3 personalized recommendations using user profile and web search"""
# # #     # Getting current web context
# # #     search_results = search_web(f"{user_query} recommendations 2024")
    
# # #     prompt = f"""
# # #     **Task**: Generate exactly 3 highly personalized recommendations based on:
    
# # #     **User Profile**:
# # #     {json.dumps(user_profile, indent=2)}
    
# # #     **User Query**:
# # #     "{user_query}"
    
# # #     **Web Context** (for reference only):
# # #     {search_results}
    
# # #     **Requirements**:
# # #     1. Each recommendation must directly reference profile details
# # #     2. Blend the user's core values and preferences
# # #     3. Only suggest what is asked for suggest no extra advices.
# # #     4. Format as JSON array with each recommendation having:
# # #        - title: string
# # #        - description: string (brief description)
# # #        - reasons: array of strings (why it matches the user profile)
# # #        - confidence_score: float (0.0-1.0)
    
# # #     **Output Example**:
# # #     [
# # #       {{
# # #          "title": "Creative Project Tool",
# # #          "description": "Notion's creative templates for content planning",
# # #          "reasons": ["Matches your love for storytelling and freelance work", "Supports your creative workflow"],
# # #          "confidence_score": 0.9
# # #       }},
# # #       {{
# # #          "title": "Historical Drama Series",
# # #          "description": "Epic series focusing on leadership and personal struggles",
# # #          "reasons": ["Resonates with your interest in historical figures", "Explores themes of resilience you value"],
# # #          "confidence_score": 0.85
# # #       }},
# # #       {{
# # #          "title": "Motivational Biopic",
# # #          "description": "Inspiring story of overcoming personal difficulties",
# # #          "reasons": ["Highlights overcoming personal difficulties", "Aligns with your experiences of resilience"],
# # #          "confidence_score": 0.8
# # #       }}
# # #     ]
    
# # #     Generate your response in JSON format only.
# # #     """
    
# # #     # Setting up LLM
# # #     client = OpenAI(api_key=openai_key)

# # #     response = client.chat.completions.create(
# # #         model="gpt-4",
# # #         messages=[
# # #             {"role": "system", "content": "You're a recommendation engine that creates hyper-personalized suggestions. Output valid JSON only."},
# # #             {"role": "user", "content": prompt}
# # #         ],
# # #         temperature=0.7  
# # #     )
    
# # #     return response.choices[0].message.content

# # # # ROUTE DEFINITIONS - SPECIFIC ROUTES FIRST, PARAMETERIZED ROUTES LAST

# # # @router.get("/profile")
# # # async def get_user_profile(current_user: str = Depends(get_current_user)):
# # #     """Get the current user's SPECIFIC profile with enhanced validation"""
# # #     try:
# # #         print(f"🔍 Getting profile for user: {current_user}")
# # #         profile = load_user_profile(current_user)
        
# # #         # Handle contaminated profile
# # #         if isinstance(profile, dict) and profile.get("error") == "contaminated_profile":
# # #             validation_info = profile.get("validation", {})
            
# # #             raise HTTPException(
# # #                 status_code=422,
# # #                 detail={
# # #                     "error": "contaminated_profile",
# # #                     "message": "Profile contains template data and needs regeneration",
# # #                     "user_id": current_user,
# # #                     "validation": {
# # #                         "reason": validation_info.get("reason"),
# # #                         "authenticity_score": validation_info.get("authenticity_score", 0.0),
# # #                         "total_detailed_responses": validation_info.get("total_detailed_responses", 0),
# # #                         "total_authenticated_responses": validation_info.get("total_authenticated_responses", 0),
# # #                         "completed_phases": validation_info.get("completed_phases", []),
# # #                         "in_progress_phases": validation_info.get("in_progress_phases", []),
# # #                         "template_indicators": validation_info.get("template_indicators", [])[:5],  # First 5
# # #                         "diagnostics": validation_info.get("diagnostics", {})
# # #                     },
# # #                     "recommended_action": "complete_interview_to_generate_authentic_profile",
# # #                     "profile_source": profile.get("profile_source")
# # #                 }
# # #             )
        
# # #         if not profile:
# # #             # Check interview status
# # #             db = get_firestore_client()
# # #             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
# # #             sessions = list(sessions_ref.stream())
            
# # #             if not sessions:
# # #                 raise HTTPException(
# # #                     status_code=404,
# # #                     detail="No profile or interview sessions found. Please start an interview."
# # #                 )
            
# # #             # Check if any sessions are completed
# # #             completed_sessions = [s for s in sessions if s.to_dict().get("status") == "completed"]
# # #             in_progress_sessions = [s for s in sessions if s.to_dict().get("status") == "in_progress"]
            
# # #             if completed_sessions:
# # #                 raise HTTPException(
# # #                     status_code=404,
# # #                     detail="Interview completed but profile not generated. Please contact support."
# # #                 )
# # #             elif in_progress_sessions:
# # #                 session_details = []
# # #                 for session in in_progress_sessions:
# # #                     session_data = session.to_dict()
# # #                     session_details.append({
# # #                         "session_id": session.id,
# # #                         "phase": session_data.get("current_phase"),
# # #                         "tier": session_data.get("current_tier")
# # #                     })
                
# # #                 raise HTTPException(
# # #                     status_code=404,
# # #                     detail={
# # #                         "message": "Interview in progress. Complete the interview to generate your profile.",
# # #                         "in_progress_sessions": session_details
# # #                     }
# # #                 )
# # #             else:
# # #                 raise HTTPException(
# # #                     status_code=404,
# # #                     detail="No completed interviews found. Please complete an interview first."
# # #                 )
        
# # #         # Remove internal validation metadata before returning
# # #         clean_profile = {k: v for k, v in profile.items() if not k.startswith('_')}
# # #         validation_summary = profile.get("_validation", {})
        
# # #         # Enhanced response with detailed validation
# # #         response = {
# # #             "success": True,
# # #             "profile": clean_profile,
# # #             "user_id": current_user,
# # #             "profile_type": "user_specific",
# # #             "profile_found": True,
# # #             "validation_summary": {
# # #                 "valid": validation_summary.get("valid", True),
# # #                 "authenticity_score": validation_summary.get("authenticity_score", 1.0),
# # #                 "reason": validation_summary.get("reason"),
# # #                 "warnings": validation_summary.get("warnings", []),
# # #                 "completed_phases": validation_summary.get("completed_phases", []),
# # #                 "in_progress_phases": validation_summary.get("in_progress_phases", []),
# # #                 "template_indicators": validation_summary.get("template_indicators", [])[:3],  # First 3
# # #                 "total_detailed_responses": validation_summary.get("total_detailed_responses", 0),
# # #                 "total_authenticated_responses": validation_summary.get("total_authenticated_responses", 0),
# # #                 "diagnostics": validation_summary.get("diagnostics", {})
# # #             },
# # #             "profile_source": profile.get("_source", "unknown")
# # #         }
        
# # #         # Add warning if profile seems templated
# # #         if validation_summary.get("template_indicators") or validation_summary.get("authenticity_score", 1.0) < 0.5:
# # #             response["warning"] = "Profile may contain template data. Complete an interview for authentic personalization."
        
# # #         return response
        
# # #     except HTTPException:
# # #         raise
# # #     except Exception as e:
# # #         print(f"❌ Error in get_user_profile: {e}")
# # #         raise HTTPException(
# # #             status_code=500,
# # #             detail=f"Failed to load profile: {str(e)}"
# # #         )

# # # @router.get("/categories")
# # # async def get_recommendation_categories():
# # #     """Get available recommendation categories"""
# # #     categories = [
# # #         {
# # #             "id": "movies",
# # #             "name": "Movies & TV",
# # #             "description": "Movie and TV show recommendations",
# # #             "questions_file": "moviesAndTV_tiered_questions.json"
# # #         },
# # #         {
# # #             "id": "food",
# # #             "name": "Food & Dining",
# # #             "description": "Restaurant and food recommendations",
# # #             "questions_file": "foodAndDining_tiered_questions.json"
# # #         },
# # #         {
# # #             "id": "travel",
# # #             "name": "Travel",
# # #             "description": "Travel destination recommendations",
# # #             "questions_file": "travel_tiered_questions.json"
# # #         },
# # #         {
# # #             "id": "books",
# # #             "name": "Books & Reading",
# # #             "description": "Book recommendations",
# # #             "questions_file": "books_tiered_questions.json"
# # #         },
# # #         {
# # #             "id": "music",
# # #             "name": "Music",
# # #             "description": "Music and artist recommendations",
# # #             "questions_file": "music_tiered_questions.json"
# # #         },
# # #         {
# # #             "id": "fitness",
# # #             "name": "Fitness & Wellness",
# # #             "description": "Fitness and wellness recommendations",
# # #             "questions_file": "fitness_tiered_questions.json"
# # #         }
# # #     ]
    
# # #     return {
# # #         "categories": categories,
# # #         "default_category": "movies"
# # #     }

# # # @router.get("/history")
# # # async def get_recommendation_history(
# # #     current_user: str = Depends(get_current_user),
# # #     limit: int = Query(20, description="Number of recommendations to return"),
# # #     offset: int = Query(0, description="Number of recommendations to skip"),
# # #     category: Optional[str] = Query(None, description="Filter by category"),
# # #     date_from: Optional[datetime] = Query(None, description="Filter from date"),
# # #     date_to: Optional[datetime] = Query(None, description="Filter to date")
# # # ):
# # #     """Get recommendation history for the user with enhanced filtering"""
# # #     try:
# # #         db = get_firestore_client()
        
# # #         # Simplified query to avoid index issues - just get user's recommendations
# # #         query = db.collection("user_recommendations").document(current_user).collection("recommendations")
# # #         query = query.where("is_active", "==", True)
# # #         query = query.limit(limit).offset(offset)
        
# # #         # Get all recommendations (without complex ordering initially)
# # #         recommendations = list(query.stream())
        
# # #         # Filter and sort in Python instead of Firestore
# # #         filtered_recs = []
# # #         for rec in recommendations:
# # #             rec_data = rec.to_dict()
            
# # #             # Apply category filter
# # #             if category and rec_data.get("category") != category:
# # #                 continue
            
# # #             # Apply date filters
# # #             rec_date = rec_data.get("generated_at")
# # #             if date_from and rec_date and rec_date < date_from:
# # #                 continue
# # #             if date_to and rec_date and rec_date > date_to:
# # #                 continue
            
# # #             filtered_recs.append(rec_data)
        
# # #         # Sort by generated_at descending
# # #         filtered_recs.sort(key=lambda x: x.get("generated_at", datetime.min), reverse=True)
        
# # #         # Format response
# # #         history = []
# # #         for rec_data in filtered_recs:
# # #             history.append({
# # #                 "recommendation_id": rec_data["recommendation_id"],
# # #                 "query": rec_data["query"],
# # #                 "category": rec_data.get("category"),
# # #                 "recommendations_count": len(rec_data.get("recommendations", [])),
# # #                 "generated_at": rec_data["generated_at"],
# # #                 "view_count": rec_data.get("view_count", 0),
# # #                 "feedback_count": rec_data.get("feedback_count", 0),
# # #                 "session_id": rec_data.get("session_id"),
# # #                 "processing_time_ms": rec_data.get("processing_time_ms")
# # #             })
        
# # #         return {
# # #             "success": True,
# # #             "history": history,
# # #             "total_count": len(history),
# # #             "user_id": current_user,
# # #             "filters": {
# # #                 "category": category,
# # #                 "date_from": date_from,
# # #                 "date_to": date_to,
# # #                 "limit": limit,
# # #                 "offset": offset
# # #             },
# # #             "note": "Using simplified query to avoid Firebase index requirements"
# # #         }
        
# # #     except Exception as e:
# # #         raise HTTPException(
# # #             status_code=500,
# # #             detail=f"Failed to get recommendation history: {str(e)}"
# # #         )

# # # @router.get("/analytics/summary")
# # # async def get_recommendation_analytics(
# # #     current_user: str = Depends(get_current_user),
# # #     days: int = Query(30, description="Number of days to analyze")
# # # ):
# # #     """Get recommendation analytics for the user"""
# # #     try:
# # #         db = get_firestore_client()
        
# # #         # Calculate date range
# # #         end_date = datetime.utcnow()
# # #         start_date = end_date - timedelta(days=days)
        
# # #         # Get recommendations - simplified query
# # #         recommendations_ref = db.collection("user_recommendations").document(current_user).collection("recommendations")
# # #         recommendations = recommendations_ref.where("is_active", "==", True).stream()
        
# # #         analytics = {
# # #             "total_recommendations": 0,
# # #             "categories_explored": set(),
# # #             "query_types": {},
# # #             "total_views": 0,
# # #             "total_feedback": 0,
# # #             "average_processing_time": 0,
# # #             "recommendations_by_day": {},
# # #             "most_popular_category": None,
# # #             "engagement_rate": 0
# # #         }
        
# # #         processing_times = []
# # #         daily_counts = {}
# # #         category_counts = {}
        
# # #         for rec in recommendations:
# # #             rec_data = rec.to_dict()
            
# # #             # Filter by date range
# # #             rec_date = rec_data.get("generated_at")
# # #             if rec_date and rec_date < start_date:
# # #                 continue
                
# # #             analytics["total_recommendations"] += 1
            
# # #             # Track categories
# # #             category = rec_data.get("category", "general")
# # #             analytics["categories_explored"].add(category)
# # #             category_counts[category] = category_counts.get(category, 0) + 1
            
# # #             # Track views and feedback
# # #             analytics["total_views"] += rec_data.get("view_count", 0)
# # #             analytics["total_feedback"] += rec_data.get("feedback_count", 0)
            
# # #             # Track processing times
# # #             if rec_data.get("processing_time_ms"):
# # #                 processing_times.append(rec_data["processing_time_ms"])
            
# # #             # Track daily activity
# # #             if rec_date:
# # #                 if hasattr(rec_date, 'date'):
# # #                     date_str = rec_date.date().isoformat()
# # #                 else:
# # #                     date_str = datetime.fromisoformat(str(rec_date)).date().isoformat()
                
# # #                 daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
        
# # #         # Calculate averages and insights
# # #         if analytics["total_recommendations"] > 0:
# # #             analytics["engagement_rate"] = round((analytics["total_views"] / analytics["total_recommendations"]) * 100, 2)
        
# # #         if processing_times:
# # #             analytics["average_processing_time"] = round(sum(processing_times) / len(processing_times), 2)
        
# # #         if category_counts:
# # #             analytics["most_popular_category"] = max(category_counts, key=category_counts.get)
        
# # #         analytics["categories_explored"] = list(analytics["categories_explored"])
# # #         analytics["recommendations_by_day"] = daily_counts
# # #         analytics["category_breakdown"] = category_counts
        
# # #         return {
# # #             "success": True,
# # #             "analytics": analytics,
# # #             "period": {
# # #                 "start_date": start_date.isoformat(),
# # #                 "end_date": end_date.isoformat(),
# # #                 "days": days
# # #             },
# # #             "user_id": current_user
# # #         }
        
# # #     except Exception as e:
# # #         raise HTTPException(
# # #             status_code=500,
# # #             detail=f"Failed to get recommendation analytics: {str(e)}"
# # #         )

# # # @router.get("/debug/profile-location")
# # # async def debug_profile_location(current_user: str = Depends(get_current_user)):
# # #     """Debug endpoint to check where user profile is stored and validate it"""
# # #     try:
# # #         db = get_firestore_client()
        
# # #         locations_checked = {
# # #             "user_profiles": False,
# # #             "user_collection": False,
# # #             "interview_profiles": False,
# # #             "user_specific_collection": False,
# # #             "fallback_locations": {}
# # #         }
        
# # #         profile_sources = []
        
# # #         # Check primary location
# # #         profile_doc_id = f"{current_user}_profile_structure.json"
        
# # #         # Check user_profiles collection
# # #         try:
# # #             profile_doc = db.collection("user_profiles").document(profile_doc_id).get()
# # #             locations_checked["user_profiles"] = profile_doc.exists
# # #             if profile_doc.exists:
# # #                 profile_sources.append({
# # #                     "location": f"user_profiles/{profile_doc_id}",
# # #                     "data_preview": str(profile_doc.to_dict())[:200] + "..."
# # #                 })
# # #         except Exception as e:
# # #             locations_checked["user_profiles"] = f"Error: {e}"
        
# # #         # Check user_collection fallback
# # #         try:
# # #             fallback_doc = db.collection("user_collection").document(profile_doc_id).get()
# # #             locations_checked["user_collection"] = fallback_doc.exists
# # #             if fallback_doc.exists:
# # #                 profile_sources.append({
# # #                     "location": f"user_collection/{profile_doc_id}",
# # #                     "data_preview": str(fallback_doc.to_dict())[:200] + "..."
# # #                 })
# # #         except Exception as e:
# # #             locations_checked["user_collection"] = f"Error: {e}"
        
# # #         # Check interview_profiles
# # #         try:
# # #             interview_doc = db.collection("interview_profiles").document(f"{current_user}_profile.json").get()
# # #             locations_checked["interview_profiles"] = interview_doc.exists
# # #             if interview_doc.exists:
# # #                 profile_sources.append({
# # #                     "location": f"interview_profiles/{current_user}_profile.json",
# # #                     "data_preview": str(interview_doc.to_dict())[:200] + "..."
# # #                 })
# # #         except Exception as e:
# # #             locations_checked["interview_profiles"] = f"Error: {e}"
        
# # #         # Check user-specific collection
# # #         try:
# # #             user_specific_doc = db.collection(f"user_{current_user}").document("profile_structure.json").get()
# # #             locations_checked["user_specific_collection"] = user_specific_doc.exists
# # #             if user_specific_doc.exists:
# # #                 profile_sources.append({
# # #                     "location": f"user_{current_user}/profile_structure.json",
# # #                     "data_preview": str(user_specific_doc.to_dict())[:200] + "..."
# # #                 })
# # #         except Exception as e:
# # #             locations_checked["user_specific_collection"] = f"Error: {e}"
        
# # #         # Check other possible locations
# # #         possible_docs = [
# # #             ("user_collection", "profile_strcuture.json"),  # Original typo
# # #             ("user_collection", "profile_structure.json"),
# # #             ("user_collection", f"{current_user}_profile.json"),
# # #             ("profiles", f"{current_user}.json"),
# # #             ("user_data", f"{current_user}_profile.json")
# # #         ]
        
# # #         for collection_name, doc_name in possible_docs:
# # #             try:
# # #                 doc_exists = db.collection(collection_name).document(doc_name).get().exists
# # #                 locations_checked["fallback_locations"][f"{collection_name}/{doc_name}"] = doc_exists
# # #                 if doc_exists:
# # #                     profile_sources.append({
# # #                         "location": f"{collection_name}/{doc_name}",
# # #                         "data_preview": "Found but not retrieved"
# # #                     })
# # #             except Exception as e:
# # #                 locations_checked["fallback_locations"][f"{collection_name}/{doc_name}"] = f"Error: {e}"
        
# # #         # Get interview session info
# # #         interview_sessions = []
# # #         try:
# # #             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
# # #             for session in sessions_ref.stream():
# # #                 session_data = session.to_dict()
# # #                 interview_sessions.append({
# # #                     "session_id": session.id,
# # #                     "status": session_data.get("status"),
# # #                     "phase": session_data.get("current_phase"),
# # #                     "tier": session_data.get("current_tier"),
# # #                     "created_at": session_data.get("created_at"),
# # #                     "updated_at": session_data.get("updated_at")
# # #                 })
# # #         except Exception as e:
# # #             interview_sessions = [{"error": str(e)}]
        
# # #         # Test the current profile loading function
# # #         test_profile = load_user_profile(current_user)
# # #         profile_validation = None
        
# # #         if test_profile:
# # #             if test_profile.get("error"):
# # #                 profile_validation = {
# # #                     "status": "error",
# # #                     "error_type": test_profile.get("error"),
# # #                     "validation_details": test_profile.get("validation", {})
# # #                 }
# # #             else:
# # #                 profile_validation = {
# # #                     "status": "loaded",
# # #                     "validation_summary": test_profile.get("_validation", {}),
# # #                     "source": test_profile.get("_source", "unknown")
# # #                 }
        
# # #         return {
# # #             "success": True,
# # #             "user_id": current_user,
# # #             "locations_checked": locations_checked,
# # #             "profile_sources_found": profile_sources,
# # #             "expected_document": profile_doc_id,
# # #             "interview_sessions": interview_sessions,
# # #             "profile_load_test": profile_validation,
# # #             "collections_searched": [
# # #                 "user_profiles", "user_collection", "interview_profiles", 
# # #                 f"user_{current_user}", "profiles", "user_data"
# # #             ]
# # #         }
        
# # #     except Exception as e:
# # #         return {
# # #             "success": False,
# # #             "error": str(e),
# # #             "user_id": current_user
# # #         }

# # # @router.post("/profile/regenerate")
# # # async def regenerate_user_profile(current_user: str = Depends(get_current_user)):
# # #     """Regenerate user profile from completed interview sessions"""
# # #     try:
# # #         db = get_firestore_client()
        
# # #         # Get all completed interview sessions for user
# # #         sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user).where("status", "==", "completed")
# # #         completed_sessions = list(sessions_ref.stream())
        
# # #         if not completed_sessions:
# # #             raise HTTPException(
# # #                 status_code=400,
# # #                 detail="No completed interview sessions found. Complete an interview first."
# # #             )
        
# # #         # TODO: Implement profile regeneration logic based on actual user responses
# # #         # This would involve:
# # #         # 1. Extracting responses from completed interview sessions
# # #         # 2. Building a clean profile structure
# # #         # 3. Saving to appropriate profile collection
        
# # #         return {
# # #             "success": True,
# # #             "message": "Profile regeneration initiated",
# # #             "user_id": current_user,
# # #             "completed_sessions": len(completed_sessions),
# # #             "note": "Profile regeneration logic needs to be implemented"
# # #         }
        
# # #     except Exception as e:
# # #         raise HTTPException(
# # #             status_code=500,
# # #             detail=f"Failed to regenerate profile: {str(e)}"
# # #         )

# # # @router.delete("/profile/clear-contaminated")
# # # async def clear_contaminated_profile(current_user: str = Depends(get_current_user)):
# # #     """Clear contaminated profile data"""
# # #     try:
# # #         db = get_firestore_client()
        
# # #         # Delete the contaminated profile from all possible locations
# # #         profile_doc_id = f"{current_user}_profile_structure.json"
        
# # #         deleted_locations = []
        
# # #         # Try deleting from multiple locations
# # #         locations = [
# # #             ("user_profiles", profile_doc_id),
# # #             ("user_collection", profile_doc_id),
# # #             ("interview_profiles", f"{current_user}_profile.json"),
# # #         ]
        
# # #         for collection_name, doc_name in locations:
# # #             try:
# # #                 doc_ref = db.collection(collection_name).document(doc_name)
# # #                 if doc_ref.get().exists:
# # #                     doc_ref.delete()
# # #                     deleted_locations.append(f"{collection_name}/{doc_name}")
# # #             except Exception as e:
# # #                 print(f"Error deleting from {collection_name}/{doc_name}: {e}")
        
# # #         return {
# # #             "success": True,
# # #             "message": f"Cleared contaminated profile for user {current_user}",
# # #             "user_id": current_user,
# # #             "deleted_locations": deleted_locations,
# # #             "action": "profile_deleted"
# # #         }
        
# # #     except Exception as e:
# # #         raise HTTPException(status_code=500, detail=str(e))

# # # @router.post("/generate", response_model=RecommendationResponse)
# # # async def generate_user_recommendations(
# # #     request: RecommendationRequest,
# # #     current_user: str = Depends(get_current_user)
# # # ):
# # #     """Generate personalized recommendations based on USER-SPECIFIC profile and query"""
# # #     try:
# # #         start_time = datetime.utcnow()
# # #         settings = get_settings()
# # #         db = get_firestore_client()
        
# # #         print(f"🚀 Generating recommendations for user: {current_user}")
# # #         print(f"📝 Query: {request.query}")
        
# # #         # Load USER-SPECIFIC profile
# # #         user_profile = load_user_profile(current_user)
        
# # #         # Handle contaminated profile
# # #         if isinstance(user_profile, dict) and user_profile.get("error") == "contaminated_profile":
# # #             raise HTTPException(
# # #                 status_code=422,
# # #                 detail={
# # #                     "error": "contaminated_profile",
# # #                     "message": "Cannot generate recommendations with contaminated profile data",
# # #                     "validation": user_profile.get("validation", {}),
# # #                     "recommended_action": "complete_interview_first_or_clear_contaminated_profile"
# # #                 }
# # #             )
        
# # #         if not user_profile:
# # #             raise HTTPException(
# # #                 status_code=404, 
# # #                 detail="No profile found for this user. Please complete an interview first to generate your personalized profile."
# # #             )
        
# # #         print(f"✅ Loaded profile for user {current_user}")
        
# # #         # Clean profile for AI processing (remove metadata)
# # #         clean_profile = {k: v for k, v in user_profile.items() if not k.startswith('_')}
        
# # #         # Generate session ID for conversation tracking
# # #         session_id = str(uuid.uuid4())
        
# # #         # Save user query to conversation history
# # #         save_conversation_message(
# # #             current_user, 
# # #             session_id, 
# # #             "user", 
# # #             f"Generate recommendations for: {request.query}", 
# # #             "recommendation",
# # #             f"Recommendation Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
# # #         )
        
# # #         # Generate recommendations using USER-SPECIFIC profile
# # #         recs_json = generate_recommendations(
# # #             clean_profile, 
# # #             request.query, 
# # #             settings.OPENAI_API_KEY
# # #         )
        
# # #         try:
# # #             recs = json.loads(recs_json)
            
# # #             # Normalize to list
# # #             if isinstance(recs, dict):
# # #                 if "recommendations" in recs and isinstance(recs["recommendations"], list):
# # #                     recs = recs["recommendations"]
# # #                 else:
# # #                     recs = [recs]
            
# # #             if not isinstance(recs, list):
# # #                 raise HTTPException(
# # #                     status_code=500,
# # #                     detail="Unexpected response format – expected a list of recommendations."
# # #                 )
            
# # #             # Calculate processing time
# # #             processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
# # #             # Prepare recommendation data for database
# # #             recommendation_data = {
# # #                 "user_id": current_user,
# # #                 "query": request.query,
# # #                 "category": request.category,
# # #                 "recommendations": recs,
# # #                 "processing_time_ms": int(processing_time),
# # #                 "search_context": search_web(f"{request.query} recommendations 2024"),
# # #                 "session_id": session_id,
# # #                 "profile_version": clean_profile.get("version", "1.0"),
# # #                 "user_specific": True,
# # #                 "profile_validation": user_profile.get("_validation", {})
# # #             }
            
# # #             # Save to database
# # #             recommendation_id = save_recommendation_to_db(recommendation_data, db)
            
# # #             if not recommendation_id:
# # #                 print("⚠️ Warning: Failed to save recommendation to database")
# # #                 recommendation_id = str(uuid.uuid4())  # Fallback
            
# # #             # Format recommendations for conversation history
# # #             recs_text = f"Here are your personalized recommendations based on your profile:\n\n"
# # #             for i, rec in enumerate(recs, 1):
# # #                 recs_text += f"{i}. **{rec.get('title', 'Recommendation')}**\n"
# # #                 recs_text += f"   {rec.get('description', rec.get('reason', 'No description provided'))}\n"
# # #                 if 'reasons' in rec and isinstance(rec['reasons'], list):
# # #                     for reason in rec['reasons']:
# # #                         recs_text += f"   • {reason}\n"
# # #                 recs_text += "\n"
            
# # #             # Save recommendations to conversation history
# # #             save_conversation_message(
# # #                 current_user, 
# # #                 session_id, 
# # #                 "assistant", 
# # #                 recs_text, 
# # #                 "recommendation"
# # #             )
            
# # #             # Convert to RecommendationItem objects
# # #             recommendation_items = []
# # #             for rec in recs:
# # #                 recommendation_items.append(RecommendationItem(
# # #                     title=rec.get('title', 'Recommendation'),
# # #                     description=rec.get('description', rec.get('reason', '')),
# # #                     reasons=rec.get('reasons', [rec.get('reason', '')] if rec.get('reason') else []),
# # #                     category=request.category,
# # #                     confidence_score=rec.get('confidence_score', 0.8)
# # #                 ))
            
# # #             return RecommendationResponse(
# # #                 recommendation_id=recommendation_id,
# # #                 recommendations=recommendation_items,
# # #                 query=request.query,
# # #                 category=request.category,
# # #                 user_id=current_user,
# # #                 generated_at=datetime.utcnow(),
# # #                 processing_time_ms=int(processing_time)
# # #             )
            
# # #         except json.JSONDecodeError as e:
# # #             error_msg = f"Failed to parse recommendations: {str(e)}"
            
# # #             # Save error to conversation history
# # #             save_conversation_message(
# # #                 current_user, 
# # #                 session_id, 
# # #                 "assistant", 
# # #                 f"Sorry, I encountered an error generating recommendations: {error_msg}", 
# # #                 "recommendation"
# # #             )
            
# # #             raise HTTPException(
# # #                 status_code=500,
# # #                 detail=error_msg
# # #             )
            
# # #     except HTTPException:
# # #         raise
# # #     except Exception as e:
# # #         print(f"❌ Error generating recommendations for user {current_user}: {e}")
# # #         raise HTTPException(
# # #             status_code=500,
# # #             detail=f"Failed to generate recommendations: {str(e)}"
# # #         )

# # # @router.post("/category")
# # # async def generate_category_recommendations(
# # #     request: RecommendationRequest,
# # #     current_user: str = Depends(get_current_user)
# # # ):
# # #     """Generate category-specific recommendations - redirect to main generate endpoint"""
# # #     # This now uses the enhanced generate endpoint
# # #     return await generate_user_recommendations(request, current_user)

# # # @router.post("/{recommendation_id}/feedback")
# # # async def submit_recommendation_feedback(
# # #     recommendation_id: str,
# # #     feedback: RecommendationFeedback,
# # #     current_user: str = Depends(get_current_user)
# # # ):
# # #     """Submit feedback for a recommendation"""
# # #     try:
# # #         db = get_firestore_client()
        
# # #         # Verify recommendation exists and belongs to user
# # #         rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
# # #         if not rec_doc.exists:
# # #             raise HTTPException(status_code=404, detail="Recommendation not found")
        
# # #         # Save feedback
# # #         feedback_data = {
# # #             "feedback_type": feedback.feedback_type,
# # #             "rating": feedback.rating,
# # #             "comment": feedback.comment,
# # #             "clicked_items": feedback.clicked_items
# # #         }
        
# # #         feedback_id = save_recommendation_feedback(recommendation_id, current_user, feedback_data, db)
        
# # #         if not feedback_id:
# # #             raise HTTPException(status_code=500, detail="Failed to save feedback")
        
# # #         return {
# # #             "success": True,
# # #             "message": "Feedback submitted successfully",
# # #             "feedback_id": feedback_id,
# # #             "recommendation_id": recommendation_id
# # #         }
        
# # #     except Exception as e:
# # #         raise HTTPException(
# # #             status_code=500,
# # #             detail=f"Failed to submit feedback: {str(e)}"
# # #         )

# # # @router.delete("/{recommendation_id}")
# # # async def delete_recommendation(
# # #     recommendation_id: str,
# # #     current_user: str = Depends(get_current_user)
# # # ):
# # #     """Delete a recommendation from history"""
# # #     try:
# # #         db = get_firestore_client()
        
# # #         # Verify recommendation exists and belongs to user
# # #         rec_ref = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id)
# # #         rec_doc = rec_ref.get()
        
# # #         if not rec_doc.exists:
# # #             raise HTTPException(status_code=404, detail="Recommendation not found")
        
# # #         # Soft delete
# # #         rec_ref.update({
# # #             "is_active": False,
# # #             "deleted_at": datetime.utcnow()
# # #         })
        
# # #         # Also update in recommendation_history
# # #         try:
# # #             db.collection("recommendation_history").document(recommendation_id).update({
# # #                 "is_active": False,
# # #                 "deleted_at": datetime.utcnow()
# # #             })
# # #         except:
# # #             pass  # History record might not exist
        
# # #         return {
# # #             "success": True,
# # #             "message": f"Recommendation {recommendation_id} deleted successfully"
# # #         }
        
# # #     except Exception as e:
# # #         raise HTTPException(
# # #             status_code=500,
# # #             detail=f"Failed to delete recommendation: {str(e)}"
# # #         )

# # # # IMPORTANT: Put parameterized routes LAST to avoid route conflicts
# # # @router.get("/{recommendation_id}")
# # # async def get_recommendation_details(
# # #     recommendation_id: str,
# # #     current_user: str = Depends(get_current_user)
# # # ):
# # #     """Get detailed information about a specific recommendation"""
# # #     try:
# # #         db = get_firestore_client()
        
# # #         # Get recommendation details
# # #         rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
# # #         if not rec_doc.exists:
# # #             raise HTTPException(status_code=404, detail="Recommendation not found")
        
# # #         rec_data = rec_doc.to_dict()
        
# # #         # Increment view count
# # #         current_views = rec_data.get("view_count", 0)
# # #         rec_doc.reference.update({
# # #             "view_count": current_views + 1,
# # #             "last_viewed": datetime.utcnow()
# # #         })
        
# # #         # Get feedback for this recommendation
# # #         feedback_query = db.collection("recommendation_feedback").where("recommendation_id", "==", recommendation_id).where("user_id", "==", current_user)
# # #         feedback_docs = feedback_query.stream()
        
# # #         feedback_list = []
# # #         for feedback_doc in feedback_docs:
# # #             feedback_data = feedback_doc.to_dict()
# # #             feedback_list.append({
# # #                 "feedback_id": feedback_data["feedback_id"],
# # #                 "feedback_type": feedback_data["feedback_type"],
# # #                 "rating": feedback_data.get("rating"),
# # #                 "comment": feedback_data.get("comment"),
# # #                 "created_at": feedback_data["created_at"]
# # #             })
        
# # #         return {
# # #             "success": True,
# # #             "recommendation": {
# # #                 "recommendation_id": rec_data["recommendation_id"],
# # #                 "query": rec_data["query"],
# # #                 "category": rec_data.get("category"),
# # #                 "recommendations": rec_data["recommendations"],
# # #                 "generated_at": rec_data["generated_at"],
# # #                 "processing_time_ms": rec_data.get("processing_time_ms"),
# # #                 "view_count": current_views + 1,
# # #                 "search_context": rec_data.get("search_context", []),
# # #                 "profile_validation": rec_data.get("profile_validation", {})
# # #             },
# # #             "feedback": feedback_list,
# # #             "user_id": current_user
# # #         }
        
# # #     except Exception as e:
# # #         raise HTTPException(
# # #             status_code=500,
# # #             detail=f"Failed to get recommendation details: {str(e)}"
# # #         )



# # from fastapi import APIRouter, Depends, HTTPException, status, Query
# # from pydantic import BaseModel
# # from typing import Dict, Any, List, Optional
# # import json
# # from openai import OpenAI
# # from duckduckgo_search import DDGS 
# # from duckduckgo_search.exceptions import DuckDuckGoSearchException
# # from itertools import islice
# # import time
# # import uuid
# # from datetime import datetime, timedelta

# # from app.core.security import get_current_user
# # from app.core.firebase import get_firestore_client
# # from app.core.config import get_settings
# # from app.routers.conversations import save_conversation_message

# # router = APIRouter()

# # # Enhanced Pydantic models
# # class RecommendationRequest(BaseModel):
# #     query: str
# #     category: Optional[str] = None
# #     user_id: Optional[str] = None
# #     context: Optional[Dict[str, Any]] = None

# # class RecommendationItem(BaseModel):
# #     title: str
# #     description: Optional[str] = None
# #     reasons: List[str] = []
# #     category: Optional[str] = None
# #     confidence_score: Optional[float] = None
# #     external_links: Optional[List[str]] = None

# # class RecommendationResponse(BaseModel):
# #     recommendation_id: str
# #     recommendations: List[RecommendationItem]
# #     query: str
# #     category: Optional[str] = None
# #     user_id: str
# #     generated_at: datetime
# #     processing_time_ms: Optional[int] = None

# # class RecommendationFeedback(BaseModel):
# #     recommendation_id: str
# #     feedback_type: str  # 'like', 'dislike', 'not_relevant', 'helpful'
# #     rating: Optional[int] = None  # 1-5 stars
# #     comment: Optional[str] = None
# #     clicked_items: List[str] = []

# # # Database helper functions
# # def save_recommendation_to_db(recommendation_data: Dict[str, Any], db) -> str:
# #     """Save recommendation to database and return recommendation_id"""
# #     try:
# #         recommendation_id = str(uuid.uuid4())
        
# #         # Prepare data for database
# #         db_data = {
# #             "recommendation_id": recommendation_id,
# #             "user_id": recommendation_data["user_id"],
# #             "query": recommendation_data["query"],
# #             "category": recommendation_data.get("category"),
# #             "recommendations": recommendation_data["recommendations"],
# #             "generated_at": datetime.utcnow(),
# #             "processing_time_ms": recommendation_data.get("processing_time_ms"),
# #             "search_context": recommendation_data.get("search_context", []),
# #             "profile_version": recommendation_data.get("profile_version"),
# #             "profile_completeness": recommendation_data.get("profile_completeness"),
# #             "questions_answered": recommendation_data.get("questions_answered", 0),
# #             "session_id": recommendation_data.get("session_id"),
# #             "is_active": True,
# #             "view_count": 0,
# #             "feedback_count": 0
# #         }
        
# #         # Save to user-specific collection
# #         db.collection("user_recommendations").document(recommendation_data["user_id"]).collection("recommendations").document(recommendation_id).set(db_data)
        
# #         # Also save to recommendation history for analytics
# #         history_data = {
# #             "recommendation_id": recommendation_id,
# #             "user_id": recommendation_data["user_id"],
# #             "query": recommendation_data["query"],
# #             "category": recommendation_data.get("category"),
# #             "recommendations_count": len(recommendation_data["recommendations"]),
# #             "profile_completeness": recommendation_data.get("profile_completeness"),
# #             "created_at": datetime.utcnow(),
# #             "is_bookmarked": False,
# #             "tags": []
# #         }
        
# #         db.collection("recommendation_history").document(recommendation_id).set(history_data)
        
# #         return recommendation_id
        
# #     except Exception as e:
# #         print(f"Error saving recommendation: {e}")
# #         return None

# # def get_user_recommendation_history(user_id: str, db, limit: int = 20, offset: int = 0, category: str = None):
# #     """Get user's recommendation history from database"""
# #     try:
# #         query = db.collection("user_recommendations").document(user_id).collection("recommendations").where("is_active", "==", True)
        
# #         if category:
# #             query = query.where("category", "==", category)
        
# #         recommendations = query.order_by("generated_at", direction="DESCENDING").limit(limit).offset(offset).stream()
        
# #         history = []
# #         for rec in recommendations:
# #             rec_data = rec.to_dict()
# #             history.append({
# #                 "recommendation_id": rec_data["recommendation_id"],
# #                 "query": rec_data["query"],
# #                 "category": rec_data.get("category"),
# #                 "recommendations_count": len(rec_data.get("recommendations", [])),
# #                 "generated_at": rec_data["generated_at"],
# #                 "view_count": rec_data.get("view_count", 0),
# #                 "feedback_count": rec_data.get("feedback_count", 0),
# #                 "session_id": rec_data.get("session_id"),
# #                 "profile_completeness": rec_data.get("profile_completeness")
# #             })
        
# #         return history
        
# #     except Exception as e:
# #         print(f"Error getting recommendation history: {e}")
# #         return []

# # def save_recommendation_feedback(recommendation_id: str, user_id: str, feedback_data: Dict[str, Any], db):
# #     """Save user feedback for a recommendation"""
# #     try:
# #         feedback_id = str(uuid.uuid4())
        
# #         feedback_doc = {
# #             "feedback_id": feedback_id,
# #             "recommendation_id": recommendation_id,
# #             "user_id": user_id,
# #             "feedback_type": feedback_data["feedback_type"],
# #             "rating": feedback_data.get("rating"),
# #             "comment": feedback_data.get("comment"),
# #             "clicked_items": feedback_data.get("clicked_items", []),
# #             "created_at": datetime.utcnow()
# #         }
        
# #         # Save feedback
# #         db.collection("recommendation_feedback").document(feedback_id).set(feedback_doc)
        
# #         # Update recommendation with feedback count
# #         rec_ref = db.collection("user_recommendations").document(user_id).collection("recommendations").document(recommendation_id)
# #         rec_doc = rec_ref.get()
        
# #         if rec_doc.exists:
# #             current_feedback_count = rec_doc.to_dict().get("feedback_count", 0)
# #             rec_ref.update({"feedback_count": current_feedback_count + 1})
        
# #         return feedback_id
        
# #     except Exception as e:
# #         print(f"Error saving feedback: {e}")
# #         return None

# # # PERMISSIVE Profile validation and loading functions
# # def validate_profile_authenticity(profile_data: Dict[str, Any], user_id: str, db) -> Dict[str, Any]:
# #     """Modified validation that allows partial profiles but detects contaminated data"""
    
# #     if not profile_data or not user_id:
# #         return {"valid": False, "reason": "empty_profile_or_user"}
    
# #     validation_result = {
# #         "valid": True,
# #         "warnings": [],
# #         "user_id": user_id,
# #         "profile_sections": {},
# #         "authenticity_score": 1.0,  # Start optimistic
# #         "template_indicators": [],
# #         "profile_completeness": "partial"
# #     }
    
# #     try:
# #         # Check interview sessions for this user
# #         interview_sessions = db.collection("interview_sessions").where("user_id", "==", user_id).stream()
        
# #         completed_phases = set()
# #         in_progress_phases = set()
# #         session_data = {}
# #         total_questions_answered = 0
# #         has_any_session = False
        
# #         for session in interview_sessions:
# #             has_any_session = True
# #             session_dict = session.to_dict()
# #             session_data[session.id] = session_dict
            
# #             phase = session_dict.get("current_phase", "unknown")
            
# #             if session_dict.get("status") == "completed":
# #                 completed_phases.add(phase)
# #                 total_questions_answered += session_dict.get("questions_answered", 0)
# #             elif session_dict.get("status") == "in_progress":
# #                 in_progress_phases.add(phase)
# #                 total_questions_answered += session_dict.get("questions_answered", 0)
        
# #         validation_result["completed_phases"] = list(completed_phases)
# #         validation_result["in_progress_phases"] = list(in_progress_phases)
# #         validation_result["total_questions_answered"] = total_questions_answered
# #         validation_result["has_any_session"] = has_any_session
# #         validation_result["session_data"] = session_data
        
# #         # Analyze profile sections
# #         profile_sections = profile_data.get("recommendationProfiles", {})
# #         general_profile = profile_data.get("generalprofile", {})
        
# #         total_detailed_responses = 0
# #         total_authenticated_responses = 0
# #         total_foreign_responses = 0
# #         template_indicators = []
        
# #         # Check recommendation profiles
# #         for section_name, section_data in profile_sections.items():
# #             section_validation = {
# #                 "has_data": bool(section_data),
# #                 "has_session_for_phase": section_name in (completed_phases | in_progress_phases),
# #                 "data_authenticity": "unknown",
# #                 "detailed_response_count": 0,
# #                 "authenticated_response_count": 0,
# #                 "foreign_response_count": 0
# #             }
            
# #             if section_data and isinstance(section_data, dict):
# #                 def analyze_responses(data, path=""):
# #                     nonlocal total_detailed_responses, total_authenticated_responses, total_foreign_responses
                    
# #                     if isinstance(data, dict):
# #                         for key, value in data.items():
# #                             current_path = f"{path}.{key}" if path else key
                            
# #                             if isinstance(value, dict) and "value" in value:
# #                                 response_value = value.get("value", "")
# #                                 if isinstance(response_value, str) and len(response_value.strip()) > 10:
# #                                     section_validation["detailed_response_count"] += 1
# #                                     total_detailed_responses += 1
                                    
# #                                     # Check authentication markers
# #                                     if "user_id" in value and "updated_at" in value:
# #                                         if value.get("user_id") == user_id:
# #                                             section_validation["authenticated_response_count"] += 1
# #                                             total_authenticated_responses += 1
# #                                         else:
# #                                             section_validation["foreign_response_count"] += 1
# #                                             total_foreign_responses += 1
# #                                             template_indicators.append(
# #                                                 f"Foreign user data: {section_name}.{current_path} (from {value.get('user_id')})"
# #                                             )
# #                                     # If no auth markers, it could be legitimate new data or template
# #                                     # We'll be more lenient here
                                
# #                                 # Recursively check nested structures
# #                                 if isinstance(value, dict):
# #                                     analyze_responses(value, current_path)
                
# #                 analyze_responses(section_data)
                
# #                 # Determine authenticity for this section
# #                 if section_validation["foreign_response_count"] > 0:
# #                     section_validation["data_authenticity"] = "foreign_user_data"
# #                 elif section_validation["detailed_response_count"] > 0:
# #                     if section_validation["has_session_for_phase"]:
# #                         section_validation["data_authenticity"] = "legitimate"
# #                     elif section_validation["authenticated_response_count"] > 0:
# #                         section_validation["data_authenticity"] = "authenticated_but_no_session"
# #                     else:
# #                         # This could be legitimate new data or template
# #                         # Check if user has ANY interview activity
# #                         if has_any_session:
# #                             section_validation["data_authenticity"] = "possibly_legitimate"
# #                         else:
# #                             section_validation["data_authenticity"] = "suspicious_no_sessions"
# #                             template_indicators.append(
# #                                 f"Detailed data without any interview sessions: {section_name}"
# #                             )
# #                 else:
# #                     section_validation["data_authenticity"] = "minimal_data"
            
# #             validation_result["profile_sections"][section_name] = section_validation
        
# #         # Check general profile
# #         general_detailed_responses = 0
# #         general_authenticated_responses = 0
        
# #         def check_general_profile(data, path="generalprofile"):
# #             nonlocal general_detailed_responses, general_authenticated_responses
            
# #             if isinstance(data, dict):
# #                 for key, value in data.items():
# #                     current_path = f"{path}.{key}"
                    
# #                     if isinstance(value, dict):
# #                         if "value" in value and isinstance(value["value"], str) and len(value["value"].strip()) > 10:
# #                             general_detailed_responses += 1
# #                             if "user_id" in value and value.get("user_id") == user_id:
# #                                 general_authenticated_responses += 1
# #                         else:
# #                             check_general_profile(value, current_path)
        
# #         check_general_profile(general_profile)
        
# #         # Calculate totals
# #         total_responses_with_general = total_detailed_responses + general_detailed_responses
# #         total_auth_with_general = total_authenticated_responses + general_authenticated_responses
        
# #         # Calculate authenticity score (more lenient)
# #         if total_responses_with_general > 0:
# #             auth_ratio = total_auth_with_general / total_responses_with_general
# #             session_factor = 1.0 if has_any_session else 0.3
# #             foreign_penalty = min(total_foreign_responses / max(total_responses_with_general, 1), 0.8)
            
# #             validation_result["authenticity_score"] = max(0.0, (auth_ratio * 0.6 + session_factor * 0.4) - foreign_penalty)
# #         else:
# #             validation_result["authenticity_score"] = 1.0
        
# #         # Determine profile completeness
# #         if len(completed_phases) > 0:
# #             validation_result["profile_completeness"] = "complete"
# #         elif has_any_session and total_questions_answered > 0:
# #             validation_result["profile_completeness"] = "partial_in_progress"
# #         elif total_responses_with_general > 0:
# #             validation_result["profile_completeness"] = "partial_data_exists"
# #         else:
# #             validation_result["profile_completeness"] = "empty"
        
# #         validation_result["template_indicators"] = template_indicators
# #         validation_result["total_detailed_responses"] = total_responses_with_general
# #         validation_result["total_authenticated_responses"] = total_auth_with_general
# #         validation_result["total_foreign_responses"] = total_foreign_responses
        
# #         # MODIFIED validation logic - more permissive
# #         # Only mark as invalid for serious contamination issues
# #         if total_foreign_responses > 0:
# #             validation_result["valid"] = False
# #             validation_result["reason"] = "foreign_user_data_detected"
# #         elif total_responses_with_general > 10 and not has_any_session:
# #             # Extensive data but no interview sessions at all - suspicious
# #             validation_result["valid"] = False
# #             validation_result["reason"] = "extensive_data_without_any_sessions"
# #         elif validation_result["authenticity_score"] < 0.2:
# #             # Very low authenticity score
# #             validation_result["valid"] = False
# #             validation_result["reason"] = "very_low_authenticity_score"
        
# #         # Add diagnostics
# #         validation_result["diagnostics"] = {
# #             "has_interview_activity": has_any_session,
# #             "questions_answered": total_questions_answered,
# #             "data_to_session_ratio": total_responses_with_general / max(len(completed_phases | in_progress_phases), 1),
# #             "authentication_percentage": (total_auth_with_general / max(total_responses_with_general, 1)) * 100,
# #             "foreign_data_percentage": (total_foreign_responses / max(total_responses_with_general, 1)) * 100,
# #             "profile_usability": "usable" if validation_result["valid"] else "needs_cleanup"
# #         }
        
# #         return validation_result
        
# #     except Exception as e:
# #         return {
# #             "valid": False, 
# #             "reason": "validation_error", 
# #             "error": str(e)
# #         }

# # def load_user_profile(user_id: str = None) -> Dict[str, Any]:
# #     """Load and validate USER-SPECIFIC profile from Firestore - allows partial profiles"""
# #     try:
# #         db = get_firestore_client()
        
# #         if not user_id:
# #             print("❌ No user_id provided for profile loading")
# #             return {}
        
# #         print(f"🔍 Looking for profile for user: {user_id}")
        
# #         # Try to find profile in multiple locations
# #         profile_locations = [
# #             {
# #                 "collection": "user_profiles",
# #                 "document": f"{user_id}_profile_structure.json",
# #                 "description": "Primary user_profiles collection"
# #             },
# #             {
# #                 "collection": "user_collection", 
# #                 "document": f"{user_id}_profile_structure.json",
# #                 "description": "Fallback user_collection with user prefix"
# #             },
# #             {
# #                 "collection": "interview_profiles",
# #                 "document": f"{user_id}_profile.json", 
# #                 "description": "Interview-generated profile"
# #             },
# #             {
# #                 "collection": f"user_{user_id}",
# #                 "document": "profile_structure.json",
# #                 "description": "User-specific collection"
# #             }
# #         ]
        
# #         raw_profile = None
# #         profile_source = None
        
# #         for location in profile_locations:
# #             try:
# #                 doc_ref = db.collection(location["collection"]).document(location["document"])
# #                 doc = doc_ref.get()
                
# #                 if doc.exists:
# #                     raw_profile = doc.to_dict()
# #                     profile_source = f"{location['collection']}/{location['document']}"
# #                     print(f"✅ Found profile at: {profile_source}")
# #                     break
                    
# #             except Exception as e:
# #                 print(f"❌ Error checking {location['description']}: {e}")
# #                 continue
        
# #         if not raw_profile:
# #             print(f"❌ No profile found for user: {user_id}")
# #             return {}
        
# #         # Validate profile authenticity with permissive validation
# #         validation = validate_profile_authenticity(raw_profile, user_id, db)
        
# #         print(f"🔍 Profile validation result: {validation.get('valid')} - {validation.get('reason', 'OK')}")
# #         print(f"🔍 Profile completeness: {validation.get('profile_completeness', 'unknown')}")
# #         print(f"🔍 Questions answered: {validation.get('total_questions_answered', 0)}")
# #         print(f"🔍 Authenticity score: {validation.get('authenticity_score', 0.0):.2f}")
        
# #         if validation.get("warnings"):
# #             print(f"⚠️ Profile warnings: {validation['warnings']}")
        
# #         # Only reject for serious contamination
# #         if not validation.get("valid"):
# #             serious_issues = ["foreign_user_data_detected", "extensive_data_without_any_sessions"]
# #             if validation.get("reason") in serious_issues:
# #                 print(f"🚨 SERIOUS PROFILE ISSUE for user {user_id}: {validation.get('reason')}")
# #                 return {
# #                     "error": "contaminated_profile",
# #                     "user_id": user_id,
# #                     "validation": validation,
# #                     "message": f"Profile validation failed: {validation.get('reason')}",
# #                     "profile_source": profile_source
# #                 }
# #             else:
# #                 print(f"⚠️ Minor profile issue for user {user_id}: {validation.get('reason')} - allowing with warnings")
        
# #         # Return profile with validation info (even if partial)
# #         profile_with_metadata = raw_profile.copy()
# #         profile_with_metadata["_validation"] = validation
# #         profile_with_metadata["_source"] = profile_source
        
# #         return profile_with_metadata
        
# #     except Exception as e:
# #         print(f"❌ Error loading user profile for {user_id}: {e}")
# #         return {}

# # def search_web(query, max_results=3, max_retries=3, base_delay=1.0):
# #     """Query DuckDuckGo via DDGS.text(), returning up to max_results items."""
# #     for attempt in range(1, max_retries + 1):
# #         try:
# #             with DDGS() as ddgs:
# #                 return list(islice(ddgs.text(query), max_results))
# #         except DuckDuckGoSearchException as e:
# #             msg = str(e)
# #             if "202" in msg:
# #                 wait = base_delay * (2 ** (attempt - 1))
# #                 print(f"[search_web] Rate‑limited (202). Retry {attempt}/{max_retries} in {wait:.1f}s…")
# #                 time.sleep(wait)
# #             else:
# #                 raise
# #         except Exception as e:
# #             print(f"[search_web] Unexpected error: {e}")
# #             break
    
# #     print(f"[search_web] Failed to fetch results after {max_retries} attempts.")
# #     return []

# # def generate_recommendations_with_context(user_profile, user_query, openai_key, completeness, questions_answered):
# #     """Generate recommendations with context about profile completeness"""
    
# #     if completeness == "empty" or questions_answered == 0:
# #         prompt_context = "**Profile Status**: This user has not completed any interview questions yet. Provide general recommendations based on the query, and suggest completing an interview for personalization."
# #     elif completeness in ["partial_in_progress", "partial_data_exists"]:
# #         prompt_context = f"**Profile Status**: This user has answered {questions_answered} interview questions. Use available profile data but note that recommendations will improve as they complete more of the interview."
# #     else:
# #         prompt_context = "**Profile Status**: This user has a complete profile. Provide highly personalized recommendations."
    
# #     search_results = search_web(f"{user_query} recommendations 2024")
    
# #     prompt = f"""
# #     **Task**: Generate exactly 3 recommendations based on available data:
    
# #     {prompt_context}
    
# #     **Available User Profile**:
# #     {json.dumps(user_profile, indent=2)}
    
# #     **User Query**:
# #     "{user_query}"
    
# #     **Web Context** (for reference only):
# #     {search_results}
    
# #     **Requirements**:
# #     1. Use whatever profile information is available
# #     2. If profile is incomplete, provide good general recommendations
# #     3. Include a note about completing interview for better personalization if needed
# #     4. Format as JSON array with each recommendation having:
# #        - title: string
# #        - description: string
# #        - reasons: array of strings
# #        - confidence_score: float (0.6 for basic, 0.8+ for personalized)
    
# #     Generate your response in JSON format only.
# #     """
    
# #     client = OpenAI(api_key=openai_key)
# #     response = client.chat.completions.create(
# #         model="gpt-4",
# #         messages=[
# #             {"role": "system", "content": "You're a recommendation engine that works with both complete and partial user profiles. Output valid JSON only."},
# #             {"role": "user", "content": prompt}
# #         ],
# #         temperature=0.7  
# #     )
    
# #     return response.choices[0].message.content

# # # ROUTE DEFINITIONS - SPECIFIC ROUTES FIRST, PARAMETERIZED ROUTES LAST

# # @router.get("/profile")
# # async def get_user_profile(current_user: str = Depends(get_current_user)):
# #     """Get the current user's profile - allows partial profiles"""
# #     try:
# #         print(f"🔍 Getting profile for user: {current_user}")
# #         profile = load_user_profile(current_user)
        
# #         # Handle contaminated profile (only for serious issues)
# #         if isinstance(profile, dict) and profile.get("error") == "contaminated_profile":
# #             validation_info = profile.get("validation", {})
            
# #             # Check if it's a serious contamination or just partial data
# #             if validation_info.get("reason") == "foreign_user_data_detected":
# #                 raise HTTPException(
# #                     status_code=422,
# #                     detail={
# #                         "error": "contaminated_profile",
# #                         "message": "Profile contains data from other users",
# #                         "user_id": current_user,
# #                         "validation": validation_info,
# #                         "recommended_action": "clear_contaminated_profile_and_restart_interview"
# #                     }
# #                 )
# #             elif validation_info.get("reason") == "extensive_data_without_any_sessions":
# #                 raise HTTPException(
# #                     status_code=422,
# #                     detail={
# #                         "error": "suspicious_profile",
# #                         "message": "Profile has extensive data but no interview sessions",
# #                         "user_id": current_user,
# #                         "validation": validation_info,
# #                         "recommended_action": "start_interview_to_validate_or_clear_profile"
# #                     }
# #                 )
# #             # For other validation issues, allow profile but with warnings
        
# #         if not profile:
# #             # Check interview status
# #             db = get_firestore_client()
# #             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
# #             sessions = list(sessions_ref.stream())
            
# #             if not sessions:
# #                 raise HTTPException(
# #                     status_code=404,
# #                     detail="No profile found. Please start an interview to begin creating your profile."
# #                 )
            
# #             # If there are sessions but no profile, suggest continuing
# #             in_progress_sessions = [s for s in sessions if s.to_dict().get("status") == "in_progress"]
# #             if in_progress_sessions:
# #                 raise HTTPException(
# #                     status_code=404,
# #                     detail={
# #                         "message": "Interview in progress but no profile generated yet. Continue the interview to build your profile.",
# #                         "sessions": [{"session_id": s.id, "phase": s.to_dict().get("current_phase")} for s in in_progress_sessions]
# #                     }
# #                 )
        
# #         # Return profile (even if partial)
# #         clean_profile = {k: v for k, v in profile.items() if not k.startswith('_')}
# #         validation_summary = profile.get("_validation", {})
        
# #         response = {
# #             "success": True,
# #             "profile": clean_profile,
# #             "user_id": current_user,
# #             "profile_type": "user_specific",
# #             "profile_found": True,
# #             "profile_completeness": validation_summary.get("profile_completeness", "unknown"),
# #             "validation_summary": {
# #                 "valid": validation_summary.get("valid", True),
# #                 "authenticity_score": validation_summary.get("authenticity_score", 1.0),
# #                 "reason": validation_summary.get("reason"),
# #                 "has_interview_activity": validation_summary.get("has_any_session", False),
# #                 "questions_answered": validation_summary.get("total_questions_answered", 0),
# #                 "total_responses": validation_summary.get("total_detailed_responses", 0),
# #                 "authenticated_responses": validation_summary.get("total_authenticated_responses", 0),
# #                 "completed_phases": validation_summary.get("completed_phases", []),
# #                 "in_progress_phases": validation_summary.get("in_progress_phases", [])
# #             },
# #             "profile_source": profile.get("_source", "unknown")
# #         }
        
# #         # Add guidance based on completeness
# #         if validation_summary.get("profile_completeness") == "partial_in_progress":
# #             response["message"] = "Profile is being built as you answer interview questions. Continue the interview for more personalized recommendations."
# #         elif validation_summary.get("profile_completeness") == "partial_data_exists":
# #             response["message"] = "Profile has some data. Start or continue an interview to enhance personalization."
# #         elif validation_summary.get("profile_completeness") == "complete":
# #             response["message"] = "Profile is complete and ready for personalized recommendations."
# #         elif validation_summary.get("profile_completeness") == "empty":
# #             response["message"] = "Profile is empty. Start an interview to begin building your personalized profile."
        
# #         return response
        
# #     except HTTPException:
# #         raise
# #     except Exception as e:
# #         print(f"❌ Error in get_user_profile: {e}")
# #         raise HTTPException(
# #             status_code=500,
# #             detail=f"Failed to load profile: {str(e)}"
# #         )

# # @router.get("/categories")
# # async def get_recommendation_categories():
# #     """Get available recommendation categories"""
# #     categories = [
# #         {
# #             "id": "movies",
# #             "name": "Movies & TV",
# #             "description": "Movie and TV show recommendations",
# #             "questions_file": "moviesAndTV_tiered_questions.json"
# #         },
# #         {
# #             "id": "food",
# #             "name": "Food & Dining",
# #             "description": "Restaurant and food recommendations",
# #             "questions_file": "foodAndDining_tiered_questions.json"
# #         },
# #         {
# #             "id": "travel",
# #             "name": "Travel",
# #             "description": "Travel destination recommendations",
# #             "questions_file": "travel_tiered_questions.json"
# #         },
# #         {
# #             "id": "books",
# #             "name": "Books & Reading",
# #             "description": "Book recommendations",
# #             "questions_file": "books_tiered_questions.json"
# #         },
# #         {
# #             "id": "music",
# #             "name": "Music",
# #             "description": "Music and artist recommendations",
# #             "questions_file": "music_tiered_questions.json"
# #         },
# #         {
# #             "id": "fitness",
# #             "name": "Fitness & Wellness",
# #             "description": "Fitness and wellness recommendations",
# #             "questions_file": "fitness_tiered_questions.json"
# #         }
# #     ]
    
# #     return {
# #         "categories": categories,
# #         "default_category": "movies"
# #     }

# # @router.get("/history")
# # async def get_recommendation_history(
# #     current_user: str = Depends(get_current_user),
# #     limit: int = Query(20, description="Number of recommendations to return"),
# #     offset: int = Query(0, description="Number of recommendations to skip"),
# #     category: Optional[str] = Query(None, description="Filter by category"),
# #     date_from: Optional[datetime] = Query(None, description="Filter from date"),
# #     date_to: Optional[datetime] = Query(None, description="Filter to date")
# # ):
# #     """Get recommendation history for the user with enhanced filtering"""
# #     try:
# #         db = get_firestore_client()
        
# #         # Simplified query to avoid index issues - just get user's recommendations
# #         query = db.collection("user_recommendations").document(current_user).collection("recommendations")
# #         query = query.where("is_active", "==", True)
# #         query = query.limit(limit).offset(offset)
        
# #         # Get all recommendations (without complex ordering initially)
# #         recommendations = list(query.stream())
        
# #         # Filter and sort in Python instead of Firestore
# #         filtered_recs = []
# #         for rec in recommendations:
# #             rec_data = rec.to_dict()
            
# #             # Apply category filter
# #             if category and rec_data.get("category") != category:
# #                 continue
            
# #             # Apply date filters
# #             rec_date = rec_data.get("generated_at")
# #             if date_from and rec_date and rec_date < date_from:
# #                 continue
# #             if date_to and rec_date and rec_date > date_to:
# #                 continue
            
# #             filtered_recs.append(rec_data)
        
# #         # Sort by generated_at descending
# #         filtered_recs.sort(key=lambda x: x.get("generated_at", datetime.min), reverse=True)
        
# #         # Format response
# #         history = []
# #         for rec_data in filtered_recs:
# #             history.append({
# #                 "recommendation_id": rec_data["recommendation_id"],
# #                 "query": rec_data["query"],
# #                 "category": rec_data.get("category"),
# #                 "recommendations_count": len(rec_data.get("recommendations", [])),
# #                 "generated_at": rec_data["generated_at"],
# #                 "view_count": rec_data.get("view_count", 0),
# #                 "feedback_count": rec_data.get("feedback_count", 0),
# #                 "session_id": rec_data.get("session_id"),
# #                 "processing_time_ms": rec_data.get("processing_time_ms"),
# #                 "profile_completeness": rec_data.get("profile_completeness", "unknown")
# #             })
        
# #         return {
# #             "success": True,
# #             "history": history,
# #             "total_count": len(history),
# #             "user_id": current_user,
# #             "filters": {
# #                 "category": category,
# #                 "date_from": date_from,
# #                 "date_to": date_to,
# #                 "limit": limit,
# #                 "offset": offset
# #             },
# #             "note": "Using simplified query to avoid Firebase index requirements"
# #         }
        
# #     except Exception as e:
# #         raise HTTPException(
# #             status_code=500,
# #             detail=f"Failed to get recommendation history: {str(e)}"
# #         )

# # @router.get("/analytics/summary")
# # async def get_recommendation_analytics(
# #     current_user: str = Depends(get_current_user),
# #     days: int = Query(30, description="Number of days to analyze")
# # ):
# #     """Get recommendation analytics for the user"""
# #     try:
# #         db = get_firestore_client()
        
# #         # Calculate date range
# #         end_date = datetime.utcnow()
# #         start_date = end_date - timedelta(days=days)
        
# #         # Get recommendations - simplified query
# #         recommendations_ref = db.collection("user_recommendations").document(current_user).collection("recommendations")
# #         recommendations = recommendations_ref.where("is_active", "==", True).stream()
        
# #         analytics = {
# #             "total_recommendations": 0,
# #             "categories_explored": set(),
# #             "query_types": {},
# #             "total_views": 0,
# #             "total_feedback": 0,
# #             "average_processing_time": 0,
# #             "recommendations_by_day": {},
# #             "most_popular_category": None,
# #             "engagement_rate": 0,
# #             "profile_completeness_breakdown": {}
# #         }
        
# #         processing_times = []
# #         daily_counts = {}
# #         category_counts = {}
# #         completeness_counts = {}
        
# #         for rec in recommendations:
# #             rec_data = rec.to_dict()
            
# #             # Filter by date range
# #             rec_date = rec_data.get("generated_at")
# #             if rec_date and rec_date < start_date:
# #                 continue
                
# #             analytics["total_recommendations"] += 1
            
# #             # Track categories
# #             category = rec_data.get("category", "general")
# #             analytics["categories_explored"].add(category)
# #             category_counts[category] = category_counts.get(category, 0) + 1
            
# #             # Track profile completeness
# #             completeness = rec_data.get("profile_completeness", "unknown")
# #             completeness_counts[completeness] = completeness_counts.get(completeness, 0) + 1
            
# #             # Track views and feedback
# #             analytics["total_views"] += rec_data.get("view_count", 0)
# #             analytics["total_feedback"] += rec_data.get("feedback_count", 0)
            
# #             # Track processing times
# #             if rec_data.get("processing_time_ms"):
# #                 processing_times.append(rec_data["processing_time_ms"])
            
# #             # Track daily activity
# #             if rec_date:
# #                 if hasattr(rec_date, 'date'):
# #                     date_str = rec_date.date().isoformat()
# #                 else:
# #                     date_str = datetime.fromisoformat(str(rec_date)).date().isoformat()
                
# #                 daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
        
# #         # Calculate averages and insights
# #         if analytics["total_recommendations"] > 0:
# #             analytics["engagement_rate"] = round((analytics["total_views"] / analytics["total_recommendations"]) * 100, 2)
        
# #         if processing_times:
# #             analytics["average_processing_time"] = round(sum(processing_times) / len(processing_times), 2)
        
# #         if category_counts:
# #             analytics["most_popular_category"] = max(category_counts, key=category_counts.get)
        
# #         analytics["categories_explored"] = list(analytics["categories_explored"])
# #         analytics["recommendations_by_day"] = daily_counts
# #         analytics["category_breakdown"] = category_counts
# #         analytics["profile_completeness_breakdown"] = completeness_counts
        
# #         return {
# #             "success": True,
# #             "analytics": analytics,
# #             "period": {
# #                 "start_date": start_date.isoformat(),
# #                 "end_date": end_date.isoformat(),
# #                 "days": days
# #             },
# #             "user_id": current_user
# #         }
        
# #     except Exception as e:
# #         raise HTTPException(
# #             status_code=500,
# #             detail=f"Failed to get recommendation analytics: {str(e)}"
# #         )

# # @router.get("/debug/profile-location")
# # async def debug_profile_location(current_user: str = Depends(get_current_user)):
# #     """Debug endpoint to check where user profile is stored and validate it"""
# #     try:
# #         db = get_firestore_client()
        
# #         locations_checked = {
# #             "user_profiles": False,
# #             "user_collection": False,
# #             "interview_profiles": False,
# #             "user_specific_collection": False,
# #             "fallback_locations": {}
# #         }
        
# #         profile_sources = []
        
# #         # Check primary location
# #         profile_doc_id = f"{current_user}_profile_structure.json"
        
# #         # Check user_profiles collection
# #         try:
# #             profile_doc = db.collection("user_profiles").document(profile_doc_id).get()
# #             locations_checked["user_profiles"] = profile_doc.exists
# #             if profile_doc.exists:
# #                 profile_sources.append({
# #                     "location": f"user_profiles/{profile_doc_id}",
# #                     "data_preview": str(profile_doc.to_dict())[:200] + "..."
# #                 })
# #         except Exception as e:
# #             locations_checked["user_profiles"] = f"Error: {e}"
        
# #         # Check user_collection fallback
# #         try:
# #             fallback_doc = db.collection("user_collection").document(profile_doc_id).get()
# #             locations_checked["user_collection"] = fallback_doc.exists
# #             if fallback_doc.exists:
# #                 profile_sources.append({
# #                     "location": f"user_collection/{profile_doc_id}",
# #                     "data_preview": str(fallback_doc.to_dict())[:200] + "..."
# #                 })
# #         except Exception as e:
# #             locations_checked["user_collection"] = f"Error: {e}"
        
# #         # Check interview_profiles
# #         try:
# #             interview_doc = db.collection("interview_profiles").document(f"{current_user}_profile.json").get()
# #             locations_checked["interview_profiles"] = interview_doc.exists
# #             if interview_doc.exists:
# #                 profile_sources.append({
# #                     "location": f"interview_profiles/{current_user}_profile.json",
# #                     "data_preview": str(interview_doc.to_dict())[:200] + "..."
# #                 })
# #         except Exception as e:
# #             locations_checked["interview_profiles"] = f"Error: {e}"
        
# #         # Check user-specific collection
# #         try:
# #             user_specific_doc = db.collection(f"user_{current_user}").document("profile_structure.json").get()
# #             locations_checked["user_specific_collection"] = user_specific_doc.exists
# #             if user_specific_doc.exists:
# #                 profile_sources.append({
# #                     "location": f"user_{current_user}/profile_structure.json",
# #                     "data_preview": str(user_specific_doc.to_dict())[:200] + "..."
# #                 })
# #         except Exception as e:
# #             locations_checked["user_specific_collection"] = f"Error: {e}"
        
# #         # Check other possible locations
# #         possible_docs = [
# #             ("user_collection", "profile_strcuture.json"),  # Original typo
# #             ("user_collection", "profile_structure.json"),
# #             ("user_collection", f"{current_user}_profile.json"),
# #             ("profiles", f"{current_user}.json"),
# #             ("user_data", f"{current_user}_profile.json")
# #         ]
        
# #         for collection_name, doc_name in possible_docs:
# #             try:
# #                 doc_exists = db.collection(collection_name).document(doc_name).get().exists
# #                 locations_checked["fallback_locations"][f"{collection_name}/{doc_name}"] = doc_exists
# #                 if doc_exists:
# #                     profile_sources.append({
# #                         "location": f"{collection_name}/{doc_name}",
# #                         "data_preview": "Found but not retrieved"
# #                     })
# #             except Exception as e:
# #                 locations_checked["fallback_locations"][f"{collection_name}/{doc_name}"] = f"Error: {e}"
        
# #         # Get interview session info
# #         interview_sessions = []
# #         try:
# #             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
# #             for session in sessions_ref.stream():
# #                 session_data = session.to_dict()
# #                 interview_sessions.append({
# #                     "session_id": session.id,
# #                     "status": session_data.get("status"),
# #                     "phase": session_data.get("current_phase"),
# #                     "tier": session_data.get("current_tier"),
# #                     "questions_answered": session_data.get("questions_answered", 0),
# #                     "created_at": session_data.get("created_at"),
# #                     "updated_at": session_data.get("updated_at")
# #                 })
# #         except Exception as e:
# #             interview_sessions = [{"error": str(e)}]
        
# #         # Test the current profile loading function
# #         test_profile = load_user_profile(current_user)
# #         profile_validation = None
        
# #         if test_profile:
# #             if test_profile.get("error"):
# #                 profile_validation = {
# #                     "status": "error",
# #                     "error_type": test_profile.get("error"),
# #                     "validation_details": test_profile.get("validation", {})
# #                 }
# #             else:
# #                 profile_validation = {
# #                     "status": "loaded",
# #                     "validation_summary": test_profile.get("_validation", {}),
# #                     "source": test_profile.get("_source", "unknown")
# #                 }
        
# #         return {
# #             "success": True,
# #             "user_id": current_user,
# #             "locations_checked": locations_checked,
# #             "profile_sources_found": profile_sources,
# #             "expected_document": profile_doc_id,
# #             "interview_sessions": interview_sessions,
# #             "profile_load_test": profile_validation,
# #             "collections_searched": [
# #                 "user_profiles", "user_collection", "interview_profiles", 
# #                 f"user_{current_user}", "profiles", "user_data"
# #             ]
# #         }
        
# #     except Exception as e:
# #         return {
# #             "success": False,
# #             "error": str(e),
# #             "user_id": current_user
# #         }

# # @router.post("/profile/regenerate")
# # async def regenerate_user_profile(current_user: str = Depends(get_current_user)):
# #     """Regenerate user profile from completed interview sessions"""
# #     try:
# #         db = get_firestore_client()
        
# #         # Get all interview sessions for user (both completed and in-progress)
# #         sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
# #         all_sessions = list(sessions_ref.stream())
        
# #         completed_sessions = [s for s in all_sessions if s.to_dict().get("status") == "completed"]
# #         in_progress_sessions = [s for s in all_sessions if s.to_dict().get("status") == "in_progress"]
        
# #         if not completed_sessions and not in_progress_sessions:
# #             raise HTTPException(
# #                 status_code=400,
# #                 detail="No interview sessions found. Start an interview first."
# #             )
        
# #         # TODO: Implement profile regeneration logic based on actual user responses
# #         # This would involve:
# #         # 1. Extracting responses from interview sessions
# #         # 2. Building a clean profile structure
# #         # 3. Saving to appropriate profile collection
        
# #         return {
# #             "success": True,
# #             "message": "Profile regeneration initiated",
# #             "user_id": current_user,
# #             "completed_sessions": len(completed_sessions),
# #             "in_progress_sessions": len(in_progress_sessions),
# #             "note": "Profile regeneration logic needs to be implemented"
# #         }
        
# #     except Exception as e:
# #         raise HTTPException(
# #             status_code=500,
# #             detail=f"Failed to regenerate profile: {str(e)}"
# #         )

# # @router.delete("/profile/clear-contaminated")
# # async def clear_contaminated_profile(current_user: str = Depends(get_current_user)):
# #     """Clear contaminated profile data"""
# #     try:
# #         db = get_firestore_client()
        
# #         # Delete the contaminated profile from all possible locations
# #         profile_doc_id = f"{current_user}_profile_structure.json"
        
# #         deleted_locations = []
        
# #         # Try deleting from multiple locations
# #         locations = [
# #             ("user_profiles", profile_doc_id),
# #             ("user_collection", profile_doc_id),
# #             ("interview_profiles", f"{current_user}_profile.json"),
# #         ]
        
# #         for collection_name, doc_name in locations:
# #             try:
# #                 doc_ref = db.collection(collection_name).document(doc_name)
# #                 if doc_ref.get().exists:
# #                     doc_ref.delete()
# #                     deleted_locations.append(f"{collection_name}/{doc_name}")
# #             except Exception as e:
# #                 print(f"Error deleting from {collection_name}/{doc_name}: {e}")
        
# #         return {
# #             "success": True,
# #             "message": f"Cleared contaminated profile for user {current_user}",
# #             "user_id": current_user,
# #             "deleted_locations": deleted_locations,
# #             "action": "profile_deleted"
# #         }
        
# #     except Exception as e:
# #         raise HTTPException(status_code=500, detail=str(e))

# # @router.post("/generate", response_model=RecommendationResponse)
# # async def generate_user_recommendations(
# #     request: RecommendationRequest,
# #     current_user: str = Depends(get_current_user)
# # ):
# #     """Generate recommendations based on available profile data (even if partial)"""
# #     try:
# #         start_time = datetime.utcnow()
# #         settings = get_settings()
# #         db = get_firestore_client()
        
# #         print(f"🚀 Generating recommendations for user: {current_user}")
# #         print(f"📝 Query: {request.query}")
        
# #         # Load profile (allow partial)
# #         user_profile = load_user_profile(current_user)
        
# #         # Handle serious contamination only
# #         if isinstance(user_profile, dict) and user_profile.get("error") == "contaminated_profile":
# #             validation = user_profile.get("validation", {})
# #             if validation.get("reason") in ["foreign_user_data_detected", "extensive_data_without_any_sessions"]:
# #                 raise HTTPException(
# #                     status_code=422,
# #                     detail={
# #                         "error": "contaminated_profile",
# #                         "message": "Cannot generate recommendations with contaminated profile data",
# #                         "recommended_action": "clear_profile_and_start_interview"
# #                     }
# #                 )
        
# #         # If no profile at all, create basic recommendations
# #         if not user_profile:
# #             print("⚠️ No profile found - generating basic recommendations")
# #             user_profile = {
# #                 "user_id": current_user,
# #                 "profile_completeness": "empty",
# #                 "generalprofile": {
# #                     "corePreferences": {
# #                         "note": "Basic profile - complete interview for personalized recommendations"
# #                     }
# #                 }
# #             }
        
# #         # Clean profile for AI processing
# #         clean_profile = {k: v for k, v in user_profile.items() if not k.startswith('_')}
# #         validation_summary = user_profile.get("_validation", {})
        
# #         # Adjust based on profile completeness
# #         profile_completeness = validation_summary.get("profile_completeness", "empty")
# #         questions_answered = validation_summary.get("total_questions_answered", 0)
        
# #         print(f"📊 Profile completeness: {profile_completeness}")
# #         print(f"📝 Questions answered: {questions_answered}")
        
# #         # Generate recommendations with context about profile completeness
# #         recs_json = generate_recommendations_with_context(
# #             clean_profile, 
# #             request.query, 
# #             settings.OPENAI_API_KEY,
# #             profile_completeness,
# #             questions_answered
# #         )
        
# #         try:
# #             recs = json.loads(recs_json)
            
# #             # Normalize to list
# #             if isinstance(recs, dict):
# #                 if "recommendations" in recs and isinstance(recs["recommendations"], list):
# #                     recs = recs["recommendations"]
# #                 else:
# #                     recs = [recs]
            
# #             if not isinstance(recs, list):
# #                 raise HTTPException(
# #                     status_code=500,
# #                     detail="Unexpected response format – expected a list of recommendations."
# #                 )
            
# #             # Calculate processing time
# #             processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
# #             # Add context about profile completeness to recommendations
# #             for rec in recs:
# #                 if profile_completeness in ["partial_in_progress", "partial_data_exists"]:
# #                     if "reasons" not in rec:
# #                         rec["reasons"] = []
# #                     rec["reasons"].append("Complete your interview for more personalized recommendations")
# #                 elif profile_completeness == "empty":
# #                     if "reasons" not in rec:
# #                         rec["reasons"] = []
# #                     rec["reasons"].append("Start an interview to get personalized recommendations")
            
# #             # Generate session ID for conversation tracking
# #             session_id = str(uuid.uuid4())
            
# #             # Save user query to conversation history
# #             save_conversation_message(
# #                 current_user, 
# #                 session_id, 
# #                 "user", 
# #                 f"Generate recommendations for: {request.query}", 
# #                 "recommendation",
# #                 f"Recommendation Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
# #             )
            
# #             # Prepare recommendation data for database
# #             recommendation_data = {
# #                 "user_id": current_user,
# #                 "query": request.query,
# #                 "category": request.category,
# #                 "recommendations": recs,
# #                 "processing_time_ms": int(processing_time),
# #                 "search_context": search_web(f"{request.query} recommendations 2024"),
# #                 "session_id": session_id,
# #                 "profile_version": clean_profile.get("version", "1.0"),
# #                 "profile_completeness": profile_completeness,
# #                 "questions_answered": questions_answered,
# #                 "user_specific": True
# #             }
            
# #             # Save to database
# #             recommendation_id = save_recommendation_to_db(recommendation_data, db)
            
# #             if not recommendation_id:
# #                 print("⚠️ Warning: Failed to save recommendation to database")
# #                 recommendation_id = str(uuid.uuid4())  # Fallback
            
# #             # Format recommendations for conversation history
# #             recs_text = f"Here are your recommendations"
# #             if profile_completeness != "empty":
# #                 recs_text += " based on your profile"
# #             recs_text += ":\n\n"
            
# #             for i, rec in enumerate(recs, 1):
# #                 recs_text += f"{i}. **{rec.get('title', 'Recommendation')}**\n"
# #                 recs_text += f"   {rec.get('description', rec.get('reason', 'No description provided'))}\n"
# #                 if 'reasons' in rec and isinstance(rec['reasons'], list):
# #                     for reason in rec['reasons']:
# #                         recs_text += f"   • {reason}\n"
# #                 recs_text += "\n"
            
# #             # Save recommendations to conversation history
# #             save_conversation_message(
# #                 current_user, 
# #                 session_id, 
# #                 "assistant", 
# #                 recs_text, 
# #                 "recommendation"
# #             )
            
# #             # Convert to RecommendationItem objects
# #             recommendation_items = []
# #             for rec in recs:
# #                 base_confidence = 0.6 if profile_completeness == "empty" else 0.8
# #                 confidence_score = rec.get('confidence_score', base_confidence)
                
# #                 recommendation_items.append(RecommendationItem(
# #                     title=rec.get('title', 'Recommendation'),
# #                     description=rec.get('description', rec.get('reason', '')),
# #                     reasons=rec.get('reasons', []),
# #                     category=request.category,
# #                     confidence_score=confidence_score
# #                 ))
            
# #             return RecommendationResponse(
# #                 recommendation_id=recommendation_id,
# #                 recommendations=recommendation_items,
# #                 query=request.query,
# #                 category=request.category,
# #                 user_id=current_user,
# #                 generated_at=datetime.utcnow(),
# #                 processing_time_ms=int(processing_time)
# #             )
            
# #         except json.JSONDecodeError as e:
# #             error_msg = f"Failed to parse recommendations: {str(e)}"
            
# #             # Save error to conversation history
# #             save_conversation_message(
# #                 current_user, 
# #                 str(uuid.uuid4()), 
# #                 "assistant", 
# #                 f"Sorry, I encountered an error generating recommendations: {error_msg}", 
# #                 "recommendation"
# #             )
            
# #             raise HTTPException(
# #                 status_code=500,
# #                 detail=error_msg
# #             )
            
# #     except HTTPException:
# #         raise
# #     except Exception as e:
# #         print(f"❌ Error generating recommendations for user {current_user}: {e}")
# #         raise HTTPException(
# #             status_code=500,
# #             detail=f"Failed to generate recommendations: {str(e)}"
# #         )

# # @router.post("/category")
# # async def generate_category_recommendations(
# #     request: RecommendationRequest,
# #     current_user: str = Depends(get_current_user)
# # ):
# #     """Generate category-specific recommendations - redirect to main generate endpoint"""
# #     # This now uses the enhanced generate endpoint
# #     return await generate_user_recommendations(request, current_user)

# # @router.post("/{recommendation_id}/feedback")
# # async def submit_recommendation_feedback(
# #     recommendation_id: str,
# #     feedback: RecommendationFeedback,
# #     current_user: str = Depends(get_current_user)
# # ):
# #     """Submit feedback for a recommendation"""
# #     try:
# #         db = get_firestore_client()
        
# #         # Verify recommendation exists and belongs to user
# #         rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
# #         if not rec_doc.exists:
# #             raise HTTPException(status_code=404, detail="Recommendation not found")
        
# #         # Save feedback
# #         feedback_data = {
# #             "feedback_type": feedback.feedback_type,
# #             "rating": feedback.rating,
# #             "comment": feedback.comment,
# #             "clicked_items": feedback.clicked_items
# #         }
        
# #         feedback_id = save_recommendation_feedback(recommendation_id, current_user, feedback_data, db)
        
# #         if not feedback_id:
# #             raise HTTPException(status_code=500, detail="Failed to save feedback")
        
# #         return {
# #             "success": True,
# #             "message": "Feedback submitted successfully",
# #             "feedback_id": feedback_id,
# #             "recommendation_id": recommendation_id
# #         }
        
# #     except Exception as e:
# #         raise HTTPException(
# #             status_code=500,
# #             detail=f"Failed to submit feedback: {str(e)}"
# #         )

# # @router.delete("/{recommendation_id}")
# # async def delete_recommendation(
# #     recommendation_id: str,
# #     current_user: str = Depends(get_current_user)
# # ):
# #     """Delete a recommendation from history"""
# #     try:
# #         db = get_firestore_client()
        
# #         # Verify recommendation exists and belongs to user
# #         rec_ref = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id)
# #         rec_doc = rec_ref.get()
        
# #         if not rec_doc.exists:
# #             raise HTTPException(status_code=404, detail="Recommendation not found")
        
# #         # Soft delete
# #         rec_ref.update({
# #             "is_active": False,
# #             "deleted_at": datetime.utcnow()
# #         })
        
# #         # Also update in recommendation_history
# #         try:
# #             db.collection("recommendation_history").document(recommendation_id).update({
# #                 "is_active": False,
# #                 "deleted_at": datetime.utcnow()
# #             })
# #         except:
# #             pass  # History record might not exist
        
# #         return {
# #             "success": True,
# #             "message": f"Recommendation {recommendation_id} deleted successfully"
# #         }
        
# #     except Exception as e:
# #         raise HTTPException(
# #             status_code=500,
# #             detail=f"Failed to delete recommendation: {str(e)}"
# #         )

# # # IMPORTANT: Put parameterized routes LAST to avoid route conflicts
# # @router.get("/{recommendation_id}")
# # async def get_recommendation_details(
# #     recommendation_id: str,
# #     current_user: str = Depends(get_current_user)
# # ):
# #     """Get detailed information about a specific recommendation"""
# #     try:
# #         db = get_firestore_client()
        
# #         # Get recommendation details
# #         rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
# #         if not rec_doc.exists:
# #             raise HTTPException(status_code=404, detail="Recommendation not found")
        
# #         rec_data = rec_doc.to_dict()
        
# #         # Increment view count
# #         current_views = rec_data.get("view_count", 0)
# #         rec_doc.reference.update({
# #             "view_count": current_views + 1,
# #             "last_viewed": datetime.utcnow()
# #         })
        
# #         # Get feedback for this recommendation
# #         feedback_query = db.collection("recommendation_feedback").where("recommendation_id", "==", recommendation_id).where("user_id", "==", current_user)
# #         feedback_docs = feedback_query.stream()
        
# #         feedback_list = []
# #         for feedback_doc in feedback_docs:
# #             feedback_data = feedback_doc.to_dict()
# #             feedback_list.append({
# #                 "feedback_id": feedback_data["feedback_id"],
# #                 "feedback_type": feedback_data["feedback_type"],
# #                 "rating": feedback_data.get("rating"),
# #                 "comment": feedback_data.get("comment"),
# #                 "created_at": feedback_data["created_at"]
# #             })
        
# #         return {
# #             "success": True,
# #             "recommendation": {
# #                 "recommendation_id": rec_data["recommendation_id"],
# #                 "query": rec_data["query"],
# #                 "category": rec_data.get("category"),
# #                 "recommendations": rec_data["recommendations"],
# #                 "generated_at": rec_data["generated_at"],
# #                 "processing_time_ms": rec_data.get("processing_time_ms"),
# #                 "view_count": current_views + 1,
# #                 "search_context": rec_data.get("search_context", []),
# #                 "profile_completeness": rec_data.get("profile_completeness", "unknown"),
# #                 "questions_answered": rec_data.get("questions_answered", 0)
# #             },
# #             "feedback": feedback_list,
# #             "user_id": current_user
# #         }
        
# #     except Exception as e:
# #         raise HTTPException(
# #             status_code=500,
# #             detail=f"Failed to get recommendation details: {str(e)}"
# #         )


# from fastapi import APIRouter, Depends, HTTPException, status, Query
# from pydantic import BaseModel
# from typing import Dict, Any, List, Optional
# import json
# from openai import OpenAI
# from duckduckgo_search import DDGS 
# from duckduckgo_search.exceptions import DuckDuckGoSearchException
# from itertools import islice
# import time
# import uuid
# from datetime import datetime, timedelta

# from app.core.security import get_current_user
# from app.core.firebase import get_firestore_client
# from app.core.config import get_settings
# from app.routers.conversations import save_conversation_message

# router = APIRouter()

# # Enhanced Pydantic models
# class RecommendationRequest(BaseModel):
#     query: str
#     category: Optional[str] = None
#     user_id: Optional[str] = None
#     context: Optional[Dict[str, Any]] = None

# class RecommendationItem(BaseModel):
#     title: str
#     description: Optional[str] = None
#     reasons: List[str] = []
#     category: Optional[str] = None
#     confidence_score: Optional[float] = None
#     external_links: Optional[List[str]] = None

# class RecommendationResponse(BaseModel):
#     recommendation_id: str
#     recommendations: List[RecommendationItem]
#     query: str
#     category: Optional[str] = None
#     user_id: str
#     generated_at: datetime
#     processing_time_ms: Optional[int] = None

# class RecommendationFeedback(BaseModel):
#     recommendation_id: str
#     feedback_type: str  # 'like', 'dislike', 'not_relevant', 'helpful'
#     rating: Optional[int] = None  # 1-5 stars
#     comment: Optional[str] = None
#     clicked_items: List[str] = []

# # Database helper functions
# def save_recommendation_to_db(recommendation_data: Dict[str, Any], db) -> str:
#     """Save recommendation to database and return recommendation_id"""
#     try:
#         recommendation_id = str(uuid.uuid4())
        
#         # Prepare data for database
#         db_data = {
#             "recommendation_id": recommendation_id,
#             "user_id": recommendation_data["user_id"],
#             "query": recommendation_data["query"],
#             "category": recommendation_data.get("category"),
#             "recommendations": recommendation_data["recommendations"],
#             "generated_at": datetime.utcnow(),
#             "processing_time_ms": recommendation_data.get("processing_time_ms"),
#             "search_context": recommendation_data.get("search_context", []),
#             "profile_version": recommendation_data.get("profile_version"),
#             "profile_completeness": recommendation_data.get("profile_completeness"),
#             "questions_answered": recommendation_data.get("questions_answered", 0),
#             "session_id": recommendation_data.get("session_id"),
#             "generation_method": recommendation_data.get("generation_method"),
#             "is_active": True,
#             "view_count": 0,
#             "feedback_count": 0
#         }
        
#         # Save to user-specific collection
#         db.collection("user_recommendations").document(recommendation_data["user_id"]).collection("recommendations").document(recommendation_id).set(db_data)
        
#         # Also save to recommendation history for analytics
#         history_data = {
#             "recommendation_id": recommendation_id,
#             "user_id": recommendation_data["user_id"],
#             "query": recommendation_data["query"],
#             "category": recommendation_data.get("category"),
#             "recommendations_count": len(recommendation_data["recommendations"]),
#             "profile_completeness": recommendation_data.get("profile_completeness"),
#             "created_at": datetime.utcnow(),
#             "is_bookmarked": False,
#             "tags": []
#         }
        
#         db.collection("recommendation_history").document(recommendation_id).set(history_data)
        
#         return recommendation_id
        
#     except Exception as e:
#         print(f"Error saving recommendation: {e}")
#         return None

# def get_user_recommendation_history(user_id: str, db, limit: int = 20, offset: int = 0, category: str = None):
#     """Get user's recommendation history from database"""
#     try:
#         query = db.collection("user_recommendations").document(user_id).collection("recommendations").where("is_active", "==", True)
        
#         if category:
#             query = query.where("category", "==", category)
        
#         recommendations = query.order_by("generated_at", direction="DESCENDING").limit(limit).offset(offset).stream()
        
#         history = []
#         for rec in recommendations:
#             rec_data = rec.to_dict()
#             history.append({
#                 "recommendation_id": rec_data["recommendation_id"],
#                 "query": rec_data["query"],
#                 "category": rec_data.get("category"),
#                 "recommendations_count": len(rec_data.get("recommendations", [])),
#                 "generated_at": rec_data["generated_at"],
#                 "view_count": rec_data.get("view_count", 0),
#                 "feedback_count": rec_data.get("feedback_count", 0),
#                 "session_id": rec_data.get("session_id"),
#                 "profile_completeness": rec_data.get("profile_completeness"),
#                 "generation_method": rec_data.get("generation_method")
#             })
        
#         return history
        
#     except Exception as e:
#         print(f"Error getting recommendation history: {e}")
#         return []

# def save_recommendation_feedback(recommendation_id: str, user_id: str, feedback_data: Dict[str, Any], db):
#     """Save user feedback for a recommendation"""
#     try:
#         feedback_id = str(uuid.uuid4())
        
#         feedback_doc = {
#             "feedback_id": feedback_id,
#             "recommendation_id": recommendation_id,
#             "user_id": user_id,
#             "feedback_type": feedback_data["feedback_type"],
#             "rating": feedback_data.get("rating"),
#             "comment": feedback_data.get("comment"),
#             "clicked_items": feedback_data.get("clicked_items", []),
#             "created_at": datetime.utcnow()
#         }
        
#         # Save feedback
#         db.collection("recommendation_feedback").document(feedback_id).set(feedback_doc)
        
#         # Update recommendation with feedback count
#         rec_ref = db.collection("user_recommendations").document(user_id).collection("recommendations").document(recommendation_id)
#         rec_doc = rec_ref.get()
        
#         if rec_doc.exists:
#             current_feedback_count = rec_doc.to_dict().get("feedback_count", 0)
#             rec_ref.update({"feedback_count": current_feedback_count + 1})
        
#         return feedback_id
        
#     except Exception as e:
#         print(f"Error saving feedback: {e}")
#         return None

# # PERMISSIVE Profile validation and loading functions
# def validate_profile_authenticity(profile_data: Dict[str, Any], user_id: str, db) -> Dict[str, Any]:
#     """Modified validation that allows partial profiles but detects contaminated data"""
    
#     if not profile_data or not user_id:
#         return {"valid": False, "reason": "empty_profile_or_user"}
    
#     validation_result = {
#         "valid": True,
#         "warnings": [],
#         "user_id": user_id,
#         "profile_sections": {},
#         "authenticity_score": 1.0,  # Start optimistic
#         "template_indicators": [],
#         "profile_completeness": "partial"
#     }
    
#     try:
#         # Check interview sessions for this user
#         interview_sessions = db.collection("interview_sessions").where("user_id", "==", user_id).stream()
        
#         completed_phases = set()
#         in_progress_phases = set()
#         session_data = {}
#         total_questions_answered = 0
#         has_any_session = False
        
#         for session in interview_sessions:
#             has_any_session = True
#             session_dict = session.to_dict()
#             session_data[session.id] = session_dict
            
#             phase = session_dict.get("current_phase", "unknown")
            
#             if session_dict.get("status") == "completed":
#                 completed_phases.add(phase)
#                 total_questions_answered += session_dict.get("questions_answered", 0)
#             elif session_dict.get("status") == "in_progress":
#                 in_progress_phases.add(phase)
#                 total_questions_answered += session_dict.get("questions_answered", 0)
        
#         validation_result["completed_phases"] = list(completed_phases)
#         validation_result["in_progress_phases"] = list(in_progress_phases)
#         validation_result["total_questions_answered"] = total_questions_answered
#         validation_result["has_any_session"] = has_any_session
#         validation_result["session_data"] = session_data
        
#         # Analyze profile sections
#         profile_sections = profile_data.get("recommendationProfiles", {})
#         general_profile = profile_data.get("generalprofile", {})
        
#         total_detailed_responses = 0
#         total_authenticated_responses = 0
#         total_foreign_responses = 0
#         template_indicators = []
        
#         # Check recommendation profiles
#         for section_name, section_data in profile_sections.items():
#             section_validation = {
#                 "has_data": bool(section_data),
#                 "has_session_for_phase": section_name in (completed_phases | in_progress_phases),
#                 "data_authenticity": "unknown",
#                 "detailed_response_count": 0,
#                 "authenticated_response_count": 0,
#                 "foreign_response_count": 0
#             }
            
#             if section_data and isinstance(section_data, dict):
#                 def analyze_responses(data, path=""):
#                     nonlocal total_detailed_responses, total_authenticated_responses, total_foreign_responses
                    
#                     if isinstance(data, dict):
#                         for key, value in data.items():
#                             current_path = f"{path}.{key}" if path else key
                            
#                             if isinstance(value, dict) and "value" in value:
#                                 response_value = value.get("value", "")
#                                 if isinstance(response_value, str) and len(response_value.strip()) > 10:
#                                     section_validation["detailed_response_count"] += 1
#                                     total_detailed_responses += 1
                                    
#                                     # Check authentication markers
#                                     if "user_id" in value and "updated_at" in value:
#                                         if value.get("user_id") == user_id:
#                                             section_validation["authenticated_response_count"] += 1
#                                             total_authenticated_responses += 1
#                                         else:
#                                             section_validation["foreign_response_count"] += 1
#                                             total_foreign_responses += 1
#                                             template_indicators.append(
#                                                 f"Foreign user data: {section_name}.{current_path} (from {value.get('user_id')})"
#                                             )
#                                     # If no auth markers, it could be legitimate new data or template
#                                     # We'll be more lenient here
                                
#                                 # Recursively check nested structures
#                                 if isinstance(value, dict):
#                                     analyze_responses(value, current_path)
                
#                 analyze_responses(section_data)
                
#                 # Determine authenticity for this section
#                 if section_validation["foreign_response_count"] > 0:
#                     section_validation["data_authenticity"] = "foreign_user_data"
#                 elif section_validation["detailed_response_count"] > 0:
#                     if section_validation["has_session_for_phase"]:
#                         section_validation["data_authenticity"] = "legitimate"
#                     elif section_validation["authenticated_response_count"] > 0:
#                         section_validation["data_authenticity"] = "authenticated_but_no_session"
#                     else:
#                         # This could be legitimate new data or template
#                         # Check if user has ANY interview activity
#                         if has_any_session:
#                             section_validation["data_authenticity"] = "possibly_legitimate"
#                         else:
#                             section_validation["data_authenticity"] = "suspicious_no_sessions"
#                             template_indicators.append(
#                                 f"Detailed data without any interview sessions: {section_name}"
#                             )
#                 else:
#                     section_validation["data_authenticity"] = "minimal_data"
            
#             validation_result["profile_sections"][section_name] = section_validation
        
#         # Check general profile
#         general_detailed_responses = 0
#         general_authenticated_responses = 0
        
#         def check_general_profile(data, path="generalprofile"):
#             nonlocal general_detailed_responses, general_authenticated_responses
            
#             if isinstance(data, dict):
#                 for key, value in data.items():
#                     current_path = f"{path}.{key}"
                    
#                     if isinstance(value, dict):
#                         if "value" in value and isinstance(value["value"], str) and len(value["value"].strip()) > 10:
#                             general_detailed_responses += 1
#                             if "user_id" in value and value.get("user_id") == user_id:
#                                 general_authenticated_responses += 1
#                         else:
#                             check_general_profile(value, current_path)
        
#         check_general_profile(general_profile)
        
#         # Calculate totals
#         total_responses_with_general = total_detailed_responses + general_detailed_responses
#         total_auth_with_general = total_authenticated_responses + general_authenticated_responses
        
#         # Calculate authenticity score (more lenient)
#         if total_responses_with_general > 0:
#             auth_ratio = total_auth_with_general / total_responses_with_general
#             session_factor = 1.0 if has_any_session else 0.3
#             foreign_penalty = min(total_foreign_responses / max(total_responses_with_general, 1), 0.8)
            
#             validation_result["authenticity_score"] = max(0.0, (auth_ratio * 0.6 + session_factor * 0.4) - foreign_penalty)
#         else:
#             validation_result["authenticity_score"] = 1.0
        
#         # Determine profile completeness
#         if len(completed_phases) > 0:
#             validation_result["profile_completeness"] = "complete"
#         elif has_any_session and total_questions_answered > 0:
#             validation_result["profile_completeness"] = "partial_in_progress"
#         elif total_responses_with_general > 0:
#             validation_result["profile_completeness"] = "partial_data_exists"
#         else:
#             validation_result["profile_completeness"] = "empty"
        
#         validation_result["template_indicators"] = template_indicators
#         validation_result["total_detailed_responses"] = total_responses_with_general
#         validation_result["total_authenticated_responses"] = total_auth_with_general
#         validation_result["total_foreign_responses"] = total_foreign_responses
        
#         # MODIFIED validation logic - more permissive
#         # Only mark as invalid for serious contamination issues
#         if total_foreign_responses > 0:
#             validation_result["valid"] = False
#             validation_result["reason"] = "foreign_user_data_detected"
#         elif total_responses_with_general > 10 and not has_any_session:
#             # Extensive data but no interview sessions at all - suspicious
#             validation_result["valid"] = False
#             validation_result["reason"] = "extensive_data_without_any_sessions"
#         elif validation_result["authenticity_score"] < 0.2:
#             # Very low authenticity score
#             validation_result["valid"] = False
#             validation_result["reason"] = "very_low_authenticity_score"
        
#         # Add diagnostics
#         validation_result["diagnostics"] = {
#             "has_interview_activity": has_any_session,
#             "questions_answered": total_questions_answered,
#             "data_to_session_ratio": total_responses_with_general / max(len(completed_phases | in_progress_phases), 1),
#             "authentication_percentage": (total_auth_with_general / max(total_responses_with_general, 1)) * 100,
#             "foreign_data_percentage": (total_foreign_responses / max(total_responses_with_general, 1)) * 100,
#             "profile_usability": "usable" if validation_result["valid"] else "needs_cleanup"
#         }
        
#         return validation_result
        
#     except Exception as e:
#         return {
#             "valid": False, 
#             "reason": "validation_error", 
#             "error": str(e)
#         }

# def load_user_profile(user_id: str = None) -> Dict[str, Any]:
#     """Load and validate USER-SPECIFIC profile from Firestore - matches Streamlit pattern"""
#     try:
#         db = get_firestore_client()
        
#         if not user_id:
#             print("❌ No user_id provided for profile loading")
#             return {}
        
#         print(f"🔍 Looking for profile for user: {user_id}")
        
#         # Try to find profile in multiple locations (same as Streamlit logic)
#         profile_locations = [
#             {
#                 "collection": "user_profiles",
#                 "document": f"{user_id}_profile_structure.json",
#                 "description": "Primary user_profiles collection"
#             },
#             {
#                 "collection": "user_collection", 
#                 "document": f"{user_id}_profile_structure.json",
#                 "description": "Fallback user_collection with user prefix"
#             },
#             {
#                 "collection": "user_collection",
#                 "document": "profile_strcuture.json",  # Matches Streamlit typo
#                 "description": "Streamlit default profile location"
#             },
#             {
#                 "collection": "interview_profiles",
#                 "document": f"{user_id}_profile.json", 
#                 "description": "Interview-generated profile"
#             },
#             {
#                 "collection": f"user_{user_id}",
#                 "document": "profile_structure.json",
#                 "description": "User-specific collection"
#             }
#         ]
        
#         raw_profile = None
#         profile_source = None
        
#         for location in profile_locations:
#             try:
#                 doc_ref = db.collection(location["collection"]).document(location["document"])
#                 doc = doc_ref.get()
                
#                 if doc.exists:
#                     raw_profile = doc.to_dict()
#                     profile_source = f"{location['collection']}/{location['document']}"
#                     print(f"✅ Found profile at: {profile_source}")
#                     break
                    
#             except Exception as e:
#                 print(f"❌ Error checking {location['description']}: {e}")
#                 continue
        
#         if not raw_profile:
#             print(f"❌ No profile found for user: {user_id}")
#             return {}
        
#         # Validate profile authenticity with permissive validation
#         validation = validate_profile_authenticity(raw_profile, user_id, db)
        
#         print(f"🔍 Profile validation result: {validation.get('valid')} - {validation.get('reason', 'OK')}")
#         print(f"🔍 Profile completeness: {validation.get('profile_completeness', 'unknown')}")
#         print(f"🔍 Questions answered: {validation.get('total_questions_answered', 0)}")
#         print(f"🔍 Authenticity score: {validation.get('authenticity_score', 0.0):.2f}")
        
#         if validation.get("warnings"):
#             print(f"⚠️ Profile warnings: {validation['warnings']}")
        
#         # Only reject for serious contamination
#         if not validation.get("valid"):
#             serious_issues = ["foreign_user_data_detected", "extensive_data_without_any_sessions"]
#             if validation.get("reason") in serious_issues:
#                 print(f"🚨 SERIOUS PROFILE ISSUE for user {user_id}: {validation.get('reason')}")
#                 return {
#                     "error": "contaminated_profile",
#                     "user_id": user_id,
#                     "validation": validation,
#                     "message": f"Profile validation failed: {validation.get('reason')}",
#                     "profile_source": profile_source
#                 }
#             else:
#                 print(f"⚠️ Minor profile issue for user {user_id}: {validation.get('reason')} - allowing with warnings")
        
#         # Return profile with validation info (even if partial)
#         profile_with_metadata = raw_profile.copy()
#         profile_with_metadata["_validation"] = validation
#         profile_with_metadata["_source"] = profile_source
        
#         return profile_with_metadata
        
#     except Exception as e:
#         print(f"❌ Error loading user profile for {user_id}: {e}")
#         return {}

# def search_web(query, max_results=3, max_retries=3, base_delay=1.0):
#     """Query DuckDuckGo via DDGS.text(), returning up to max_results items."""
#     for attempt in range(1, max_retries + 1):
#         try:
#             with DDGS() as ddgs:
#                 return list(islice(ddgs.text(query), max_results))
#         except DuckDuckGoSearchException as e:
#             msg = str(e)
#             if "202" in msg:
#                 wait = base_delay * (2 ** (attempt - 1))
#                 print(f"[search_web] Rate‑limited (202). Retry {attempt}/{max_retries} in {wait:.1f}s…")
#                 time.sleep(wait)
#             else:
#                 raise
#         except Exception as e:
#             print(f"[search_web] Unexpected error: {e}")
#             break
    
#     print(f"[search_web] Failed to fetch results after {max_retries} attempts.")
#     return []

# def generate_recommendations(user_profile, user_query, openai_key, category=None):
#     """Generate 3 personalized recommendations using user profile and web search - STREAMLIT COMPATIBLE"""
    
#     # Enhanced search with category context
#     if category:
#         search_query = f"{category} {user_query} recommendations 2024"
#     else:
#         search_query = f"{user_query} recommendations 2024"
    
#     search_results = search_web(search_query)
    
#     # Category-specific instructions
#     category_instructions = ""
#     if category:
#         category_lower = category.lower()
        
#         if category_lower in ["travel", "travel & destinations"]:
#             category_instructions = """
#             **CATEGORY FOCUS: TRAVEL & DESTINATIONS**
#             - Recommend specific destinations, attractions, or travel experiences
#             - Include practical travel advice (best time to visit, transportation, accommodations)
#             - Consider cultural experiences, local cuisine, historical sites, natural attractions
#             - Focus on places to visit, things to do, travel itineraries
#             - DO NOT recommend economic plans, political content, or business strategies
            
#             **EXAMPLE for Pakistan Travel Query**:
#             - "Hunza Valley, Pakistan" - Mountain valley with stunning landscapes
#             - "Lahore Food Street" - Culinary travel experience in historic city
#             - "Skardu Adventures" - Trekking and mountaineering destination
#             """
            
#         elif category_lower in ["movies", "movies & tv", "entertainment"]:
#             category_instructions = """
#             **CATEGORY FOCUS: MOVIES & TV**
#             - Recommend specific movies, TV shows, or streaming content
#             - Consider genres, directors, actors, themes that match user preferences
#             - Include where to watch (streaming platforms) if possible
#             - Focus on entertainment content, not travel or other categories
#             """
            
#         elif category_lower in ["food", "food & dining", "restaurants"]:
#             category_instructions = """
#             **CATEGORY FOCUS: FOOD & DINING**
#             - Recommend specific restaurants, cuisines, or food experiences
#             - Include local specialties, popular dishes, dining venues
#             - Consider user's location and dietary preferences
#             - Focus on food and dining experiences, not travel destinations
#             """
            
#         else:
#             category_instructions = f"""
#             **CATEGORY FOCUS: {category.upper()}**
#             - Focus recommendations specifically on {category} related content
#             - Ensure all suggestions are relevant to the {category} category
#             - Do not recommend content from other categories
#             """
    
#     prompt = f"""
#     **Task**: Generate exactly 3 highly personalized {category + ' ' if category else ''}recommendations based on:
    
#     {category_instructions}
    
#     **User Profile**:
#     {json.dumps(user_profile, indent=2)}
    
#     **User Query**:
#     "{user_query}"
    
#     **Web Context** (for reference only):
#     {search_results}
    
#     **Requirements**:
#     1. Each recommendation must directly reference profile details when available
#     2. ALL recommendations MUST be relevant to the "{category}" category if specified
#     3. Blend the user's core values and preferences from their profile
#     4. Only suggest what is asked for - no extra advice
#     5. For travel queries, recommend specific destinations, attractions, or experiences
#     6. Format as JSON array with each recommendation having:
#        - title: string (specific name of place/item/experience)
#        - description: string (brief description of what it is)
#        - reasons: array of strings (why it matches the user profile)
#        - confidence_score: float (0.0-1.0)
    
#     **CRITICAL for Travel Category**: 
#     If this is a travel recommendation, suggest actual destinations, attractions, restaurants, or travel experiences.
#     DO NOT suggest economic plans, political content, or business strategies.
    
#     **Output Example for Travel**:
#     [
#       {{
#          "title": "Hunza Valley, Pakistan",
#          "description": "Breathtaking mountain valley known for stunning landscapes and rich cultural heritage",
#          "reasons": ["Matches your love for natural beauty and cultural exploration", "Perfect for peaceful mountain retreats you prefer"],
#          "confidence_score": 0.9
#       }},
#       {{
#          "title": "Lahore Food Street, Pakistan", 
#          "description": "Historic food destination offering authentic Pakistani cuisine and cultural immersion",
#          "reasons": ["Aligns with your interest in trying traditional foods", "Offers the cultural experiences you enjoy"],
#          "confidence_score": 0.85
#       }},
#       {{
#          "title": "Skardu, Pakistan",
#          "description": "Adventure destination for trekking and mountaineering with stunning natural scenery",
#          "reasons": ["Perfect for your moderate adventure seeking preferences", "Offers the peaceful outdoor experiences you value"],
#          "confidence_score": 0.8
#       }}
#     ]
    
#     Generate your response in JSON format only.
#     """
    
#     # Setting up LLM - same as Streamlit pattern
#     client = OpenAI(api_key=openai_key)

#     response = client.chat.completions.create(
#         model="gpt-4",
#         messages=[
#             {"role": "system", "content": f"You're a recommendation engine that creates hyper-personalized {category.lower() if category else ''} suggestions. You MUST focus on {category.lower() if category else 'relevant'} content only. Output valid JSON only."},
#             {"role": "user", "content": prompt}
#         ],
#         temperature=0.7  
#     )
    
#     return response.choices[0].message.content

# # ROUTE DEFINITIONS - SPECIFIC ROUTES FIRST, PARAMETERIZED ROUTES LAST

# @router.get("/profile")
# async def get_user_profile(current_user: str = Depends(get_current_user)):
#     """Get the current user's profile - allows partial profiles"""
#     try:
#         print(f"🔍 Getting profile for user: {current_user}")
#         profile = load_user_profile(current_user)
        
#         # Handle contaminated profile (only for serious issues)
#         if isinstance(profile, dict) and profile.get("error") == "contaminated_profile":
#             validation_info = profile.get("validation", {})
            
#             # Check if it's a serious contamination or just partial data
#             if validation_info.get("reason") == "foreign_user_data_detected":
#                 raise HTTPException(
#                     status_code=422,
#                     detail={
#                         "error": "contaminated_profile",
#                         "message": "Profile contains data from other users",
#                         "user_id": current_user,
#                         "validation": validation_info,
#                         "recommended_action": "clear_contaminated_profile_and_restart_interview"
#                     }
#                 )
#             elif validation_info.get("reason") == "extensive_data_without_any_sessions":
#                 raise HTTPException(
#                     status_code=422,
#                     detail={
#                         "error": "suspicious_profile",
#                         "message": "Profile has extensive data but no interview sessions",
#                         "user_id": current_user,
#                         "validation": validation_info,
#                         "recommended_action": "start_interview_to_validate_or_clear_profile"
#                     }
#                 )
#             # For other validation issues, allow profile but with warnings
        
#         if not profile:
#             # Check interview status
#             db = get_firestore_client()
#             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#             sessions = list(sessions_ref.stream())
            
#             if not sessions:
#                 raise HTTPException(
#                     status_code=404,
#                     detail="No profile found. Please start an interview to begin creating your profile."
#                 )
            
#             # If there are sessions but no profile, suggest continuing
#             in_progress_sessions = [s for s in sessions if s.to_dict().get("status") == "in_progress"]
#             if in_progress_sessions:
#                 raise HTTPException(
#                     status_code=404,
#                     detail={
#                         "message": "Interview in progress but no profile generated yet. Continue the interview to build your profile.",
#                         "sessions": [{"session_id": s.id, "phase": s.to_dict().get("current_phase")} for s in in_progress_sessions]
#                     }
#                 )
        
#         # Return profile (even if partial)
#         clean_profile = {k: v for k, v in profile.items() if not k.startswith('_')}
#         validation_summary = profile.get("_validation", {})
        
#         response = {
#             "success": True,
#             "profile": clean_profile,
#             "user_id": current_user,
#             "profile_type": "user_specific",
#             "profile_found": True,
#             "profile_completeness": validation_summary.get("profile_completeness", "unknown"),
#             "validation_summary": {
#                 "valid": validation_summary.get("valid", True),
#                 "authenticity_score": validation_summary.get("authenticity_score", 1.0),
#                 "reason": validation_summary.get("reason"),
#                 "has_interview_activity": validation_summary.get("has_any_session", False),
#                 "questions_answered": validation_summary.get("total_questions_answered", 0),
#                 "total_responses": validation_summary.get("total_detailed_responses", 0),
#                 "authenticated_responses": validation_summary.get("total_authenticated_responses", 0),
#                 "completed_phases": validation_summary.get("completed_phases", []),
#                 "in_progress_phases": validation_summary.get("in_progress_phases", [])
#             },
#             "profile_source": profile.get("_source", "unknown")
#         }
        
#         # Add guidance based on completeness
#         # Add guidance based on completeness
#         if validation_summary.get("profile_completeness") == "partial_in_progress":
#             response["message"] = "Profile is being built as you answer interview questions. Continue the interview for more personalized recommendations."
#         elif validation_summary.get("profile_completeness") == "partial_data_exists":
#             response["message"] = "Profile has some data. Start or continue an interview to enhance personalization."
#         elif validation_summary.get("profile_completeness") == "complete":
#             response["message"] = "Profile is complete and ready for personalized recommendations."
#         elif validation_summary.get("profile_completeness") == "empty":
#             response["message"] = "Profile is empty. Start an interview to begin building your personalized profile."
        
#         return response
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"❌ Error in get_user_profile: {e}")
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to load profile: {str(e)}"
#         )

# @router.get("/categories")
# async def get_recommendation_categories():
#     """Get available recommendation categories"""
#     categories = [
#         {
#             "id": "movies",
#             "name": "Movies & TV",
#             "description": "Movie and TV show recommendations",
#             "questions_file": "moviesAndTV_tiered_questions.json"
#         },
#         {
#             "id": "food",
#             "name": "Food & Dining",
#             "description": "Restaurant and food recommendations",
#             "questions_file": "foodAndDining_tiered_questions.json"
#         },
#         {
#             "id": "travel",
#             "name": "Travel",
#             "description": "Travel destination recommendations",
#             "questions_file": "travel_tiered_questions.json"
#         },
#         {
#             "id": "books",
#             "name": "Books & Reading",
#             "description": "Book recommendations",
#             "questions_file": "books_tiered_questions.json"
#         },
#         {
#             "id": "music",
#             "name": "Music",
#             "description": "Music and artist recommendations",
#             "questions_file": "music_tiered_questions.json"
#         },
#         {
#             "id": "fitness",
#             "name": "Fitness & Wellness",
#             "description": "Fitness and wellness recommendations",
#             "questions_file": "fitness_tiered_questions.json"
#         }
#     ]
    
#     return {
#         "categories": categories,
#         "default_category": "movies"
#     }

# @router.get("/history")
# async def get_recommendation_history(
#     current_user: str = Depends(get_current_user),
#     limit: int = Query(20, description="Number of recommendations to return"),
#     offset: int = Query(0, description="Number of recommendations to skip"),
#     category: Optional[str] = Query(None, description="Filter by category"),
#     date_from: Optional[datetime] = Query(None, description="Filter from date"),
#     date_to: Optional[datetime] = Query(None, description="Filter to date")
# ):
#     """Get recommendation history for the user with enhanced filtering"""
#     try:
#         db = get_firestore_client()
        
#         # Simplified query to avoid index issues - just get user's recommendations
#         query = db.collection("user_recommendations").document(current_user).collection("recommendations")
#         query = query.where("is_active", "==", True)
#         query = query.limit(limit).offset(offset)
        
#         # Get all recommendations (without complex ordering initially)
#         recommendations = list(query.stream())
        
#         # Filter and sort in Python instead of Firestore
#         filtered_recs = []
#         for rec in recommendations:
#             rec_data = rec.to_dict()
            
#             # Apply category filter
#             if category and rec_data.get("category") != category:
#                 continue
            
#             # Apply date filters
#             rec_date = rec_data.get("generated_at")
#             if date_from and rec_date and rec_date < date_from:
#                 continue
#             if date_to and rec_date and rec_date > date_to:
#                 continue
            
#             filtered_recs.append(rec_data)
        
#         # Sort by generated_at descending
#         filtered_recs.sort(key=lambda x: x.get("generated_at", datetime.min), reverse=True)
        
#         # Format response
#         history = []
#         for rec_data in filtered_recs:
#             history.append({
#                 "recommendation_id": rec_data["recommendation_id"],
#                 "query": rec_data["query"],
#                 "category": rec_data.get("category"),
#                 "recommendations_count": len(rec_data.get("recommendations", [])),
#                 "generated_at": rec_data["generated_at"],
#                 "view_count": rec_data.get("view_count", 0),
#                 "feedback_count": rec_data.get("feedback_count", 0),
#                 "session_id": rec_data.get("session_id"),
#                 "processing_time_ms": rec_data.get("processing_time_ms"),
#                 "profile_completeness": rec_data.get("profile_completeness", "unknown"),
#                 "generation_method": rec_data.get("generation_method", "unknown")
#             })
        
#         return {
#             "success": True,
#             "history": history,
#             "total_count": len(history),
#             "user_id": current_user,
#             "filters": {
#                 "category": category,
#                 "date_from": date_from,
#                 "date_to": date_to,
#                 "limit": limit,
#                 "offset": offset
#             },
#             "note": "Using simplified query to avoid Firebase index requirements"
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to get recommendation history: {str(e)}"
#         )

# @router.get("/analytics/summary")
# async def get_recommendation_analytics(
#     current_user: str = Depends(get_current_user),
#     days: int = Query(30, description="Number of days to analyze")
# ):
#     """Get recommendation analytics for the user"""
#     try:
#         db = get_firestore_client()
        
#         # Calculate date range
#         end_date = datetime.utcnow()
#         start_date = end_date - timedelta(days=days)
        
#         # Get recommendations - simplified query
#         recommendations_ref = db.collection("user_recommendations").document(current_user).collection("recommendations")
#         recommendations = recommendations_ref.where("is_active", "==", True).stream()
        
#         analytics = {
#             "total_recommendations": 0,
#             "categories_explored": set(),
#             "query_types": {},
#             "total_views": 0,
#             "total_feedback": 0,
#             "average_processing_time": 0,
#             "recommendations_by_day": {},
#             "most_popular_category": None,
#             "engagement_rate": 0,
#             "profile_completeness_breakdown": {},
#             "generation_method_breakdown": {}
#         }
        
#         processing_times = []
#         daily_counts = {}
#         category_counts = {}
#         completeness_counts = {}
#         method_counts = {}
        
#         for rec in recommendations:
#             rec_data = rec.to_dict()
            
#             # Filter by date range
#             rec_date = rec_data.get("generated_at")
#             if rec_date and rec_date < start_date:
#                 continue
                
#             analytics["total_recommendations"] += 1
            
#             # Track categories
#             category = rec_data.get("category", "general")
#             analytics["categories_explored"].add(category)
#             category_counts[category] = category_counts.get(category, 0) + 1
            
#             # Track profile completeness
#             completeness = rec_data.get("profile_completeness", "unknown")
#             completeness_counts[completeness] = completeness_counts.get(completeness, 0) + 1
            
#             # Track generation method
#             method = rec_data.get("generation_method", "unknown")
#             method_counts[method] = method_counts.get(method, 0) + 1
            
#             # Track views and feedback
#             analytics["total_views"] += rec_data.get("view_count", 0)
#             analytics["total_feedback"] += rec_data.get("feedback_count", 0)
            
#             # Track processing times
#             if rec_data.get("processing_time_ms"):
#                 processing_times.append(rec_data["processing_time_ms"])
            
#             # Track daily activity
#             if rec_date:
#                 if hasattr(rec_date, 'date'):
#                     date_str = rec_date.date().isoformat()
#                 else:
#                     date_str = datetime.fromisoformat(str(rec_date)).date().isoformat()
                
#                 daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
        
#         # Calculate averages and insights
#         if analytics["total_recommendations"] > 0:
#             analytics["engagement_rate"] = round((analytics["total_views"] / analytics["total_recommendations"]) * 100, 2)
        
#         if processing_times:
#             analytics["average_processing_time"] = round(sum(processing_times) / len(processing_times), 2)
        
#         if category_counts:
#             analytics["most_popular_category"] = max(category_counts, key=category_counts.get)
        
#         analytics["categories_explored"] = list(analytics["categories_explored"])
#         analytics["recommendations_by_day"] = daily_counts
#         analytics["category_breakdown"] = category_counts
#         analytics["profile_completeness_breakdown"] = completeness_counts
#         analytics["generation_method_breakdown"] = method_counts
        
#         return {
#             "success": True,
#             "analytics": analytics,
#             "period": {
#                 "start_date": start_date.isoformat(),
#                 "end_date": end_date.isoformat(),
#                 "days": days
#             },
#             "user_id": current_user
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to get recommendation analytics: {str(e)}"
#         )

# @router.get("/debug/profile-location")
# async def debug_profile_location(current_user: str = Depends(get_current_user)):
#     """Debug endpoint to check where user profile is stored and validate it"""
#     try:
#         db = get_firestore_client()
        
#         locations_checked = {
#             "user_profiles": False,
#             "user_collection": False,
#             "interview_profiles": False,
#             "user_specific_collection": False,
#             "streamlit_default": False,
#             "fallback_locations": {}
#         }
        
#         profile_sources = []
        
#         # Check primary location
#         profile_doc_id = f"{current_user}_profile_structure.json"
        
#         # Check user_profiles collection
#         try:
#             profile_doc = db.collection("user_profiles").document(profile_doc_id).get()
#             locations_checked["user_profiles"] = profile_doc.exists
#             if profile_doc.exists:
#                 profile_sources.append({
#                     "location": f"user_profiles/{profile_doc_id}",
#                     "data_preview": str(profile_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["user_profiles"] = f"Error: {e}"
        
#         # Check user_collection fallback
#         try:
#             fallback_doc = db.collection("user_collection").document(profile_doc_id).get()
#             locations_checked["user_collection"] = fallback_doc.exists
#             if fallback_doc.exists:
#                 profile_sources.append({
#                     "location": f"user_collection/{profile_doc_id}",
#                     "data_preview": str(fallback_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["user_collection"] = f"Error: {e}"
        
#         # Check Streamlit default location (matches typo)
#         try:
#             streamlit_doc = db.collection("user_collection").document("profile_strcuture.json").get()
#             locations_checked["streamlit_default"] = streamlit_doc.exists
#             if streamlit_doc.exists:
#                 profile_sources.append({
#                     "location": "user_collection/profile_strcuture.json",
#                     "data_preview": str(streamlit_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["streamlit_default"] = f"Error: {e}"
        
#         # Check interview_profiles
#         try:
#             interview_doc = db.collection("interview_profiles").document(f"{current_user}_profile.json").get()
#             locations_checked["interview_profiles"] = interview_doc.exists
#             if interview_doc.exists:
#                 profile_sources.append({
#                     "location": f"interview_profiles/{current_user}_profile.json",
#                     "data_preview": str(interview_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["interview_profiles"] = f"Error: {e}"
        
#         # Check user-specific collection
#         try:
#             user_specific_doc = db.collection(f"user_{current_user}").document("profile_structure.json").get()
#             locations_checked["user_specific_collection"] = user_specific_doc.exists
#             if user_specific_doc.exists:
#                 profile_sources.append({
#                     "location": f"user_{current_user}/profile_structure.json",
#                     "data_preview": str(user_specific_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["user_specific_collection"] = f"Error: {e}"
        
#         # Check other possible locations
#         possible_docs = [
#             ("user_collection", "profile_structure.json"),
#             ("user_collection", f"{current_user}_profile.json"),
#             ("profiles", f"{current_user}.json"),
#             ("user_data", f"{current_user}_profile.json")
#         ]
        
#         for collection_name, doc_name in possible_docs:
#             try:
#                 doc_exists = db.collection(collection_name).document(doc_name).get().exists
#                 locations_checked["fallback_locations"][f"{collection_name}/{doc_name}"] = doc_exists
#                 if doc_exists:
#                     profile_sources.append({
#                         "location": f"{collection_name}/{doc_name}",
#                         "data_preview": "Found but not retrieved"
#                     })
#             except Exception as e:
#                 locations_checked["fallback_locations"][f"{collection_name}/{doc_name}"] = f"Error: {e}"
        
#         # Get interview session info
#         interview_sessions = []
#         try:
#             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#             for session in sessions_ref.stream():
#                 session_data = session.to_dict()
#                 interview_sessions.append({
#                     "session_id": session.id,
#                     "status": session_data.get("status"),
#                     "phase": session_data.get("current_phase"),
#                     "tier": session_data.get("current_tier"),
#                     "questions_answered": session_data.get("questions_answered", 0),
#                     "created_at": session_data.get("created_at"),
#                     "updated_at": session_data.get("updated_at")
#                 })
#         except Exception as e:
#             interview_sessions = [{"error": str(e)}]
        
#         # Test the current profile loading function
#         test_profile = load_user_profile(current_user)
#         profile_validation = None
        
#         if test_profile:
#             if test_profile.get("error"):
#                 profile_validation = {
#                     "status": "error",
#                     "error_type": test_profile.get("error"),
#                     "validation_details": test_profile.get("validation", {})
#                 }
#             else:
#                 profile_validation = {
#                     "status": "loaded",
#                     "validation_summary": test_profile.get("_validation", {}),
#                     "source": test_profile.get("_source", "unknown")
#                 }
        
#         return {
#             "success": True,
#             "user_id": current_user,
#             "locations_checked": locations_checked,
#             "profile_sources_found": profile_sources,
#             "expected_document": profile_doc_id,
#             "streamlit_compatible_search": True,
#             "interview_sessions": interview_sessions,
#             "profile_load_test": profile_validation,
#             "collections_searched": [
#                 "user_profiles", "user_collection", "interview_profiles", 
#                 f"user_{current_user}", "profiles", "user_data"
#             ]
#         }
        
#     except Exception as e:
#         return {
#             "success": False,
#             "error": str(e),
#             "user_id": current_user
#         }

# @router.post("/profile/regenerate")
# async def regenerate_user_profile(current_user: str = Depends(get_current_user)):
#     """Regenerate user profile from completed interview sessions"""
#     try:
#         db = get_firestore_client()
        
#         # Get all interview sessions for user (both completed and in-progress)
#         sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#         all_sessions = list(sessions_ref.stream())
        
#         completed_sessions = [s for s in all_sessions if s.to_dict().get("status") == "completed"]
#         in_progress_sessions = [s for s in all_sessions if s.to_dict().get("status") == "in_progress"]
        
#         if not completed_sessions and not in_progress_sessions:
#             raise HTTPException(
#                 status_code=400,
#                 detail="No interview sessions found. Start an interview first."
#             )
        
#         # TODO: Implement profile regeneration logic based on actual user responses
#         # This would involve:
#         # 1. Extracting responses from interview sessions
#         # 2. Building a clean profile structure
#         # 3. Saving to appropriate profile collection
        
#         return {
#             "success": True,
#             "message": "Profile regeneration initiated",
#             "user_id": current_user,
#             "completed_sessions": len(completed_sessions),
#             "in_progress_sessions": len(in_progress_sessions),
#             "note": "Profile regeneration logic needs to be implemented"
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to regenerate profile: {str(e)}"
#         )

# @router.delete("/profile/clear-contaminated")
# async def clear_contaminated_profile(current_user: str = Depends(get_current_user)):
#     """Clear contaminated profile data"""
#     try:
#         db = get_firestore_client()
        
#         # Delete the contaminated profile from all possible locations
#         profile_doc_id = f"{current_user}_profile_structure.json"
        
#         deleted_locations = []
        
#         # Try deleting from multiple locations
#         locations = [
#             ("user_profiles", profile_doc_id),
#             ("user_collection", profile_doc_id),
#             ("user_collection", "profile_strcuture.json"),  # Streamlit default
#             ("interview_profiles", f"{current_user}_profile.json"),
#         ]
        
#         for collection_name, doc_name in locations:
#             try:
#                 doc_ref = db.collection(collection_name).document(doc_name)
#                 if doc_ref.get().exists:
#                     doc_ref.delete()
#                     deleted_locations.append(f"{collection_name}/{doc_name}")
#             except Exception as e:
#                 print(f"Error deleting from {collection_name}/{doc_name}: {e}")
        
#         return {
#             "success": True,
#             "message": f"Cleared contaminated profile for user {current_user}",
#             "user_id": current_user,
#             "deleted_locations": deleted_locations,
#             "action": "profile_deleted"
#         }
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/generate", response_model=RecommendationResponse)
# async def generate_user_recommendations(
#     request: RecommendationRequest,
#     current_user: str = Depends(get_current_user)
# ):
#     """Generate recommendations using the same logic as Streamlit but enhanced for FastAPI"""
#     try:
#         start_time = datetime.utcnow()
#         settings = get_settings()
#         db = get_firestore_client()
        
#         print(f"🚀 Generating recommendations for user: {current_user}")
#         print(f"📝 Query: {request.query}")
#         print(f"🏷️ Category: {request.category}")
        
#         # Load profile (same as Streamlit)
#         user_profile = load_user_profile(current_user)
        
#         # Handle serious contamination only
#         if isinstance(user_profile, dict) and user_profile.get("error") == "contaminated_profile":
#             validation = user_profile.get("validation", {})
#             if validation.get("reason") in ["foreign_user_data_detected", "extensive_data_without_any_sessions"]:
#                 raise HTTPException(
#                     status_code=422,
#                     detail={
#                         "error": "contaminated_profile",
#                         "message": "Cannot generate recommendations with contaminated profile data",
#                         "recommended_action": "clear_profile_and_start_interview"
#                     }
#                 )
        
#         # If no profile, check if we should allow basic recommendations (same as Streamlit)
#         if not user_profile:
#             print("⚠️ No profile found - checking interview status")
            
#             # Check if user has any interview activity
#             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#             sessions = list(sessions_ref.stream())
            
#             if not sessions:
#                 # No interview started - create minimal profile for basic recommendations
#                 print("📝 No interview sessions - creating basic profile for general recommendations")
#                 user_profile = {
#                     "user_id": current_user,
#                     "generalprofile": {
#                         "corePreferences": {
#                             "note": "Basic profile - complete interview for personalized recommendations"
#                         }
#                     },
#                     "profile_completeness": "empty"
#                 }
#             else:
#                 # Has interview activity but no profile - this shouldn't happen
#                 raise HTTPException(
#                     status_code=404,
#                     detail="Interview sessions found but no profile generated. Please contact support."
#                 )
        
#         # Clean profile for AI processing (remove metadata)
#         clean_profile = {k: v for k, v in user_profile.items() if not k.startswith('_')}
        
#         # Get profile completeness info
#         validation_summary = user_profile.get("_validation", {})
#         profile_completeness = validation_summary.get("profile_completeness", "unknown")
#         questions_answered = validation_summary.get("total_questions_answered", 0)
        
#         print(f"📊 Profile completeness: {profile_completeness}")
#         print(f"📝 Questions answered: {questions_answered}")
        
#         # Generate recommendations using same function as Streamlit but with category
#         recs_json = generate_recommendations(
#             clean_profile, 
#             request.query, 
#             settings.OPENAI_API_KEY,
#             request.category  # Add category parameter
#         )
        
#         try:
#             recs = json.loads(recs_json)
            
#             # Normalize to list (same as Streamlit)
#             if isinstance(recs, dict):
#                 if "recommendations" in recs and isinstance(recs["recommendations"], list):
#                     recs = recs["recommendations"]
#                 else:
#                     recs = [recs]
            
#             if not isinstance(recs, list):
#                 raise HTTPException(
#                     status_code=500,
#                     detail="Unexpected response format – expected a list of recommendations."
#                 )
            
#             # Validate category relevance for travel
#             if request.category and request.category.lower() == "travel":
#                 travel_keywords = ["destination", "place", "visit", "travel", "city", "country", "attraction", "trip", "valley", "mountain", "beach", "street", "food", "culture", "heritage", "adventure", "pakistan", "hunza", "lahore", "skardu"]
                
#                 for i, rec in enumerate(recs):
#                     title_and_desc = (rec.get('title', '') + ' ' + rec.get('description', '')).lower()
#                     if not any(keyword in title_and_desc for keyword in travel_keywords):
#                         print(f"⚠️ Recommendation {i+1} '{rec.get('title')}' may not be travel-related")
#                         print(f"🔍 Content: {title_and_desc[:100]}...")
            
#             # Calculate processing time
#             processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
#             # Add profile completion guidance (like Streamlit would)
#             for rec in recs:
#                 if profile_completeness in ["partial_in_progress", "partial_data_exists", "empty"]:
#                     if "reasons" not in rec:
#                         rec["reasons"] = []
#                     if profile_completeness == "empty":
#                         rec["reasons"].append("Start the interview to get more personalized recommendations")
#                     else:
#                         rec["reasons"].append("Complete more interview questions for better personalization")
            
#             # Generate session ID for conversation tracking
#             session_id = str(uuid.uuid4())
            
#             # Save conversation messages (like Streamlit chat)
#             save_conversation_message(
#                 current_user, 
#                 session_id, 
#                 "user", 
#                 f"What would you like {request.category.lower() if request.category else ''} recommendations for? {request.query}", 
#                 "recommendation",
#                 f"{request.category or 'General'} Recommendation Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
#             )
            
#             # Prepare recommendation data for database
#             recommendation_data = {
#                 "user_id": current_user,
#                 "query": request.query,
#                 "category": request.category,
#                 "recommendations": recs,
#                 "processing_time_ms": int(processing_time),
#                 "search_context": search_web(f"{request.category} {request.query} recommendations 2024" if request.category else f"{request.query} recommendations 2024"),
#                 "session_id": session_id,
#                 "profile_version": clean_profile.get("version", "1.0"),
#                 "profile_completeness": profile_completeness,
#                 "questions_answered": questions_answered,
#                 "user_specific": True,
#                 "generation_method": "streamlit_compatible"
#             }
            
#             # Save to database
#             recommendation_id = save_recommendation_to_db(recommendation_data, db)
            
#             if not recommendation_id:
#                 print("⚠️ Warning: Failed to save recommendation to database")
#                 recommendation_id = str(uuid.uuid4())  # Fallback
            
#             # Format recommendations for conversation history (like Streamlit display)
#             recs_text = f"Here are your {request.category.lower() if request.category else ''} recommendations:\n\n"
            
#             for i, rec in enumerate(recs, 1):
#                 title = rec.get("title", "<no title>")
#                 description = rec.get("description", rec.get("reason", "<no description>"))
#                 reasons = rec.get("reasons", [])
                
#                 recs_text += f"**{i}. {title}**\n"
#                 recs_text += f"{description}\n"
#                 if reasons:
#                     for reason in reasons:
#                         recs_text += f"• {reason}\n"
#                 recs_text += "\n"
            
#             # Save recommendations to conversation history
#             save_conversation_message(
#                 current_user, 
#                 session_id, 
#                 "assistant", 
#                 recs_text, 
#                 "recommendation"
#             )
            
#             # Convert to RecommendationItem objects
#             recommendation_items = []
#             for rec in recs:
#                 # Use confidence score from AI or default based on profile completeness
#                 confidence_score = rec.get('confidence_score', 0.6 if profile_completeness == "empty" else 0.8)
                
#                 recommendation_items.append(RecommendationItem(
#                     title=rec.get('title', 'Recommendation'),
#                     description=rec.get('description', rec.get('reason', '')),
#                     reasons=rec.get('reasons', []),
#                     category=request.category,
#                     confidence_score=confidence_score
#                 ))
            
#             return RecommendationResponse(
#                 recommendation_id=recommendation_id,
#                 recommendations=recommendation_items,
#                 query=request.query,
#                 category=request.category,
#                 user_id=current_user,
#                 generated_at=datetime.utcnow(),
#                 processing_time_ms=int(processing_time)
#             )
            
#         except json.JSONDecodeError as e:
#             error_msg = f"Failed to parse recommendations: {str(e)}"
#             print(f"❌ JSON parsing error: {error_msg}")
#             print(f"🔍 Raw AI response: {recs_json[:500]}...")
            
#             # Save error to conversation history
#             save_conversation_message(
#                 current_user, 
#                 str(uuid.uuid4()), 
#                 "assistant", 
#                 f"Sorry, I encountered an error generating {request.category or ''} recommendations: {error_msg}", 
#                 "recommendation"
#             )
            
#             raise HTTPException(
#                 status_code=500,
#                 detail=error_msg
#             )
            
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"❌ Error generating recommendations for user {current_user}: {e}")
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to generate {request.category or ''} recommendations: {str(e)}"
#         )

# @router.post("/category")
# async def generate_category_recommendations(
#     request: RecommendationRequest,
#     current_user: str = Depends(get_current_user)
# ):
#     """Generate category-specific recommendations - redirect to main generate endpoint"""
#     # This now uses the enhanced generate endpoint
#     return await generate_user_recommendations(request, current_user)

# @router.post("/{recommendation_id}/feedback")
# async def submit_recommendation_feedback(
#     recommendation_id: str,
#     feedback: RecommendationFeedback,
#     current_user: str = Depends(get_current_user)
# ):
#     """Submit feedback for a recommendation"""
#     try:
#         db = get_firestore_client()
        
#         # Verify recommendation exists and belongs to user
#         rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
#         if not rec_doc.exists:
#             raise HTTPException(status_code=404, detail="Recommendation not found")
        
#         # Save feedback
#         feedback_data = {
#             "feedback_type": feedback.feedback_type,
#             "rating": feedback.rating,
#             "comment": feedback.comment,
#             "clicked_items": feedback.clicked_items
#         }
        
#         feedback_id = save_recommendation_feedback(recommendation_id, current_user, feedback_data, db)
        
#         if not feedback_id:
#             raise HTTPException(status_code=500, detail="Failed to save feedback")
        
#         return {
#             "success": True,
#             "message": "Feedback submitted successfully",
#             "feedback_id": feedback_id,
#             "recommendation_id": recommendation_id
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to submit feedback: {str(e)}"
#         )

# @router.delete("/{recommendation_id}")
# async def delete_recommendation(
#     recommendation_id: str,
#     current_user: str = Depends(get_current_user)
# ):
#     """Delete a recommendation from history"""
#     try:
#         db = get_firestore_client()
        
#         # Verify recommendation exists and belongs to user
#         rec_ref = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id)
#         rec_doc = rec_ref.get()
        
#         if not rec_doc.exists:
#             raise HTTPException(status_code=404, detail="Recommendation not found")
        
#         # Soft delete
#         rec_ref.update({
#             "is_active": False,
#             "deleted_at": datetime.utcnow()
#         })
        
#         # Also update in recommendation_history
#         try:
#             db.collection("recommendation_history").document(recommendation_id).update({
#                 "is_active": False,
#                 "deleted_at": datetime.utcnow()
#             })
#         except:
#             pass  # History record might not exist
        
#         return {
#             "success": True,
#             "message": f"Recommendation {recommendation_id} deleted successfully"
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to delete recommendation: {str(e)}"
#         )

# # IMPORTANT: Put parameterized routes LAST to avoid route conflicts
# @router.get("/{recommendation_id}")
# async def get_recommendation_details(
#     recommendation_id: str,
#     current_user: str = Depends(get_current_user)
# ):
#     """Get detailed information about a specific recommendation"""
#     try:
#         db = get_firestore_client()
        
#         # Get recommendation details
#         rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
#         if not rec_doc.exists:
#             raise HTTPException(status_code=404, detail="Recommendation not found")
        
#         rec_data = rec_doc.to_dict()
        
#         # Increment view count
#         current_views = rec_data.get("view_count", 0)
#         rec_doc.reference.update({
#             "view_count": current_views + 1,
#             "last_viewed": datetime.utcnow()
#         })
        
#         # Get feedback for this recommendation
#         feedback_query = db.collection("recommendation_feedback").where("recommendation_id", "==", recommendation_id).where("user_id", "==", current_user)
#         feedback_docs = feedback_query.stream()
        
#         feedback_list = []
#         for feedback_doc in feedback_docs:
#             feedback_data = feedback_doc.to_dict()
#             feedback_list.append({
#                 "feedback_id": feedback_data["feedback_id"],
#                 "feedback_type": feedback_data["feedback_type"],
#                 "rating": feedback_data.get("rating"),
#                 "comment": feedback_data.get("comment"),
#                 "created_at": feedback_data["created_at"]
#             })
        
#         return {
#             "success": True,
#             "recommendation": {
#                 "recommendation_id": rec_data["recommendation_id"],
#                 "query": rec_data["query"],
#                 "category": rec_data.get("category"),
#                 "recommendations": rec_data["recommendations"],
#                 "generated_at": rec_data["generated_at"],
#                 "processing_time_ms": rec_data.get("processing_time_ms"),
#                 "view_count": current_views + 1,
#                 "search_context": rec_data.get("search_context", []),
#                 "profile_completeness": rec_data.get("profile_completeness", "unknown"),
#                 "questions_answered": rec_data.get("questions_answered", 0),
#                 "generation_method": rec_data.get("generation_method", "unknown")
#             },
#             "feedback": feedback_list,
#             "user_id": current_user
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to get recommendation details: {str(e)}"
#         )from fastapi import APIRouter, Depends, HTTPException, status, Query
# from pydantic import BaseModel
# from typing import Dict, Any, List, Optional
# import json
# from openai import OpenAI
# from duckduckgo_search import DDGS 
# from duckduckgo_search.exceptions import DuckDuckGoSearchException
# from itertools import islice
# import time
# import uuid
# from datetime import datetime, timedelta

# from app.core.security import get_current_user
# from app.core.firebase import get_firestore_client
# from app.core.config import get_settings
# from app.routers.conversations import save_conversation_message

# router = APIRouter()

# # Enhanced Pydantic models
# class RecommendationRequest(BaseModel):
#     query: str
#     category: Optional[str] = None
#     user_id: Optional[str] = None
#     context: Optional[Dict[str, Any]] = None

# class RecommendationItem(BaseModel):
#     title: str
#     description: Optional[str] = None
#     reasons: List[str] = []
#     category: Optional[str] = None
#     confidence_score: Optional[float] = None
#     external_links: Optional[List[str]] = None

# class RecommendationResponse(BaseModel):
#     recommendation_id: str
#     recommendations: List[RecommendationItem]
#     query: str
#     category: Optional[str] = None
#     user_id: str
#     generated_at: datetime
#     processing_time_ms: Optional[int] = None

# class RecommendationFeedback(BaseModel):
#     recommendation_id: str
#     feedback_type: str  # 'like', 'dislike', 'not_relevant', 'helpful'
#     rating: Optional[int] = None  # 1-5 stars
#     comment: Optional[str] = None
#     clicked_items: List[str] = []

# # Database helper functions
# def save_recommendation_to_db(recommendation_data: Dict[str, Any], db) -> str:
#     """Save recommendation to database and return recommendation_id"""
#     try:
#         recommendation_id = str(uuid.uuid4())
        
#         # Prepare data for database
#         db_data = {
#             "recommendation_id": recommendation_id,
#             "user_id": recommendation_data["user_id"],
#             "query": recommendation_data["query"],
#             "category": recommendation_data.get("category"),
#             "recommendations": recommendation_data["recommendations"],
#             "generated_at": datetime.utcnow(),
#             "processing_time_ms": recommendation_data.get("processing_time_ms"),
#             "search_context": recommendation_data.get("search_context", []),
#             "profile_version": recommendation_data.get("profile_version"),
#             "profile_completeness": recommendation_data.get("profile_completeness"),
#             "questions_answered": recommendation_data.get("questions_answered", 0),
#             "session_id": recommendation_data.get("session_id"),
#             "generation_method": recommendation_data.get("generation_method"),
#             "is_active": True,
#             "view_count": 0,
#             "feedback_count": 0
#         }
        
#         # Save to user-specific collection
#         db.collection("user_recommendations").document(recommendation_data["user_id"]).collection("recommendations").document(recommendation_id).set(db_data)
        
#         # Also save to recommendation history for analytics
#         history_data = {
#             "recommendation_id": recommendation_id,
#             "user_id": recommendation_data["user_id"],
#             "query": recommendation_data["query"],
#             "category": recommendation_data.get("category"),
#             "recommendations_count": len(recommendation_data["recommendations"]),
#             "profile_completeness": recommendation_data.get("profile_completeness"),
#             "created_at": datetime.utcnow(),
#             "is_bookmarked": False,
#             "tags": []
#         }
        
#         db.collection("recommendation_history").document(recommendation_id).set(history_data)
        
#         return recommendation_id
        
#     except Exception as e:
#         print(f"Error saving recommendation: {e}")
#         return None

# def get_user_recommendation_history(user_id: str, db, limit: int = 20, offset: int = 0, category: str = None):
#     """Get user's recommendation history from database"""
#     try:
#         query = db.collection("user_recommendations").document(user_id).collection("recommendations").where("is_active", "==", True)
        
#         if category:
#             query = query.where("category", "==", category)
        
#         recommendations = query.order_by("generated_at", direction="DESCENDING").limit(limit).offset(offset).stream()
        
#         history = []
#         for rec in recommendations:
#             rec_data = rec.to_dict()
#             history.append({
#                 "recommendation_id": rec_data["recommendation_id"],
#                 "query": rec_data["query"],
#                 "category": rec_data.get("category"),
#                 "recommendations_count": len(rec_data.get("recommendations", [])),
#                 "generated_at": rec_data["generated_at"],
#                 "view_count": rec_data.get("view_count", 0),
#                 "feedback_count": rec_data.get("feedback_count", 0),
#                 "session_id": rec_data.get("session_id"),
#                 "profile_completeness": rec_data.get("profile_completeness"),
#                 "generation_method": rec_data.get("generation_method")
#             })
        
#         return history
        
#     except Exception as e:
#         print(f"Error getting recommendation history: {e}")
#         return []

# def save_recommendation_feedback(recommendation_id: str, user_id: str, feedback_data: Dict[str, Any], db):
#     """Save user feedback for a recommendation"""
#     try:
#         feedback_id = str(uuid.uuid4())
        
#         feedback_doc = {
#             "feedback_id": feedback_id,
#             "recommendation_id": recommendation_id,
#             "user_id": user_id,
#             "feedback_type": feedback_data["feedback_type"],
#             "rating": feedback_data.get("rating"),
#             "comment": feedback_data.get("comment"),
#             "clicked_items": feedback_data.get("clicked_items", []),
#             "created_at": datetime.utcnow()
#         }
        
#         # Save feedback
#         db.collection("recommendation_feedback").document(feedback_id).set(feedback_doc)
        
#         # Update recommendation with feedback count
#         rec_ref = db.collection("user_recommendations").document(user_id).collection("recommendations").document(recommendation_id)
#         rec_doc = rec_ref.get()
        
#         if rec_doc.exists:
#             current_feedback_count = rec_doc.to_dict().get("feedback_count", 0)
#             rec_ref.update({"feedback_count": current_feedback_count + 1})
        
#         return feedback_id
        
#     except Exception as e:
#         print(f"Error saving feedback: {e}")
#         return None

# # PERMISSIVE Profile validation and loading functions
# def validate_profile_authenticity(profile_data: Dict[str, Any], user_id: str, db) -> Dict[str, Any]:
#     """Modified validation that allows partial profiles but detects contaminated data"""
    
#     if not profile_data or not user_id:
#         return {"valid": False, "reason": "empty_profile_or_user"}
    
#     validation_result = {
#         "valid": True,
#         "warnings": [],
#         "user_id": user_id,
#         "profile_sections": {},
#         "authenticity_score": 1.0,  # Start optimistic
#         "template_indicators": [],
#         "profile_completeness": "partial"
#     }
    
#     try:
#         # Check interview sessions for this user
#         interview_sessions = db.collection("interview_sessions").where("user_id", "==", user_id).stream()
        
#         completed_phases = set()
#         in_progress_phases = set()
#         session_data = {}
#         total_questions_answered = 0
#         has_any_session = False
        
#         for session in interview_sessions:
#             has_any_session = True
#             session_dict = session.to_dict()
#             session_data[session.id] = session_dict
            
#             phase = session_dict.get("current_phase", "unknown")
            
#             if session_dict.get("status") == "completed":
#                 completed_phases.add(phase)
#                 total_questions_answered += session_dict.get("questions_answered", 0)
#             elif session_dict.get("status") == "in_progress":
#                 in_progress_phases.add(phase)
#                 total_questions_answered += session_dict.get("questions_answered", 0)
        
#         validation_result["completed_phases"] = list(completed_phases)
#         validation_result["in_progress_phases"] = list(in_progress_phases)
#         validation_result["total_questions_answered"] = total_questions_answered
#         validation_result["has_any_session"] = has_any_session
#         validation_result["session_data"] = session_data
        
#         # Analyze profile sections
#         profile_sections = profile_data.get("recommendationProfiles", {})
#         general_profile = profile_data.get("generalprofile", {})
        
#         total_detailed_responses = 0
#         total_authenticated_responses = 0
#         total_foreign_responses = 0
#         template_indicators = []
        
#         # Check recommendation profiles
#         for section_name, section_data in profile_sections.items():
#             section_validation = {
#                 "has_data": bool(section_data),
#                 "has_session_for_phase": section_name in (completed_phases | in_progress_phases),
#                 "data_authenticity": "unknown",
#                 "detailed_response_count": 0,
#                 "authenticated_response_count": 0,
#                 "foreign_response_count": 0
#             }
            
#             if section_data and isinstance(section_data, dict):
#                 def analyze_responses(data, path=""):
#                     nonlocal total_detailed_responses, total_authenticated_responses, total_foreign_responses
                    
#                     if isinstance(data, dict):
#                         for key, value in data.items():
#                             current_path = f"{path}.{key}" if path else key
                            
#                             if isinstance(value, dict) and "value" in value:
#                                 response_value = value.get("value", "")
#                                 if isinstance(response_value, str) and len(response_value.strip()) > 10:
#                                     section_validation["detailed_response_count"] += 1
#                                     total_detailed_responses += 1
                                    
#                                     # Check authentication markers
#                                     if "user_id" in value and "updated_at" in value:
#                                         if value.get("user_id") == user_id:
#                                             section_validation["authenticated_response_count"] += 1
#                                             total_authenticated_responses += 1
#                                         else:
#                                             section_validation["foreign_response_count"] += 1
#                                             total_foreign_responses += 1
#                                             template_indicators.append(
#                                                 f"Foreign user data: {section_name}.{current_path} (from {value.get('user_id')})"
#                                             )
#                                     # If no auth markers, it could be legitimate new data or template
#                                     # We'll be more lenient here
                                
#                                 # Recursively check nested structures
#                                 if isinstance(value, dict):
#                                     analyze_responses(value, current_path)
                
#                 analyze_responses(section_data)
                
#                 # Determine authenticity for this section
#                 if section_validation["foreign_response_count"] > 0:
#                     section_validation["data_authenticity"] = "foreign_user_data"
#                 elif section_validation["detailed_response_count"] > 0:
#                     if section_validation["has_session_for_phase"]:
#                         section_validation["data_authenticity"] = "legitimate"
#                     elif section_validation["authenticated_response_count"] > 0:
#                         section_validation["data_authenticity"] = "authenticated_but_no_session"
#                     else:
#                         # This could be legitimate new data or template
#                         # Check if user has ANY interview activity
#                         if has_any_session:
#                             section_validation["data_authenticity"] = "possibly_legitimate"
#                         else:
#                             section_validation["data_authenticity"] = "suspicious_no_sessions"
#                             template_indicators.append(
#                                 f"Detailed data without any interview sessions: {section_name}"
#                             )
#                 else:
#                     section_validation["data_authenticity"] = "minimal_data"
            
#             validation_result["profile_sections"][section_name] = section_validation
        
#         # Check general profile
#         general_detailed_responses = 0
#         general_authenticated_responses = 0
        
#         def check_general_profile(data, path="generalprofile"):
#             nonlocal general_detailed_responses, general_authenticated_responses
            
#             if isinstance(data, dict):
#                 for key, value in data.items():
#                     current_path = f"{path}.{key}"
                    
#                     if isinstance(value, dict):
#                         if "value" in value and isinstance(value["value"], str) and len(value["value"].strip()) > 10:
#                             general_detailed_responses += 1
#                             if "user_id" in value and value.get("user_id") == user_id:
#                                 general_authenticated_responses += 1
#                         else:
#                             check_general_profile(value, current_path)
        
#         check_general_profile(general_profile)
        
#         # Calculate totals
#         total_responses_with_general = total_detailed_responses + general_detailed_responses
#         total_auth_with_general = total_authenticated_responses + general_authenticated_responses
        
#         # Calculate authenticity score (more lenient)
#         if total_responses_with_general > 0:
#             auth_ratio = total_auth_with_general / total_responses_with_general
#             session_factor = 1.0 if has_any_session else 0.3
#             foreign_penalty = min(total_foreign_responses / max(total_responses_with_general, 1), 0.8)
            
#             validation_result["authenticity_score"] = max(0.0, (auth_ratio * 0.6 + session_factor * 0.4) - foreign_penalty)
#         else:
#             validation_result["authenticity_score"] = 1.0
        
#         # Determine profile completeness
#         if len(completed_phases) > 0:
#             validation_result["profile_completeness"] = "complete"
#         elif has_any_session and total_questions_answered > 0:
#             validation_result["profile_completeness"] = "partial_in_progress"
#         elif total_responses_with_general > 0:
#             validation_result["profile_completeness"] = "partial_data_exists"
#         else:
#             validation_result["profile_completeness"] = "empty"
        
#         validation_result["template_indicators"] = template_indicators
#         validation_result["total_detailed_responses"] = total_responses_with_general
#         validation_result["total_authenticated_responses"] = total_auth_with_general
#         validation_result["total_foreign_responses"] = total_foreign_responses
        
#         # MODIFIED validation logic - more permissive
#         # Only mark as invalid for serious contamination issues
#         if total_foreign_responses > 0:
#             validation_result["valid"] = False
#             validation_result["reason"] = "foreign_user_data_detected"
#         elif total_responses_with_general > 10 and not has_any_session:
#             # Extensive data but no interview sessions at all - suspicious
#             validation_result["valid"] = False
#             validation_result["reason"] = "extensive_data_without_any_sessions"
#         elif validation_result["authenticity_score"] < 0.2:
#             # Very low authenticity score
#             validation_result["valid"] = False
#             validation_result["reason"] = "very_low_authenticity_score"
        
#         # Add diagnostics
#         validation_result["diagnostics"] = {
#             "has_interview_activity": has_any_session,
#             "questions_answered": total_questions_answered,
#             "data_to_session_ratio": total_responses_with_general / max(len(completed_phases | in_progress_phases), 1),
#             "authentication_percentage": (total_auth_with_general / max(total_responses_with_general, 1)) * 100,
#             "foreign_data_percentage": (total_foreign_responses / max(total_responses_with_general, 1)) * 100,
#             "profile_usability": "usable" if validation_result["valid"] else "needs_cleanup"
#         }
        
#         return validation_result
        
#     except Exception as e:
#         return {
#             "valid": False, 
#             "reason": "validation_error", 
#             "error": str(e)
#         }

# def load_user_profile(user_id: str = None) -> Dict[str, Any]:
#     """Load and validate USER-SPECIFIC profile from Firestore - matches Streamlit pattern"""
#     try:
#         db = get_firestore_client()
        
#         if not user_id:
#             print("❌ No user_id provided for profile loading")
#             return {}
        
#         print(f"🔍 Looking for profile for user: {user_id}")
        
#         # Try to find profile in multiple locations (same as Streamlit logic)
#         profile_locations = [
#             {
#                 "collection": "user_profiles",
#                 "document": f"{user_id}_profile_structure.json",
#                 "description": "Primary user_profiles collection"
#             },
#             {
#                 "collection": "user_collection", 
#                 "document": f"{user_id}_profile_structure.json",
#                 "description": "Fallback user_collection with user prefix"
#             },
#             {
#                 "collection": "user_collection",
#                 "document": "profile_strcuture.json",  # Matches Streamlit typo
#                 "description": "Streamlit default profile location"
#             },
#             {
#                 "collection": "interview_profiles",
#                 "document": f"{user_id}_profile.json", 
#                 "description": "Interview-generated profile"
#             },
#             {
#                 "collection": f"user_{user_id}",
#                 "document": "profile_structure.json",
#                 "description": "User-specific collection"
#             }
#         ]
        
#         raw_profile = None
#         profile_source = None
        
#         for location in profile_locations:
#             try:
#                 doc_ref = db.collection(location["collection"]).document(location["document"])
#                 doc = doc_ref.get()
                
#                 if doc.exists:
#                     raw_profile = doc.to_dict()
#                     profile_source = f"{location['collection']}/{location['document']}"
#                     print(f"✅ Found profile at: {profile_source}")
#                     break
                    
#             except Exception as e:
#                 print(f"❌ Error checking {location['description']}: {e}")
#                 continue
        
#         if not raw_profile:
#             print(f"❌ No profile found for user: {user_id}")
#             return {}
        
#         # Validate profile authenticity with permissive validation
#         validation = validate_profile_authenticity(raw_profile, user_id, db)
        
#         print(f"🔍 Profile validation result: {validation.get('valid')} - {validation.get('reason', 'OK')}")
#         print(f"🔍 Profile completeness: {validation.get('profile_completeness', 'unknown')}")
#         print(f"🔍 Questions answered: {validation.get('total_questions_answered', 0)}")
#         print(f"🔍 Authenticity score: {validation.get('authenticity_score', 0.0):.2f}")
        
#         if validation.get("warnings"):
#             print(f"⚠️ Profile warnings: {validation['warnings']}")
        
#         # Only reject for serious contamination
#         if not validation.get("valid"):
#             serious_issues = ["foreign_user_data_detected", "extensive_data_without_any_sessions"]
#             if validation.get("reason") in serious_issues:
#                 print(f"🚨 SERIOUS PROFILE ISSUE for user {user_id}: {validation.get('reason')}")
#                 return {
#                     "error": "contaminated_profile",
#                     "user_id": user_id,
#                     "validation": validation,
#                     "message": f"Profile validation failed: {validation.get('reason')}",
#                     "profile_source": profile_source
#                 }
#             else:
#                 print(f"⚠️ Minor profile issue for user {user_id}: {validation.get('reason')} - allowing with warnings")
        
#         # Return profile with validation info (even if partial)
#         profile_with_metadata = raw_profile.copy()
#         profile_with_metadata["_validation"] = validation
#         profile_with_metadata["_source"] = profile_source
        
#         return profile_with_metadata
        
#     except Exception as e:
#         print(f"❌ Error loading user profile for {user_id}: {e}")
#         return {}

# def search_web(query, max_results=3, max_retries=3, base_delay=1.0):
#     """Query DuckDuckGo via DDGS.text(), returning up to max_results items."""
#     for attempt in range(1, max_retries + 1):
#         try:
#             with DDGS() as ddgs:
#                 return list(islice(ddgs.text(query), max_results))
#         except DuckDuckGoSearchException as e:
#             msg = str(e)
#             if "202" in msg:
#                 wait = base_delay * (2 ** (attempt - 1))
#                 print(f"[search_web] Rate‑limited (202). Retry {attempt}/{max_retries} in {wait:.1f}s…")
#                 time.sleep(wait)
#             else:
#                 raise
#         except Exception as e:
#             print(f"[search_web] Unexpected error: {e}")
#             break
    
#     print(f"[search_web] Failed to fetch results after {max_retries} attempts.")
#     return []

# def generate_recommendations(user_profile, user_query, openai_key, category=None):
#     """Generate 3 personalized recommendations using user profile and web search - STREAMLIT COMPATIBLE"""
    
#     # Enhanced search with category context
#     if category:
#         search_query = f"{category} {user_query} recommendations 2024"
#     else:
#         search_query = f"{user_query} recommendations 2024"
    
#     search_results = search_web(search_query)
    
#     # Category-specific instructions
#     category_instructions = ""
#     if category:
#         category_lower = category.lower()
        
#         if category_lower in ["travel", "travel & destinations"]:
#             category_instructions = """
#             **CATEGORY FOCUS: TRAVEL & DESTINATIONS**
#             - Recommend specific destinations, attractions, or travel experiences
#             - Include practical travel advice (best time to visit, transportation, accommodations)
#             - Consider cultural experiences, local cuisine, historical sites, natural attractions
#             - Focus on places to visit, things to do, travel itineraries
#             - DO NOT recommend economic plans, political content, or business strategies
            
#             **EXAMPLE for Pakistan Travel Query**:
#             - "Hunza Valley, Pakistan" - Mountain valley with stunning landscapes
#             - "Lahore Food Street" - Culinary travel experience in historic city
#             - "Skardu Adventures" - Trekking and mountaineering destination
#             """
            
#         elif category_lower in ["movies", "movies & tv", "entertainment"]:
#             category_instructions = """
#             **CATEGORY FOCUS: MOVIES & TV**
#             - Recommend specific movies, TV shows, or streaming content
#             - Consider genres, directors, actors, themes that match user preferences
#             - Include where to watch (streaming platforms) if possible
#             - Focus on entertainment content, not travel or other categories
#             """
            
#         elif category_lower in ["food", "food & dining", "restaurants"]:
#             category_instructions = """
#             **CATEGORY FOCUS: FOOD & DINING**
#             - Recommend specific restaurants, cuisines, or food experiences
#             - Include local specialties, popular dishes, dining venues
#             - Consider user's location and dietary preferences
#             - Focus on food and dining experiences, not travel destinations
#             """
            
#         else:
#             category_instructions = f"""
#             **CATEGORY FOCUS: {category.upper()}**
#             - Focus recommendations specifically on {category} related content
#             - Ensure all suggestions are relevant to the {category} category
#             - Do not recommend content from other categories
#             """
    
#     prompt = f"""
#     **Task**: Generate exactly 3 highly personalized {category + ' ' if category else ''}recommendations based on:
    
#     {category_instructions}
    
#     **User Profile**:
#     {json.dumps(user_profile, indent=2)}
    
#     **User Query**:
#     "{user_query}"
    
#     **Web Context** (for reference only):
#     {search_results}
    
#     **Requirements**:
#     1. Each recommendation must directly reference profile details when available
#     2. ALL recommendations MUST be relevant to the "{category}" category if specified
#     3. Blend the user's core values and preferences from their profile
#     4. Only suggest what is asked for - no extra advice
#     5. For travel queries, recommend specific destinations, attractions, or experiences
#     6. Format as JSON array with each recommendation having:
#        - title: string (specific name of place/item/experience)
#        - description: string (brief description of what it is)
#        - reasons: array of strings (why it matches the user profile)
#        - confidence_score: float (0.0-1.0)
    
#     **CRITICAL for Travel Category**: 
#     If this is a travel recommendation, suggest actual destinations, attractions, restaurants, or travel experiences.
#     DO NOT suggest economic plans, political content, or business strategies.
    
#     **Output Example for Travel**:
#     [
#       {{
#          "title": "Hunza Valley, Pakistan",
#          "description": "Breathtaking mountain valley known for stunning landscapes and rich cultural heritage",
#          "reasons": ["Matches your love for natural beauty and cultural exploration", "Perfect for peaceful mountain retreats you prefer"],
#          "confidence_score": 0.9
#       }},
#       {{
#          "title": "Lahore Food Street, Pakistan", 
#          "description": "Historic food destination offering authentic Pakistani cuisine and cultural immersion",
#          "reasons": ["Aligns with your interest in trying traditional foods", "Offers the cultural experiences you enjoy"],
#          "confidence_score": 0.85
#       }},
#       {{
#          "title": "Skardu, Pakistan",
#          "description": "Adventure destination for trekking and mountaineering with stunning natural scenery",
#          "reasons": ["Perfect for your moderate adventure seeking preferences", "Offers the peaceful outdoor experiences you value"],
#          "confidence_score": 0.8
#       }}
#     ]
    
#     Generate your response in JSON format only.
#     """
    
#     # Setting up LLM - same as Streamlit pattern
#     client = OpenAI(api_key=openai_key)

#     response = client.chat.completions.create(
#         model="gpt-4",
#         messages=[
#             {"role": "system", "content": f"You're a recommendation engine that creates hyper-personalized {category.lower() if category else ''} suggestions. You MUST focus on {category.lower() if category else 'relevant'} content only. Output valid JSON only."},
#             {"role": "user", "content": prompt}
#         ],
#         temperature=0.7  
#     )
    
#     return response.choices[0].message.content

# # ROUTE DEFINITIONS - SPECIFIC ROUTES FIRST, PARAMETERIZED ROUTES LAST

# @router.get("/profile")
# async def get_user_profile(current_user: str = Depends(get_current_user)):
#     """Get the current user's profile - allows partial profiles"""
#     try:
#         print(f"🔍 Getting profile for user: {current_user}")
#         profile = load_user_profile(current_user)
        
#         # Handle contaminated profile (only for serious issues)
#         if isinstance(profile, dict) and profile.get("error") == "contaminated_profile":
#             validation_info = profile.get("validation", {})
            
#             # Check if it's a serious contamination or just partial data
#             if validation_info.get("reason") == "foreign_user_data_detected":
#                 raise HTTPException(
#                     status_code=422,
#                     detail={
#                         "error": "contaminated_profile",
#                         "message": "Profile contains data from other users",
#                         "user_id": current_user,
#                         "validation": validation_info,
#                         "recommended_action": "clear_contaminated_profile_and_restart_interview"
#                     }
#                 )
#             elif validation_info.get("reason") == "extensive_data_without_any_sessions":
#                 raise HTTPException(
#                     status_code=422,
#                     detail={
#                         "error": "suspicious_profile",
#                         "message": "Profile has extensive data but no interview sessions",
#                         "user_id": current_user,
#                         "validation": validation_info,
#                         "recommended_action": "start_interview_to_validate_or_clear_profile"
#                     }
#                 )
#             # For other validation issues, allow profile but with warnings
        
#         if not profile:
#             # Check interview status
#             db = get_firestore_client()
#             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#             sessions = list(sessions_ref.stream())
            
#             if not sessions:
#                 raise HTTPException(
#                     status_code=404,
#                     detail="No profile found. Please start an interview to begin creating your profile."
#                 )
            
#             # If there are sessions but no profile, suggest continuing
#             in_progress_sessions = [s for s in sessions if s.to_dict().get("status") == "in_progress"]
#             if in_progress_sessions:
#                 raise HTTPException(
#                     status_code=404,
#                     detail={
#                         "message": "Interview in progress but no profile generated yet. Continue the interview to build your profile.",
#                         "sessions": [{"session_id": s.id, "phase": s.to_dict().get("current_phase")} for s in in_progress_sessions]
#                     }
#                 )
        
#         # Return profile (even if partial)
#         clean_profile = {k: v for k, v in profile.items() if not k.startswith('_')}
#         validation_summary = profile.get("_validation", {})
        
#         response = {
#             "success": True,
#             "profile": clean_profile,
#             "user_id": current_user,
#             "profile_type": "user_specific",
#             "profile_found": True,
#             "profile_completeness": validation_summary.get("profile_completeness", "unknown"),
#             "validation_summary": {
#                 "valid": validation_summary.get("valid", True),
#                 "authenticity_score": validation_summary.get("authenticity_score", 1.0),
#                 "reason": validation_summary.get("reason"),
#                 "has_interview_activity": validation_summary.get("has_any_session", False),
#                 "questions_answered": validation_summary.get("total_questions_answered", 0),
#                 "total_responses": validation_summary.get("total_detailed_responses", 0),
#                 "authenticated_responses": validation_summary.get("total_authenticated_responses", 0),
#                 "completed_phases": validation_summary.get("completed_phases", []),
#                 "in_progress_phases": validation_summary.get("in_progress_phases", [])
#             },
#             "profile_source": profile.get("_source", "unknown")
#         }
        
#         # Add guidance based on completeness
#         # Add guidance based on completeness
#         if validation_summary.get("profile_completeness") == "partial_in_progress":
#             response["message"] = "Profile is being built as you answer interview questions. Continue the interview for more personalized recommendations."
#         elif validation_summary.get("profile_completeness") == "partial_data_exists":
#             response["message"] = "Profile has some data. Start or continue an interview to enhance personalization."
#         elif validation_summary.get("profile_completeness") == "complete":
#             response["message"] = "Profile is complete and ready for personalized recommendations."
#         elif validation_summary.get("profile_completeness") == "empty":
#             response["message"] = "Profile is empty. Start an interview to begin building your personalized profile."
        
#         return response
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"❌ Error in get_user_profile: {e}")
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to load profile: {str(e)}"
#         )

# @router.get("/categories")
# async def get_recommendation_categories():
#     """Get available recommendation categories"""
#     categories = [
#         {
#             "id": "movies",
#             "name": "Movies & TV",
#             "description": "Movie and TV show recommendations",
#             "questions_file": "moviesAndTV_tiered_questions.json"
#         },
#         {
#             "id": "food",
#             "name": "Food & Dining",
#             "description": "Restaurant and food recommendations",
#             "questions_file": "foodAndDining_tiered_questions.json"
#         },
#         {
#             "id": "travel",
#             "name": "Travel",
#             "description": "Travel destination recommendations",
#             "questions_file": "travel_tiered_questions.json"
#         },
#         {
#             "id": "books",
#             "name": "Books & Reading",
#             "description": "Book recommendations",
#             "questions_file": "books_tiered_questions.json"
#         },
#         {
#             "id": "music",
#             "name": "Music",
#             "description": "Music and artist recommendations",
#             "questions_file": "music_tiered_questions.json"
#         },
#         {
#             "id": "fitness",
#             "name": "Fitness & Wellness",
#             "description": "Fitness and wellness recommendations",
#             "questions_file": "fitness_tiered_questions.json"
#         }
#     ]
    
#     return {
#         "categories": categories,
#         "default_category": "movies"
#     }

# @router.get("/history")
# async def get_recommendation_history(
#     current_user: str = Depends(get_current_user),
#     limit: int = Query(20, description="Number of recommendations to return"),
#     offset: int = Query(0, description="Number of recommendations to skip"),
#     category: Optional[str] = Query(None, description="Filter by category"),
#     date_from: Optional[datetime] = Query(None, description="Filter from date"),
#     date_to: Optional[datetime] = Query(None, description="Filter to date")
# ):
#     """Get recommendation history for the user with enhanced filtering"""
#     try:
#         db = get_firestore_client()
        
#         # Simplified query to avoid index issues - just get user's recommendations
#         query = db.collection("user_recommendations").document(current_user).collection("recommendations")
#         query = query.where("is_active", "==", True)
#         query = query.limit(limit).offset(offset)
        
#         # Get all recommendations (without complex ordering initially)
#         recommendations = list(query.stream())
        
#         # Filter and sort in Python instead of Firestore
#         filtered_recs = []
#         for rec in recommendations:
#             rec_data = rec.to_dict()
            
#             # Apply category filter
#             if category and rec_data.get("category") != category:
#                 continue
            
#             # Apply date filters
#             rec_date = rec_data.get("generated_at")
#             if date_from and rec_date and rec_date < date_from:
#                 continue
#             if date_to and rec_date and rec_date > date_to:
#                 continue
            
#             filtered_recs.append(rec_data)
        
#         # Sort by generated_at descending
#         filtered_recs.sort(key=lambda x: x.get("generated_at", datetime.min), reverse=True)
        
#         # Format response
#         history = []
#         for rec_data in filtered_recs:
#             history.append({
#                 "recommendation_id": rec_data["recommendation_id"],
#                 "query": rec_data["query"],
#                 "category": rec_data.get("category"),
#                 "recommendations_count": len(rec_data.get("recommendations", [])),
#                 "generated_at": rec_data["generated_at"],
#                 "view_count": rec_data.get("view_count", 0),
#                 "feedback_count": rec_data.get("feedback_count", 0),
#                 "session_id": rec_data.get("session_id"),
#                 "processing_time_ms": rec_data.get("processing_time_ms"),
#                 "profile_completeness": rec_data.get("profile_completeness", "unknown"),
#                 "generation_method": rec_data.get("generation_method", "unknown")
#             })
        
#         return {
#             "success": True,
#             "history": history,
#             "total_count": len(history),
#             "user_id": current_user,
#             "filters": {
#                 "category": category,
#                 "date_from": date_from,
#                 "date_to": date_to,
#                 "limit": limit,
#                 "offset": offset
#             },
#             "note": "Using simplified query to avoid Firebase index requirements"
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to get recommendation history: {str(e)}"
#         )

# @router.get("/analytics/summary")
# async def get_recommendation_analytics(
#     current_user: str = Depends(get_current_user),
#     days: int = Query(30, description="Number of days to analyze")
# ):
#     """Get recommendation analytics for the user"""
#     try:
#         db = get_firestore_client()
        
#         # Calculate date range
#         end_date = datetime.utcnow()
#         start_date = end_date - timedelta(days=days)
        
#         # Get recommendations - simplified query
#         recommendations_ref = db.collection("user_recommendations").document(current_user).collection("recommendations")
#         recommendations = recommendations_ref.where("is_active", "==", True).stream()
        
#         analytics = {
#             "total_recommendations": 0,
#             "categories_explored": set(),
#             "query_types": {},
#             "total_views": 0,
#             "total_feedback": 0,
#             "average_processing_time": 0,
#             "recommendations_by_day": {},
#             "most_popular_category": None,
#             "engagement_rate": 0,
#             "profile_completeness_breakdown": {},
#             "generation_method_breakdown": {}
#         }
        
#         processing_times = []
#         daily_counts = {}
#         category_counts = {}
#         completeness_counts = {}
#         method_counts = {}
        
#         for rec in recommendations:
#             rec_data = rec.to_dict()
            
#             # Filter by date range
#             rec_date = rec_data.get("generated_at")
#             if rec_date and rec_date < start_date:
#                 continue
                
#             analytics["total_recommendations"] += 1
            
#             # Track categories
#             category = rec_data.get("category", "general")
#             analytics["categories_explored"].add(category)
#             category_counts[category] = category_counts.get(category, 0) + 1
            
#             # Track profile completeness
#             completeness = rec_data.get("profile_completeness", "unknown")
#             completeness_counts[completeness] = completeness_counts.get(completeness, 0) + 1
            
#             # Track generation method
#             method = rec_data.get("generation_method", "unknown")
#             method_counts[method] = method_counts.get(method, 0) + 1
            
#             # Track views and feedback
#             analytics["total_views"] += rec_data.get("view_count", 0)
#             analytics["total_feedback"] += rec_data.get("feedback_count", 0)
            
#             # Track processing times
#             if rec_data.get("processing_time_ms"):
#                 processing_times.append(rec_data["processing_time_ms"])
            
#             # Track daily activity
#             if rec_date:
#                 if hasattr(rec_date, 'date'):
#                     date_str = rec_date.date().isoformat()
#                 else:
#                     date_str = datetime.fromisoformat(str(rec_date)).date().isoformat()
                
#                 daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
        
#         # Calculate averages and insights
#         if analytics["total_recommendations"] > 0:
#             analytics["engagement_rate"] = round((analytics["total_views"] / analytics["total_recommendations"]) * 100, 2)
        
#         if processing_times:
#             analytics["average_processing_time"] = round(sum(processing_times) / len(processing_times), 2)
        
#         if category_counts:
#             analytics["most_popular_category"] = max(category_counts, key=category_counts.get)
        
#         analytics["categories_explored"] = list(analytics["categories_explored"])
#         analytics["recommendations_by_day"] = daily_counts
#         analytics["category_breakdown"] = category_counts
#         analytics["profile_completeness_breakdown"] = completeness_counts
#         analytics["generation_method_breakdown"] = method_counts
        
#         return {
#             "success": True,
#             "analytics": analytics,
#             "period": {
#                 "start_date": start_date.isoformat(),
#                 "end_date": end_date.isoformat(),
#                 "days": days
#             },
#             "user_id": current_user
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to get recommendation analytics: {str(e)}"
#         )

# @router.get("/debug/profile-location")
# async def debug_profile_location(current_user: str = Depends(get_current_user)):
#     """Debug endpoint to check where user profile is stored and validate it"""
#     try:
#         db = get_firestore_client()
        
#         locations_checked = {
#             "user_profiles": False,
#             "user_collection": False,
#             "interview_profiles": False,
#             "user_specific_collection": False,
#             "streamlit_default": False,
#             "fallback_locations": {}
#         }
        
#         profile_sources = []
        
#         # Check primary location
#         profile_doc_id = f"{current_user}_profile_structure.json"
        
#         # Check user_profiles collection
#         try:
#             profile_doc = db.collection("user_profiles").document(profile_doc_id).get()
#             locations_checked["user_profiles"] = profile_doc.exists
#             if profile_doc.exists:
#                 profile_sources.append({
#                     "location": f"user_profiles/{profile_doc_id}",
#                     "data_preview": str(profile_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["user_profiles"] = f"Error: {e}"
        
#         # Check user_collection fallback
#         try:
#             fallback_doc = db.collection("user_collection").document(profile_doc_id).get()
#             locations_checked["user_collection"] = fallback_doc.exists
#             if fallback_doc.exists:
#                 profile_sources.append({
#                     "location": f"user_collection/{profile_doc_id}",
#                     "data_preview": str(fallback_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["user_collection"] = f"Error: {e}"
        
#         # Check Streamlit default location (matches typo)
#         try:
#             streamlit_doc = db.collection("user_collection").document("profile_strcuture.json").get()
#             locations_checked["streamlit_default"] = streamlit_doc.exists
#             if streamlit_doc.exists:
#                 profile_sources.append({
#                     "location": "user_collection/profile_strcuture.json",
#                     "data_preview": str(streamlit_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["streamlit_default"] = f"Error: {e}"
        
#         # Check interview_profiles
#         try:
#             interview_doc = db.collection("interview_profiles").document(f"{current_user}_profile.json").get()
#             locations_checked["interview_profiles"] = interview_doc.exists
#             if interview_doc.exists:
#                 profile_sources.append({
#                     "location": f"interview_profiles/{current_user}_profile.json",
#                     "data_preview": str(interview_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["interview_profiles"] = f"Error: {e}"
        
#         # Check user-specific collection
#         try:
#             user_specific_doc = db.collection(f"user_{current_user}").document("profile_structure.json").get()
#             locations_checked["user_specific_collection"] = user_specific_doc.exists
#             if user_specific_doc.exists:
#                 profile_sources.append({
#                     "location": f"user_{current_user}/profile_structure.json",
#                     "data_preview": str(user_specific_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["user_specific_collection"] = f"Error: {e}"
        
#         # Check other possible locations
#         possible_docs = [
#             ("user_collection", "profile_structure.json"),
#             ("user_collection", f"{current_user}_profile.json"),
#             ("profiles", f"{current_user}.json"),
#             ("user_data", f"{current_user}_profile.json")
#         ]
        
#         for collection_name, doc_name in possible_docs:
#             try:
#                 doc_exists = db.collection(collection_name).document(doc_name).get().exists
#                 locations_checked["fallback_locations"][f"{collection_name}/{doc_name}"] = doc_exists
#                 if doc_exists:
#                     profile_sources.append({
#                         "location": f"{collection_name}/{doc_name}",
#                         "data_preview": "Found but not retrieved"
#                     })
#             except Exception as e:
#                 locations_checked["fallback_locations"][f"{collection_name}/{doc_name}"] = f"Error: {e}"
        
#         # Get interview session info
#         interview_sessions = []
#         try:
#             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#             for session in sessions_ref.stream():
#                 session_data = session.to_dict()
#                 interview_sessions.append({
#                     "session_id": session.id,
#                     "status": session_data.get("status"),
#                     "phase": session_data.get("current_phase"),
#                     "tier": session_data.get("current_tier"),
#                     "questions_answered": session_data.get("questions_answered", 0),
#                     "created_at": session_data.get("created_at"),
#                     "updated_at": session_data.get("updated_at")
#                 })
#         except Exception as e:
#             interview_sessions = [{"error": str(e)}]
        
#         # Test the current profile loading function
#         test_profile = load_user_profile(current_user)
#         profile_validation = None
        
#         if test_profile:
#             if test_profile.get("error"):
#                 profile_validation = {
#                     "status": "error",
#                     "error_type": test_profile.get("error"),
#                     "validation_details": test_profile.get("validation", {})
#                 }
#             else:
#                 profile_validation = {
#                     "status": "loaded",
#                     "validation_summary": test_profile.get("_validation", {}),
#                     "source": test_profile.get("_source", "unknown")
#                 }
        
#         return {
#             "success": True,
#             "user_id": current_user,
#             "locations_checked": locations_checked,
#             "profile_sources_found": profile_sources,
#             "expected_document": profile_doc_id,
#             "streamlit_compatible_search": True,
#             "interview_sessions": interview_sessions,
#             "profile_load_test": profile_validation,
#             "collections_searched": [
#                 "user_profiles", "user_collection", "interview_profiles", 
#                 f"user_{current_user}", "profiles", "user_data"
#             ]
#         }
        
#     except Exception as e:
#         return {
#             "success": False,
#             "error": str(e),
#             "user_id": current_user
#         }

# @router.post("/profile/regenerate")
# async def regenerate_user_profile(current_user: str = Depends(get_current_user)):
#     """Regenerate user profile from completed interview sessions"""
#     try:
#         db = get_firestore_client()
        
#         # Get all interview sessions for user (both completed and in-progress)
#         sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#         all_sessions = list(sessions_ref.stream())
        
#         completed_sessions = [s for s in all_sessions if s.to_dict().get("status") == "completed"]
#         in_progress_sessions = [s for s in all_sessions if s.to_dict().get("status") == "in_progress"]
        
#         if not completed_sessions and not in_progress_sessions:
#             raise HTTPException(
#                 status_code=400,
#                 detail="No interview sessions found. Start an interview first."
#             )
        
#         # TODO: Implement profile regeneration logic based on actual user responses
#         # This would involve:
#         # 1. Extracting responses from interview sessions
#         # 2. Building a clean profile structure
#         # 3. Saving to appropriate profile collection
        
#         return {
#             "success": True,
#             "message": "Profile regeneration initiated",
#             "user_id": current_user,
#             "completed_sessions": len(completed_sessions),
#             "in_progress_sessions": len(in_progress_sessions),
#             "note": "Profile regeneration logic needs to be implemented"
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to regenerate profile: {str(e)}"
#         )

# @router.delete("/profile/clear-contaminated")
# async def clear_contaminated_profile(current_user: str = Depends(get_current_user)):
#     """Clear contaminated profile data"""
#     try:
#         db = get_firestore_client()
        
#         # Delete the contaminated profile from all possible locations
#         profile_doc_id = f"{current_user}_profile_structure.json"
        
#         deleted_locations = []
        
#         # Try deleting from multiple locations
#         locations = [
#             ("user_profiles", profile_doc_id),
#             ("user_collection", profile_doc_id),
#             ("user_collection", "profile_strcuture.json"),  # Streamlit default
#             ("interview_profiles", f"{current_user}_profile.json"),
#         ]
        
#         for collection_name, doc_name in locations:
#             try:
#                 doc_ref = db.collection(collection_name).document(doc_name)
#                 if doc_ref.get().exists:
#                     doc_ref.delete()
#                     deleted_locations.append(f"{collection_name}/{doc_name}")
#             except Exception as e:
#                 print(f"Error deleting from {collection_name}/{doc_name}: {e}")
        
#         return {
#             "success": True,
#             "message": f"Cleared contaminated profile for user {current_user}",
#             "user_id": current_user,
#             "deleted_locations": deleted_locations,
#             "action": "profile_deleted"
#         }
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/generate", response_model=RecommendationResponse)
# async def generate_user_recommendations(
#     request: RecommendationRequest,
#     current_user: str = Depends(get_current_user)
# ):
#     """Generate recommendations using the same logic as Streamlit but enhanced for FastAPI"""
#     try:
#         start_time = datetime.utcnow()
#         settings = get_settings()
#         db = get_firestore_client()
        
#         print(f"🚀 Generating recommendations for user: {current_user}")
#         print(f"📝 Query: {request.query}")
#         print(f"🏷️ Category: {request.category}")
        
#         # Load profile (same as Streamlit)
#         user_profile = load_user_profile(current_user)
        
#         # Handle serious contamination only
#         if isinstance(user_profile, dict) and user_profile.get("error") == "contaminated_profile":
#             validation = user_profile.get("validation", {})
#             if validation.get("reason") in ["foreign_user_data_detected", "extensive_data_without_any_sessions"]:
#                 raise HTTPException(
#                     status_code=422,
#                     detail={
#                         "error": "contaminated_profile",
#                         "message": "Cannot generate recommendations with contaminated profile data",
#                         "recommended_action": "clear_profile_and_start_interview"
#                     }
#                 )
        
#         # If no profile, check if we should allow basic recommendations (same as Streamlit)
#         if not user_profile:
#             print("⚠️ No profile found - checking interview status")
            
#             # Check if user has any interview activity
#             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#             sessions = list(sessions_ref.stream())
            
#             if not sessions:
#                 # No interview started - create minimal profile for basic recommendations
#                 print("📝 No interview sessions - creating basic profile for general recommendations")
#                 user_profile = {
#                     "user_id": current_user,
#                     "generalprofile": {
#                         "corePreferences": {
#                             "note": "Basic profile - complete interview for personalized recommendations"
#                         }
#                     },
#                     "profile_completeness": "empty"
#                 }
#             else:
#                 # Has interview activity but no profile - this shouldn't happen
#                 raise HTTPException(
#                     status_code=404,
#                     detail="Interview sessions found but no profile generated. Please contact support."
#                 )
        
#         # Clean profile for AI processing (remove metadata)
#         clean_profile = {k: v for k, v in user_profile.items() if not k.startswith('_')}
        
#         # Get profile completeness info
#         validation_summary = user_profile.get("_validation", {})
#         profile_completeness = validation_summary.get("profile_completeness", "unknown")
#         questions_answered = validation_summary.get("total_questions_answered", 0)
        
#         print(f"📊 Profile completeness: {profile_completeness}")
#         print(f"📝 Questions answered: {questions_answered}")
        
#         # Generate recommendations using same function as Streamlit but with category
#         recs_json = generate_recommendations(
#             clean_profile, 
#             request.query, 
#             settings.OPENAI_API_KEY,
#             request.category  # Add category parameter
#         )
        
#         try:
#             recs = json.loads(recs_json)
            
#             # Normalize to list (same as Streamlit)
#             if isinstance(recs, dict):
#                 if "recommendations" in recs and isinstance(recs["recommendations"], list):
#                     recs = recs["recommendations"]
#                 else:
#                     recs = [recs]
            
#             if not isinstance(recs, list):
#                 raise HTTPException(
#                     status_code=500,
#                     detail="Unexpected response format – expected a list of recommendations."
#                 )
            
#             # Validate category relevance for travel
#             if request.category and request.category.lower() == "travel":
#                 travel_keywords = ["destination", "place", "visit", "travel", "city", "country", "attraction", "trip", "valley", "mountain", "beach", "street", "food", "culture", "heritage", "adventure", "pakistan", "hunza", "lahore", "skardu"]
                
#                 for i, rec in enumerate(recs):
#                     title_and_desc = (rec.get('title', '') + ' ' + rec.get('description', '')).lower()
#                     if not any(keyword in title_and_desc for keyword in travel_keywords):
#                         print(f"⚠️ Recommendation {i+1} '{rec.get('title')}' may not be travel-related")
#                         print(f"🔍 Content: {title_and_desc[:100]}...")
            
#             # Calculate processing time
#             processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
#             # Add profile completion guidance (like Streamlit would)
#             for rec in recs:
#                 if profile_completeness in ["partial_in_progress", "partial_data_exists", "empty"]:
#                     if "reasons" not in rec:
#                         rec["reasons"] = []
#                     if profile_completeness == "empty":
#                         rec["reasons"].append("Start the interview to get more personalized recommendations")
#                     else:
#                         rec["reasons"].append("Complete more interview questions for better personalization")
            
#             # Generate session ID for conversation tracking
#             session_id = str(uuid.uuid4())
            
#             # Save conversation messages (like Streamlit chat)
#             save_conversation_message(
#                 current_user, 
#                 session_id, 
#                 "user", 
#                 f"What would you like {request.category.lower() if request.category else ''} recommendations for? {request.query}", 
#                 "recommendation",
#                 f"{request.category or 'General'} Recommendation Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
#             )
            
#             # Prepare recommendation data for database
#             recommendation_data = {
#                 "user_id": current_user,
#                 "query": request.query,
#                 "category": request.category,
#                 "recommendations": recs,
#                 "processing_time_ms": int(processing_time),
#                 "search_context": search_web(f"{request.category} {request.query} recommendations 2024" if request.category else f"{request.query} recommendations 2024"),
#                 "session_id": session_id,
#                 "profile_version": clean_profile.get("version", "1.0"),
#                 "profile_completeness": profile_completeness,
#                 "questions_answered": questions_answered,
#                 "user_specific": True,
#                 "generation_method": "streamlit_compatible"
#             }
            
#             # Save to database
#             recommendation_id = save_recommendation_to_db(recommendation_data, db)
            
#             if not recommendation_id:
#                 print("⚠️ Warning: Failed to save recommendation to database")
#                 recommendation_id = str(uuid.uuid4())  # Fallback
            
#             # Format recommendations for conversation history (like Streamlit display)
#             recs_text = f"Here are your {request.category.lower() if request.category else ''} recommendations:\n\n"
            
#             for i, rec in enumerate(recs, 1):
#                 title = rec.get("title", "<no title>")
#                 description = rec.get("description", rec.get("reason", "<no description>"))
#                 reasons = rec.get("reasons", [])
                
#                 recs_text += f"**{i}. {title}**\n"
#                 recs_text += f"{description}\n"
#                 if reasons:
#                     for reason in reasons:
#                         recs_text += f"• {reason}\n"
#                 recs_text += "\n"
            
#             # Save recommendations to conversation history
#             save_conversation_message(
#                 current_user, 
#                 session_id, 
#                 "assistant", 
#                 recs_text, 
#                 "recommendation"
#             )
            
#             # Convert to RecommendationItem objects
#             recommendation_items = []
#             for rec in recs:
#                 # Use confidence score from AI or default based on profile completeness
#                 confidence_score = rec.get('confidence_score', 0.6 if profile_completeness == "empty" else 0.8)
                
#                 recommendation_items.append(RecommendationItem(
#                     title=rec.get('title', 'Recommendation'),
#                     description=rec.get('description', rec.get('reason', '')),
#                     reasons=rec.get('reasons', []),
#                     category=request.category,
#                     confidence_score=confidence_score
#                 ))
            
#             return RecommendationResponse(
#                 recommendation_id=recommendation_id,
#                 recommendations=recommendation_items,
#                 query=request.query,
#                 category=request.category,
#                 user_id=current_user,
#                 generated_at=datetime.utcnow(),
#                 processing_time_ms=int(processing_time)
#             )
            
#         except json.JSONDecodeError as e:
#             error_msg = f"Failed to parse recommendations: {str(e)}"
#             print(f"❌ JSON parsing error: {error_msg}")
#             print(f"🔍 Raw AI response: {recs_json[:500]}...")
            
#             # Save error to conversation history
#             save_conversation_message(
#                 current_user, 
#                 str(uuid.uuid4()), 
#                 "assistant", 
#                 f"Sorry, I encountered an error generating {request.category or ''} recommendations: {error_msg}", 
#                 "recommendation"
#             )
            
#             raise HTTPException(
#                 status_code=500,
#                 detail=error_msg
#             )
            
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"❌ Error generating recommendations for user {current_user}: {e}")
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to generate {request.category or ''} recommendations: {str(e)}"
#         )

# @router.post("/category")
# async def generate_category_recommendations(
#     request: RecommendationRequest,
#     current_user: str = Depends(get_current_user)
# ):
#     """Generate category-specific recommendations - redirect to main generate endpoint"""
#     # This now uses the enhanced generate endpoint
#     return await generate_user_recommendations(request, current_user)

# @router.post("/{recommendation_id}/feedback")
# async def submit_recommendation_feedback(
#     recommendation_id: str,
#     feedback: RecommendationFeedback,
#     current_user: str = Depends(get_current_user)
# ):
#     """Submit feedback for a recommendation"""
#     try:
#         db = get_firestore_client()
        
#         # Verify recommendation exists and belongs to user
#         rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
#         if not rec_doc.exists:
#             raise HTTPException(status_code=404, detail="Recommendation not found")
        
#         # Save feedback
#         feedback_data = {
#             "feedback_type": feedback.feedback_type,
#             "rating": feedback.rating,
#             "comment": feedback.comment,
#             "clicked_items": feedback.clicked_items
#         }
        
#         feedback_id = save_recommendation_feedback(recommendation_id, current_user, feedback_data, db)
        
#         if not feedback_id:
#             raise HTTPException(status_code=500, detail="Failed to save feedback")
        
#         return {
#             "success": True,
#             "message": "Feedback submitted successfully",
#             "feedback_id": feedback_id,
#             "recommendation_id": recommendation_id
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to submit feedback: {str(e)}"
#         )

# @router.delete("/{recommendation_id}")
# async def delete_recommendation(
#     recommendation_id: str,
#     current_user: str = Depends(get_current_user)
# ):
#     """Delete a recommendation from history"""
#     try:
#         db = get_firestore_client()
        
#         # Verify recommendation exists and belongs to user
#         rec_ref = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id)
#         rec_doc = rec_ref.get()
        
#         if not rec_doc.exists:
#             raise HTTPException(status_code=404, detail="Recommendation not found")
        
#         # Soft delete
#         rec_ref.update({
#             "is_active": False,
#             "deleted_at": datetime.utcnow()
#         })
        
#         # Also update in recommendation_history
#         try:
#             db.collection("recommendation_history").document(recommendation_id).update({
#                 "is_active": False,
#                 "deleted_at": datetime.utcnow()
#             })
#         except:
#             pass  # History record might not exist
        
#         return {
#             "success": True,
#             "message": f"Recommendation {recommendation_id} deleted successfully"
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to delete recommendation: {str(e)}"
#         )

# # IMPORTANT: Put parameterized routes LAST to avoid route conflicts
# @router.get("/{recommendation_id}")
# async def get_recommendation_details(
#     recommendation_id: str,
#     current_user: str = Depends(get_current_user)
# ):
#     """Get detailed information about a specific recommendation"""
#     try:
#         db = get_firestore_client()
        
#         # Get recommendation details
#         rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
#         if not rec_doc.exists:
#             raise HTTPException(status_code=404, detail="Recommendation not found")
        
#         rec_data = rec_doc.to_dict()
        
#         # Increment view count
#         current_views = rec_data.get("view_count", 0)
#         rec_doc.reference.update({
#             "view_count": current_views + 1,
#             "last_viewed": datetime.utcnow()
#         })
        
#         # Get feedback for this recommendation
#         feedback_query = db.collection("recommendation_feedback").where("recommendation_id", "==", recommendation_id).where("user_id", "==", current_user)
#         feedback_docs = feedback_query.stream()
        
#         feedback_list = []
#         for feedback_doc in feedback_docs:
#             feedback_data = feedback_doc.to_dict()
#             feedback_list.append({
#                 "feedback_id": feedback_data["feedback_id"],
#                 "feedback_type": feedback_data["feedback_type"],
#                 "rating": feedback_data.get("rating"),
#                 "comment": feedback_data.get("comment"),
#                 "created_at": feedback_data["created_at"]
#             })
        
#         return {
#             "success": True,
#             "recommendation": {
#                 "recommendation_id": rec_data["recommendation_id"],
#                 "query": rec_data["query"],
#                 "category": rec_data.get("category"),
#                 "recommendations": rec_data["recommendations"],
#                 "generated_at": rec_data["generated_at"],
#                 "processing_time_ms": rec_data.get("processing_time_ms"),
#                 "view_count": current_views + 1,
#                 "search_context": rec_data.get("search_context", []),
#                 "profile_completeness": rec_data.get("profile_completeness", "unknown"),
#                 "questions_answered": rec_data.get("questions_answered", 0),
#                 "generation_method": rec_data.get("generation_method", "unknown")
#             },
#             "feedback": feedback_list,
#             "user_id": current_user
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to get recommendation details: {str(e)}"
#         )from fastapi import APIRouter, Depends, HTTPException, status, Query
# from pydantic import BaseModel
# from typing import Dict, Any, List, Optional
# import json
# from openai import OpenAI
# from duckduckgo_search import DDGS 
# from duckduckgo_search.exceptions import DuckDuckGoSearchException
# from itertools import islice
# import time
# import uuid
# from datetime import datetime, timedelta

# from app.core.security import get_current_user
# from app.core.firebase import get_firestore_client
# from app.core.config import get_settings
# from app.routers.conversations import save_conversation_message

# router = APIRouter()

# # Enhanced Pydantic models
# class RecommendationRequest(BaseModel):
#     query: str
#     category: Optional[str] = None
#     user_id: Optional[str] = None
#     context: Optional[Dict[str, Any]] = None

# class RecommendationItem(BaseModel):
#     title: str
#     description: Optional[str] = None
#     reasons: List[str] = []
#     category: Optional[str] = None
#     confidence_score: Optional[float] = None
#     external_links: Optional[List[str]] = None

# class RecommendationResponse(BaseModel):
#     recommendation_id: str
#     recommendations: List[RecommendationItem]
#     query: str
#     category: Optional[str] = None
#     user_id: str
#     generated_at: datetime
#     processing_time_ms: Optional[int] = None

# class RecommendationFeedback(BaseModel):
#     recommendation_id: str
#     feedback_type: str  # 'like', 'dislike', 'not_relevant', 'helpful'
#     rating: Optional[int] = None  # 1-5 stars
#     comment: Optional[str] = None
#     clicked_items: List[str] = []

# # Database helper functions
# def save_recommendation_to_db(recommendation_data: Dict[str, Any], db) -> str:
#     """Save recommendation to database and return recommendation_id"""
#     try:
#         recommendation_id = str(uuid.uuid4())
        
#         # Prepare data for database
#         db_data = {
#             "recommendation_id": recommendation_id,
#             "user_id": recommendation_data["user_id"],
#             "query": recommendation_data["query"],
#             "category": recommendation_data.get("category"),
#             "recommendations": recommendation_data["recommendations"],
#             "generated_at": datetime.utcnow(),
#             "processing_time_ms": recommendation_data.get("processing_time_ms"),
#             "search_context": recommendation_data.get("search_context", []),
#             "profile_version": recommendation_data.get("profile_version"),
#             "profile_completeness": recommendation_data.get("profile_completeness"),
#             "questions_answered": recommendation_data.get("questions_answered", 0),
#             "session_id": recommendation_data.get("session_id"),
#             "generation_method": recommendation_data.get("generation_method"),
#             "is_active": True,
#             "view_count": 0,
#             "feedback_count": 0
#         }
        
#         # Save to user-specific collection
#         db.collection("user_recommendations").document(recommendation_data["user_id"]).collection("recommendations").document(recommendation_id).set(db_data)
        
#         # Also save to recommendation history for analytics
#         history_data = {
#             "recommendation_id": recommendation_id,
#             "user_id": recommendation_data["user_id"],
#             "query": recommendation_data["query"],
#             "category": recommendation_data.get("category"),
#             "recommendations_count": len(recommendation_data["recommendations"]),
#             "profile_completeness": recommendation_data.get("profile_completeness"),
#             "created_at": datetime.utcnow(),
#             "is_bookmarked": False,
#             "tags": []
#         }
        
#         db.collection("recommendation_history").document(recommendation_id).set(history_data)
        
#         return recommendation_id
        
#     except Exception as e:
#         print(f"Error saving recommendation: {e}")
#         return None

# def get_user_recommendation_history(user_id: str, db, limit: int = 20, offset: int = 0, category: str = None):
#     """Get user's recommendation history from database"""
#     try:
#         query = db.collection("user_recommendations").document(user_id).collection("recommendations").where("is_active", "==", True)
        
#         if category:
#             query = query.where("category", "==", category)
        
#         recommendations = query.order_by("generated_at", direction="DESCENDING").limit(limit).offset(offset).stream()
        
#         history = []
#         for rec in recommendations:
#             rec_data = rec.to_dict()
#             history.append({
#                 "recommendation_id": rec_data["recommendation_id"],
#                 "query": rec_data["query"],
#                 "category": rec_data.get("category"),
#                 "recommendations_count": len(rec_data.get("recommendations", [])),
#                 "generated_at": rec_data["generated_at"],
#                 "view_count": rec_data.get("view_count", 0),
#                 "feedback_count": rec_data.get("feedback_count", 0),
#                 "session_id": rec_data.get("session_id"),
#                 "profile_completeness": rec_data.get("profile_completeness"),
#                 "generation_method": rec_data.get("generation_method")
#             })
        
#         return history
        
#     except Exception as e:
#         print(f"Error getting recommendation history: {e}")
#         return []

# def save_recommendation_feedback(recommendation_id: str, user_id: str, feedback_data: Dict[str, Any], db):
#     """Save user feedback for a recommendation"""
#     try:
#         feedback_id = str(uuid.uuid4())
        
#         feedback_doc = {
#             "feedback_id": feedback_id,
#             "recommendation_id": recommendation_id,
#             "user_id": user_id,
#             "feedback_type": feedback_data["feedback_type"],
#             "rating": feedback_data.get("rating"),
#             "comment": feedback_data.get("comment"),
#             "clicked_items": feedback_data.get("clicked_items", []),
#             "created_at": datetime.utcnow()
#         }
        
#         # Save feedback
#         db.collection("recommendation_feedback").document(feedback_id).set(feedback_doc)
        
#         # Update recommendation with feedback count
#         rec_ref = db.collection("user_recommendations").document(user_id).collection("recommendations").document(recommendation_id)
#         rec_doc = rec_ref.get()
        
#         if rec_doc.exists:
#             current_feedback_count = rec_doc.to_dict().get("feedback_count", 0)
#             rec_ref.update({"feedback_count": current_feedback_count + 1})
        
#         return feedback_id
        
#     except Exception as e:
#         print(f"Error saving feedback: {e}")
#         return None

# # PERMISSIVE Profile validation and loading functions
# def validate_profile_authenticity(profile_data: Dict[str, Any], user_id: str, db) -> Dict[str, Any]:
#     """Modified validation that allows partial profiles but detects contaminated data"""
    
#     if not profile_data or not user_id:
#         return {"valid": False, "reason": "empty_profile_or_user"}
    
#     validation_result = {
#         "valid": True,
#         "warnings": [],
#         "user_id": user_id,
#         "profile_sections": {},
#         "authenticity_score": 1.0,  # Start optimistic
#         "template_indicators": [],
#         "profile_completeness": "partial"
#     }
    
#     try:
#         # Check interview sessions for this user
#         interview_sessions = db.collection("interview_sessions").where("user_id", "==", user_id).stream()
        
#         completed_phases = set()
#         in_progress_phases = set()
#         session_data = {}
#         total_questions_answered = 0
#         has_any_session = False
        
#         for session in interview_sessions:
#             has_any_session = True
#             session_dict = session.to_dict()
#             session_data[session.id] = session_dict
            
#             phase = session_dict.get("current_phase", "unknown")
            
#             if session_dict.get("status") == "completed":
#                 completed_phases.add(phase)
#                 total_questions_answered += session_dict.get("questions_answered", 0)
#             elif session_dict.get("status") == "in_progress":
#                 in_progress_phases.add(phase)
#                 total_questions_answered += session_dict.get("questions_answered", 0)
        
#         validation_result["completed_phases"] = list(completed_phases)
#         validation_result["in_progress_phases"] = list(in_progress_phases)
#         validation_result["total_questions_answered"] = total_questions_answered
#         validation_result["has_any_session"] = has_any_session
#         validation_result["session_data"] = session_data
        
#         # Analyze profile sections
#         profile_sections = profile_data.get("recommendationProfiles", {})
#         general_profile = profile_data.get("generalprofile", {})
        
#         total_detailed_responses = 0
#         total_authenticated_responses = 0
#         total_foreign_responses = 0
#         template_indicators = []
        
#         # Check recommendation profiles
#         for section_name, section_data in profile_sections.items():
#             section_validation = {
#                 "has_data": bool(section_data),
#                 "has_session_for_phase": section_name in (completed_phases | in_progress_phases),
#                 "data_authenticity": "unknown",
#                 "detailed_response_count": 0,
#                 "authenticated_response_count": 0,
#                 "foreign_response_count": 0
#             }
            
#             if section_data and isinstance(section_data, dict):
#                 def analyze_responses(data, path=""):
#                     nonlocal total_detailed_responses, total_authenticated_responses, total_foreign_responses
                    
#                     if isinstance(data, dict):
#                         for key, value in data.items():
#                             current_path = f"{path}.{key}" if path else key
                            
#                             if isinstance(value, dict) and "value" in value:
#                                 response_value = value.get("value", "")
#                                 if isinstance(response_value, str) and len(response_value.strip()) > 10:
#                                     section_validation["detailed_response_count"] += 1
#                                     total_detailed_responses += 1
                                    
#                                     # Check authentication markers
#                                     if "user_id" in value and "updated_at" in value:
#                                         if value.get("user_id") == user_id:
#                                             section_validation["authenticated_response_count"] += 1
#                                             total_authenticated_responses += 1
#                                         else:
#                                             section_validation["foreign_response_count"] += 1
#                                             total_foreign_responses += 1
#                                             template_indicators.append(
#                                                 f"Foreign user data: {section_name}.{current_path} (from {value.get('user_id')})"
#                                             )
#                                     # If no auth markers, it could be legitimate new data or template
#                                     # We'll be more lenient here
                                
#                                 # Recursively check nested structures
#                                 if isinstance(value, dict):
#                                     analyze_responses(value, current_path)
                
#                 analyze_responses(section_data)
                
#                 # Determine authenticity for this section
#                 if section_validation["foreign_response_count"] > 0:
#                     section_validation["data_authenticity"] = "foreign_user_data"
#                 elif section_validation["detailed_response_count"] > 0:
#                     if section_validation["has_session_for_phase"]:
#                         section_validation["data_authenticity"] = "legitimate"
#                     elif section_validation["authenticated_response_count"] > 0:
#                         section_validation["data_authenticity"] = "authenticated_but_no_session"
#                     else:
#                         # This could be legitimate new data or template
#                         # Check if user has ANY interview activity
#                         if has_any_session:
#                             section_validation["data_authenticity"] = "possibly_legitimate"
#                         else:
#                             section_validation["data_authenticity"] = "suspicious_no_sessions"
#                             template_indicators.append(
#                                 f"Detailed data without any interview sessions: {section_name}"
#                             )
#                 else:
#                     section_validation["data_authenticity"] = "minimal_data"
            
#             validation_result["profile_sections"][section_name] = section_validation
        
#         # Check general profile
#         general_detailed_responses = 0
#         general_authenticated_responses = 0
        
#         def check_general_profile(data, path="generalprofile"):
#             nonlocal general_detailed_responses, general_authenticated_responses
            
#             if isinstance(data, dict):
#                 for key, value in data.items():
#                     current_path = f"{path}.{key}"
                    
#                     if isinstance(value, dict):
#                         if "value" in value and isinstance(value["value"], str) and len(value["value"].strip()) > 10:
#                             general_detailed_responses += 1
#                             if "user_id" in value and value.get("user_id") == user_id:
#                                 general_authenticated_responses += 1
#                         else:
#                             check_general_profile(value, current_path)
        
#         check_general_profile(general_profile)
        
#         # Calculate totals
#         total_responses_with_general = total_detailed_responses + general_detailed_responses
#         total_auth_with_general = total_authenticated_responses + general_authenticated_responses
        
#         # Calculate authenticity score (more lenient)
#         if total_responses_with_general > 0:
#             auth_ratio = total_auth_with_general / total_responses_with_general
#             session_factor = 1.0 if has_any_session else 0.3
#             foreign_penalty = min(total_foreign_responses / max(total_responses_with_general, 1), 0.8)
            
#             validation_result["authenticity_score"] = max(0.0, (auth_ratio * 0.6 + session_factor * 0.4) - foreign_penalty)
#         else:
#             validation_result["authenticity_score"] = 1.0
        
#         # Determine profile completeness
#         if len(completed_phases) > 0:
#             validation_result["profile_completeness"] = "complete"
#         elif has_any_session and total_questions_answered > 0:
#             validation_result["profile_completeness"] = "partial_in_progress"
#         elif total_responses_with_general > 0:
#             validation_result["profile_completeness"] = "partial_data_exists"
#         else:
#             validation_result["profile_completeness"] = "empty"
        
#         validation_result["template_indicators"] = template_indicators
#         validation_result["total_detailed_responses"] = total_responses_with_general
#         validation_result["total_authenticated_responses"] = total_auth_with_general
#         validation_result["total_foreign_responses"] = total_foreign_responses
        
#         # MODIFIED validation logic - more permissive
#         # Only mark as invalid for serious contamination issues
#         if total_foreign_responses > 0:
#             validation_result["valid"] = False
#             validation_result["reason"] = "foreign_user_data_detected"
#         elif total_responses_with_general > 10 and not has_any_session:
#             # Extensive data but no interview sessions at all - suspicious
#             validation_result["valid"] = False
#             validation_result["reason"] = "extensive_data_without_any_sessions"
#         elif validation_result["authenticity_score"] < 0.2:
#             # Very low authenticity score
#             validation_result["valid"] = False
#             validation_result["reason"] = "very_low_authenticity_score"
        
#         # Add diagnostics
#         validation_result["diagnostics"] = {
#             "has_interview_activity": has_any_session,
#             "questions_answered": total_questions_answered,
#             "data_to_session_ratio": total_responses_with_general / max(len(completed_phases | in_progress_phases), 1),
#             "authentication_percentage": (total_auth_with_general / max(total_responses_with_general, 1)) * 100,
#             "foreign_data_percentage": (total_foreign_responses / max(total_responses_with_general, 1)) * 100,
#             "profile_usability": "usable" if validation_result["valid"] else "needs_cleanup"
#         }
        
#         return validation_result
        
#     except Exception as e:
#         return {
#             "valid": False, 
#             "reason": "validation_error", 
#             "error": str(e)
#         }

# def load_user_profile(user_id: str = None) -> Dict[str, Any]:
#     """Load and validate USER-SPECIFIC profile from Firestore - matches Streamlit pattern"""
#     try:
#         db = get_firestore_client()
        
#         if not user_id:
#             print("❌ No user_id provided for profile loading")
#             return {}
        
#         print(f"🔍 Looking for profile for user: {user_id}")
        
#         # Try to find profile in multiple locations (same as Streamlit logic)
#         profile_locations = [
#             {
#                 "collection": "user_profiles",
#                 "document": f"{user_id}_profile_structure.json",
#                 "description": "Primary user_profiles collection"
#             },
#             {
#                 "collection": "user_collection", 
#                 "document": f"{user_id}_profile_structure.json",
#                 "description": "Fallback user_collection with user prefix"
#             },
#             {
#                 "collection": "user_collection",
#                 "document": "profile_strcuture.json",  # Matches Streamlit typo
#                 "description": "Streamlit default profile location"
#             },
#             {
#                 "collection": "interview_profiles",
#                 "document": f"{user_id}_profile.json", 
#                 "description": "Interview-generated profile"
#             },
#             {
#                 "collection": f"user_{user_id}",
#                 "document": "profile_structure.json",
#                 "description": "User-specific collection"
#             }
#         ]
        
#         raw_profile = None
#         profile_source = None
        
#         for location in profile_locations:
#             try:
#                 doc_ref = db.collection(location["collection"]).document(location["document"])
#                 doc = doc_ref.get()
                
#                 if doc.exists:
#                     raw_profile = doc.to_dict()
#                     profile_source = f"{location['collection']}/{location['document']}"
#                     print(f"✅ Found profile at: {profile_source}")
#                     break
                    
#             except Exception as e:
#                 print(f"❌ Error checking {location['description']}: {e}")
#                 continue
        
#         if not raw_profile:
#             print(f"❌ No profile found for user: {user_id}")
#             return {}
        
#         # Validate profile authenticity with permissive validation
#         validation = validate_profile_authenticity(raw_profile, user_id, db)
        
#         print(f"🔍 Profile validation result: {validation.get('valid')} - {validation.get('reason', 'OK')}")
#         print(f"🔍 Profile completeness: {validation.get('profile_completeness', 'unknown')}")
#         print(f"🔍 Questions answered: {validation.get('total_questions_answered', 0)}")
#         print(f"🔍 Authenticity score: {validation.get('authenticity_score', 0.0):.2f}")
        
#         if validation.get("warnings"):
#             print(f"⚠️ Profile warnings: {validation['warnings']}")
        
#         # Only reject for serious contamination
#         if not validation.get("valid"):
#             serious_issues = ["foreign_user_data_detected", "extensive_data_without_any_sessions"]
#             if validation.get("reason") in serious_issues:
#                 print(f"🚨 SERIOUS PROFILE ISSUE for user {user_id}: {validation.get('reason')}")
#                 return {
#                     "error": "contaminated_profile",
#                     "user_id": user_id,
#                     "validation": validation,
#                     "message": f"Profile validation failed: {validation.get('reason')}",
#                     "profile_source": profile_source
#                 }
#             else:
#                 print(f"⚠️ Minor profile issue for user {user_id}: {validation.get('reason')} - allowing with warnings")
        
#         # Return profile with validation info (even if partial)
#         profile_with_metadata = raw_profile.copy()
#         profile_with_metadata["_validation"] = validation
#         profile_with_metadata["_source"] = profile_source
        
#         return profile_with_metadata
        
#     except Exception as e:
#         print(f"❌ Error loading user profile for {user_id}: {e}")
#         return {}

# def search_web(query, max_results=3, max_retries=3, base_delay=1.0):
#     """Query DuckDuckGo via DDGS.text(), returning up to max_results items."""
#     for attempt in range(1, max_retries + 1):
#         try:
#             with DDGS() as ddgs:
#                 return list(islice(ddgs.text(query), max_results))
#         except DuckDuckGoSearchException as e:
#             msg = str(e)
#             if "202" in msg:
#                 wait = base_delay * (2 ** (attempt - 1))
#                 print(f"[search_web] Rate‑limited (202). Retry {attempt}/{max_retries} in {wait:.1f}s…")
#                 time.sleep(wait)
#             else:
#                 raise
#         except Exception as e:
#             print(f"[search_web] Unexpected error: {e}")
#             break
    
#     print(f"[search_web] Failed to fetch results after {max_retries} attempts.")
#     return []

# def generate_recommendations(user_profile, user_query, openai_key, category=None):
#     """Generate 3 personalized recommendations using user profile and web search - STREAMLIT COMPATIBLE"""
    
#     # Enhanced search with category context
#     if category:
#         search_query = f"{category} {user_query} recommendations 2024"
#     else:
#         search_query = f"{user_query} recommendations 2024"
    
#     search_results = search_web(search_query)
    
#     # Category-specific instructions
#     category_instructions = ""
#     if category:
#         category_lower = category.lower()
        
#         if category_lower in ["travel", "travel & destinations"]:
#             category_instructions = """
#             **CATEGORY FOCUS: TRAVEL & DESTINATIONS**
#             - Recommend specific destinations, attractions, or travel experiences
#             - Include practical travel advice (best time to visit, transportation, accommodations)
#             - Consider cultural experiences, local cuisine, historical sites, natural attractions
#             - Focus on places to visit, things to do, travel itineraries
#             - DO NOT recommend economic plans, political content, or business strategies
            
#             **EXAMPLE for Pakistan Travel Query**:
#             - "Hunza Valley, Pakistan" - Mountain valley with stunning landscapes
#             - "Lahore Food Street" - Culinary travel experience in historic city
#             - "Skardu Adventures" - Trekking and mountaineering destination
#             """
            
#         elif category_lower in ["movies", "movies & tv", "entertainment"]:
#             category_instructions = """
#             **CATEGORY FOCUS: MOVIES & TV**
#             - Recommend specific movies, TV shows, or streaming content
#             - Consider genres, directors, actors, themes that match user preferences
#             - Include where to watch (streaming platforms) if possible
#             - Focus on entertainment content, not travel or other categories
#             """
            
#         elif category_lower in ["food", "food & dining", "restaurants"]:
#             category_instructions = """
#             **CATEGORY FOCUS: FOOD & DINING**
#             - Recommend specific restaurants, cuisines, or food experiences
#             - Include local specialties, popular dishes, dining venues
#             - Consider user's location and dietary preferences
#             - Focus on food and dining experiences, not travel destinations
#             """
            
#         else:
#             category_instructions = f"""
#             **CATEGORY FOCUS: {category.upper()}**
#             - Focus recommendations specifically on {category} related content
#             - Ensure all suggestions are relevant to the {category} category
#             - Do not recommend content from other categories
#             """
    
#     prompt = f"""
#     **Task**: Generate exactly 3 highly personalized {category + ' ' if category else ''}recommendations based on:
    
#     {category_instructions}
    
#     **User Profile**:
#     {json.dumps(user_profile, indent=2)}
    
#     **User Query**:
#     "{user_query}"
    
#     **Web Context** (for reference only):
#     {search_results}
    
#     **Requirements**:
#     1. Each recommendation must directly reference profile details when available
#     2. ALL recommendations MUST be relevant to the "{category}" category if specified
#     3. Blend the user's core values and preferences from their profile
#     4. Only suggest what is asked for - no extra advice
#     5. For travel queries, recommend specific destinations, attractions, or experiences
#     6. Format as JSON array with each recommendation having:
#        - title: string (specific name of place/item/experience)
#        - description: string (brief description of what it is)
#        - reasons: array of strings (why it matches the user profile)
#        - confidence_score: float (0.0-1.0)
    
#     **CRITICAL for Travel Category**: 
#     If this is a travel recommendation, suggest actual destinations, attractions, restaurants, or travel experiences.
#     DO NOT suggest economic plans, political content, or business strategies.
    
#     **Output Example for Travel**:
#     [
#       {{
#          "title": "Hunza Valley, Pakistan",
#          "description": "Breathtaking mountain valley known for stunning landscapes and rich cultural heritage",
#          "reasons": ["Matches your love for natural beauty and cultural exploration", "Perfect for peaceful mountain retreats you prefer"],
#          "confidence_score": 0.9
#       }},
#       {{
#          "title": "Lahore Food Street, Pakistan", 
#          "description": "Historic food destination offering authentic Pakistani cuisine and cultural immersion",
#          "reasons": ["Aligns with your interest in trying traditional foods", "Offers the cultural experiences you enjoy"],
#          "confidence_score": 0.85
#       }},
#       {{
#          "title": "Skardu, Pakistan",
#          "description": "Adventure destination for trekking and mountaineering with stunning natural scenery",
#          "reasons": ["Perfect for your moderate adventure seeking preferences", "Offers the peaceful outdoor experiences you value"],
#          "confidence_score": 0.8
#       }}
#     ]
    
#     Generate your response in JSON format only.
#     """
    
#     # Setting up LLM - same as Streamlit pattern
#     client = OpenAI(api_key=openai_key)

#     response = client.chat.completions.create(
#         model="gpt-4",
#         messages=[
#             {"role": "system", "content": f"You're a recommendation engine that creates hyper-personalized {category.lower() if category else ''} suggestions. You MUST focus on {category.lower() if category else 'relevant'} content only. Output valid JSON only."},
#             {"role": "user", "content": prompt}
#         ],
#         temperature=0.7  
#     )
    
#     return response.choices[0].message.content

# # ROUTE DEFINITIONS - SPECIFIC ROUTES FIRST, PARAMETERIZED ROUTES LAST

# @router.get("/profile")
# async def get_user_profile(current_user: str = Depends(get_current_user)):
#     """Get the current user's profile - allows partial profiles"""
#     try:
#         print(f"🔍 Getting profile for user: {current_user}")
#         profile = load_user_profile(current_user)
        
#         # Handle contaminated profile (only for serious issues)
#         if isinstance(profile, dict) and profile.get("error") == "contaminated_profile":
#             validation_info = profile.get("validation", {})
            
#             # Check if it's a serious contamination or just partial data
#             if validation_info.get("reason") == "foreign_user_data_detected":
#                 raise HTTPException(
#                     status_code=422,
#                     detail={
#                         "error": "contaminated_profile",
#                         "message": "Profile contains data from other users",
#                         "user_id": current_user,
#                         "validation": validation_info,
#                         "recommended_action": "clear_contaminated_profile_and_restart_interview"
#                     }
#                 )
#             elif validation_info.get("reason") == "extensive_data_without_any_sessions":
#                 raise HTTPException(
#                     status_code=422,
#                     detail={
#                         "error": "suspicious_profile",
#                         "message": "Profile has extensive data but no interview sessions",
#                         "user_id": current_user,
#                         "validation": validation_info,
#                         "recommended_action": "start_interview_to_validate_or_clear_profile"
#                     }
#                 )
#             # For other validation issues, allow profile but with warnings
        
#         if not profile:
#             # Check interview status
#             db = get_firestore_client()
#             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#             sessions = list(sessions_ref.stream())
            
#             if not sessions:
#                 raise HTTPException(
#                     status_code=404,
#                     detail="No profile found. Please start an interview to begin creating your profile."
#                 )
            
#             # If there are sessions but no profile, suggest continuing
#             in_progress_sessions = [s for s in sessions if s.to_dict().get("status") == "in_progress"]
#             if in_progress_sessions:
#                 raise HTTPException(
#                     status_code=404,
#                     detail={
#                         "message": "Interview in progress but no profile generated yet. Continue the interview to build your profile.",
#                         "sessions": [{"session_id": s.id, "phase": s.to_dict().get("current_phase")} for s in in_progress_sessions]
#                     }
#                 )
        
#         # Return profile (even if partial)
#         clean_profile = {k: v for k, v in profile.items() if not k.startswith('_')}
#         validation_summary = profile.get("_validation", {})
        
#         response = {
#             "success": True,
#             "profile": clean_profile,
#             "user_id": current_user,
#             "profile_type": "user_specific",
#             "profile_found": True,
#             "profile_completeness": validation_summary.get("profile_completeness", "unknown"),
#             "validation_summary": {
#                 "valid": validation_summary.get("valid", True),
#                 "authenticity_score": validation_summary.get("authenticity_score", 1.0),
#                 "reason": validation_summary.get("reason"),
#                 "has_interview_activity": validation_summary.get("has_any_session", False),
#                 "questions_answered": validation_summary.get("total_questions_answered", 0),
#                 "total_responses": validation_summary.get("total_detailed_responses", 0),
#                 "authenticated_responses": validation_summary.get("total_authenticated_responses", 0),
#                 "completed_phases": validation_summary.get("completed_phases", []),
#                 "in_progress_phases": validation_summary.get("in_progress_phases", [])
#             },
#             "profile_source": profile.get("_source", "unknown")
#         }
        
#         # Add guidance based on completeness
#         # Add guidance based on completeness
#         if validation_summary.get("profile_completeness") == "partial_in_progress":
#             response["message"] = "Profile is being built as you answer interview questions. Continue the interview for more personalized recommendations."
#         elif validation_summary.get("profile_completeness") == "partial_data_exists":
#             response["message"] = "Profile has some data. Start or continue an interview to enhance personalization."
#         elif validation_summary.get("profile_completeness") == "complete":
#             response["message"] = "Profile is complete and ready for personalized recommendations."
#         elif validation_summary.get("profile_completeness") == "empty":
#             response["message"] = "Profile is empty. Start an interview to begin building your personalized profile."
        
#         return response
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"❌ Error in get_user_profile: {e}")
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to load profile: {str(e)}"
#         )

# @router.get("/categories")
# async def get_recommendation_categories():
#     """Get available recommendation categories"""
#     categories = [
#         {
#             "id": "movies",
#             "name": "Movies & TV",
#             "description": "Movie and TV show recommendations",
#             "questions_file": "moviesAndTV_tiered_questions.json"
#         },
#         {
#             "id": "food",
#             "name": "Food & Dining",
#             "description": "Restaurant and food recommendations",
#             "questions_file": "foodAndDining_tiered_questions.json"
#         },
#         {
#             "id": "travel",
#             "name": "Travel",
#             "description": "Travel destination recommendations",
#             "questions_file": "travel_tiered_questions.json"
#         },
#         {
#             "id": "books",
#             "name": "Books & Reading",
#             "description": "Book recommendations",
#             "questions_file": "books_tiered_questions.json"
#         },
#         {
#             "id": "music",
#             "name": "Music",
#             "description": "Music and artist recommendations",
#             "questions_file": "music_tiered_questions.json"
#         },
#         {
#             "id": "fitness",
#             "name": "Fitness & Wellness",
#             "description": "Fitness and wellness recommendations",
#             "questions_file": "fitness_tiered_questions.json"
#         }
#     ]
    
#     return {
#         "categories": categories,
#         "default_category": "movies"
#     }

# @router.get("/history")
# async def get_recommendation_history(
#     current_user: str = Depends(get_current_user),
#     limit: int = Query(20, description="Number of recommendations to return"),
#     offset: int = Query(0, description="Number of recommendations to skip"),
#     category: Optional[str] = Query(None, description="Filter by category"),
#     date_from: Optional[datetime] = Query(None, description="Filter from date"),
#     date_to: Optional[datetime] = Query(None, description="Filter to date")
# ):
#     """Get recommendation history for the user with enhanced filtering"""
#     try:
#         db = get_firestore_client()
        
#         # Simplified query to avoid index issues - just get user's recommendations
#         query = db.collection("user_recommendations").document(current_user).collection("recommendations")
#         query = query.where("is_active", "==", True)
#         query = query.limit(limit).offset(offset)
        
#         # Get all recommendations (without complex ordering initially)
#         recommendations = list(query.stream())
        
#         # Filter and sort in Python instead of Firestore
#         filtered_recs = []
#         for rec in recommendations:
#             rec_data = rec.to_dict()
            
#             # Apply category filter
#             if category and rec_data.get("category") != category:
#                 continue
            
#             # Apply date filters
#             rec_date = rec_data.get("generated_at")
#             if date_from and rec_date and rec_date < date_from:
#                 continue
#             if date_to and rec_date and rec_date > date_to:
#                 continue
            
#             filtered_recs.append(rec_data)
        
#         # Sort by generated_at descending
#         filtered_recs.sort(key=lambda x: x.get("generated_at", datetime.min), reverse=True)
        
#         # Format response
#         history = []
#         for rec_data in filtered_recs:
#             history.append({
#                 "recommendation_id": rec_data["recommendation_id"],
#                 "query": rec_data["query"],
#                 "category": rec_data.get("category"),
#                 "recommendations_count": len(rec_data.get("recommendations", [])),
#                 "generated_at": rec_data["generated_at"],
#                 "view_count": rec_data.get("view_count", 0),
#                 "feedback_count": rec_data.get("feedback_count", 0),
#                 "session_id": rec_data.get("session_id"),
#                 "processing_time_ms": rec_data.get("processing_time_ms"),
#                 "profile_completeness": rec_data.get("profile_completeness", "unknown"),
#                 "generation_method": rec_data.get("generation_method", "unknown")
#             })
        
#         return {
#             "success": True,
#             "history": history,
#             "total_count": len(history),
#             "user_id": current_user,
#             "filters": {
#                 "category": category,
#                 "date_from": date_from,
#                 "date_to": date_to,
#                 "limit": limit,
#                 "offset": offset
#             },
#             "note": "Using simplified query to avoid Firebase index requirements"
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to get recommendation history: {str(e)}"
#         )

# @router.get("/analytics/summary")
# async def get_recommendation_analytics(
#     current_user: str = Depends(get_current_user),
#     days: int = Query(30, description="Number of days to analyze")
# ):
#     """Get recommendation analytics for the user"""
#     try:
#         db = get_firestore_client()
        
#         # Calculate date range
#         end_date = datetime.utcnow()
#         start_date = end_date - timedelta(days=days)
        
#         # Get recommendations - simplified query
#         recommendations_ref = db.collection("user_recommendations").document(current_user).collection("recommendations")
#         recommendations = recommendations_ref.where("is_active", "==", True).stream()
        
#         analytics = {
#             "total_recommendations": 0,
#             "categories_explored": set(),
#             "query_types": {},
#             "total_views": 0,
#             "total_feedback": 0,
#             "average_processing_time": 0,
#             "recommendations_by_day": {},
#             "most_popular_category": None,
#             "engagement_rate": 0,
#             "profile_completeness_breakdown": {},
#             "generation_method_breakdown": {}
#         }
        
#         processing_times = []
#         daily_counts = {}
#         category_counts = {}
#         completeness_counts = {}
#         method_counts = {}
        
#         for rec in recommendations:
#             rec_data = rec.to_dict()
            
#             # Filter by date range
#             rec_date = rec_data.get("generated_at")
#             if rec_date and rec_date < start_date:
#                 continue
                
#             analytics["total_recommendations"] += 1
            
#             # Track categories
#             category = rec_data.get("category", "general")
#             analytics["categories_explored"].add(category)
#             category_counts[category] = category_counts.get(category, 0) + 1
            
#             # Track profile completeness
#             completeness = rec_data.get("profile_completeness", "unknown")
#             completeness_counts[completeness] = completeness_counts.get(completeness, 0) + 1
            
#             # Track generation method
#             method = rec_data.get("generation_method", "unknown")
#             method_counts[method] = method_counts.get(method, 0) + 1
            
#             # Track views and feedback
#             analytics["total_views"] += rec_data.get("view_count", 0)
#             analytics["total_feedback"] += rec_data.get("feedback_count", 0)
            
#             # Track processing times
#             if rec_data.get("processing_time_ms"):
#                 processing_times.append(rec_data["processing_time_ms"])
            
#             # Track daily activity
#             if rec_date:
#                 if hasattr(rec_date, 'date'):
#                     date_str = rec_date.date().isoformat()
#                 else:
#                     date_str = datetime.fromisoformat(str(rec_date)).date().isoformat()
                
#                 daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
        
#         # Calculate averages and insights
#         if analytics["total_recommendations"] > 0:
#             analytics["engagement_rate"] = round((analytics["total_views"] / analytics["total_recommendations"]) * 100, 2)
        
#         if processing_times:
#             analytics["average_processing_time"] = round(sum(processing_times) / len(processing_times), 2)
        
#         if category_counts:
#             analytics["most_popular_category"] = max(category_counts, key=category_counts.get)
        
#         analytics["categories_explored"] = list(analytics["categories_explored"])
#         analytics["recommendations_by_day"] = daily_counts
#         analytics["category_breakdown"] = category_counts
#         analytics["profile_completeness_breakdown"] = completeness_counts
#         analytics["generation_method_breakdown"] = method_counts
        
#         return {
#             "success": True,
#             "analytics": analytics,
#             "period": {
#                 "start_date": start_date.isoformat(),
#                 "end_date": end_date.isoformat(),
#                 "days": days
#             },
#             "user_id": current_user
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to get recommendation analytics: {str(e)}"
#         )

# @router.get("/debug/profile-location")
# async def debug_profile_location(current_user: str = Depends(get_current_user)):
#     """Debug endpoint to check where user profile is stored and validate it"""
#     try:
#         db = get_firestore_client()
        
#         locations_checked = {
#             "user_profiles": False,
#             "user_collection": False,
#             "interview_profiles": False,
#             "user_specific_collection": False,
#             "streamlit_default": False,
#             "fallback_locations": {}
#         }
        
#         profile_sources = []
        
#         # Check primary location
#         profile_doc_id = f"{current_user}_profile_structure.json"
        
#         # Check user_profiles collection
#         try:
#             profile_doc = db.collection("user_profiles").document(profile_doc_id).get()
#             locations_checked["user_profiles"] = profile_doc.exists
#             if profile_doc.exists:
#                 profile_sources.append({
#                     "location": f"user_profiles/{profile_doc_id}",
#                     "data_preview": str(profile_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["user_profiles"] = f"Error: {e}"
        
#         # Check user_collection fallback
#         try:
#             fallback_doc = db.collection("user_collection").document(profile_doc_id).get()
#             locations_checked["user_collection"] = fallback_doc.exists
#             if fallback_doc.exists:
#                 profile_sources.append({
#                     "location": f"user_collection/{profile_doc_id}",
#                     "data_preview": str(fallback_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["user_collection"] = f"Error: {e}"
        
#         # Check Streamlit default location (matches typo)
#         try:
#             streamlit_doc = db.collection("user_collection").document("profile_strcuture.json").get()
#             locations_checked["streamlit_default"] = streamlit_doc.exists
#             if streamlit_doc.exists:
#                 profile_sources.append({
#                     "location": "user_collection/profile_strcuture.json",
#                     "data_preview": str(streamlit_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["streamlit_default"] = f"Error: {e}"
        
#         # Check interview_profiles
#         try:
#             interview_doc = db.collection("interview_profiles").document(f"{current_user}_profile.json").get()
#             locations_checked["interview_profiles"] = interview_doc.exists
#             if interview_doc.exists:
#                 profile_sources.append({
#                     "location": f"interview_profiles/{current_user}_profile.json",
#                     "data_preview": str(interview_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["interview_profiles"] = f"Error: {e}"
        
#         # Check user-specific collection
#         try:
#             user_specific_doc = db.collection(f"user_{current_user}").document("profile_structure.json").get()
#             locations_checked["user_specific_collection"] = user_specific_doc.exists
#             if user_specific_doc.exists:
#                 profile_sources.append({
#                     "location": f"user_{current_user}/profile_structure.json",
#                     "data_preview": str(user_specific_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["user_specific_collection"] = f"Error: {e}"
        
#         # Check other possible locations
#         possible_docs = [
#             ("user_collection", "profile_structure.json"),
#             ("user_collection", f"{current_user}_profile.json"),
#             ("profiles", f"{current_user}.json"),
#             ("user_data", f"{current_user}_profile.json")
#         ]
        
#         for collection_name, doc_name in possible_docs:
#             try:
#                 doc_exists = db.collection(collection_name).document(doc_name).get().exists
#                 locations_checked["fallback_locations"][f"{collection_name}/{doc_name}"] = doc_exists
#                 if doc_exists:
#                     profile_sources.append({
#                         "location": f"{collection_name}/{doc_name}",
#                         "data_preview": "Found but not retrieved"
#                     })
#             except Exception as e:
#                 locations_checked["fallback_locations"][f"{collection_name}/{doc_name}"] = f"Error: {e}"
        
#         # Get interview session info
#         interview_sessions = []
#         try:
#             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#             for session in sessions_ref.stream():
#                 session_data = session.to_dict()
#                 interview_sessions.append({
#                     "session_id": session.id,
#                     "status": session_data.get("status"),
#                     "phase": session_data.get("current_phase"),
#                     "tier": session_data.get("current_tier"),
#                     "questions_answered": session_data.get("questions_answered", 0),
#                     "created_at": session_data.get("created_at"),
#                     "updated_at": session_data.get("updated_at")
#                 })
#         except Exception as e:
#             interview_sessions = [{"error": str(e)}]
        
#         # Test the current profile loading function
#         test_profile = load_user_profile(current_user)
#         profile_validation = None
        
#         if test_profile:
#             if test_profile.get("error"):
#                 profile_validation = {
#                     "status": "error",
#                     "error_type": test_profile.get("error"),
#                     "validation_details": test_profile.get("validation", {})
#                 }
#             else:
#                 profile_validation = {
#                     "status": "loaded",
#                     "validation_summary": test_profile.get("_validation", {}),
#                     "source": test_profile.get("_source", "unknown")
#                 }
        
#         return {
#             "success": True,
#             "user_id": current_user,
#             "locations_checked": locations_checked,
#             "profile_sources_found": profile_sources,
#             "expected_document": profile_doc_id,
#             "streamlit_compatible_search": True,
#             "interview_sessions": interview_sessions,
#             "profile_load_test": profile_validation,
#             "collections_searched": [
#                 "user_profiles", "user_collection", "interview_profiles", 
#                 f"user_{current_user}", "profiles", "user_data"
#             ]
#         }
        
#     except Exception as e:
#         return {
#             "success": False,
#             "error": str(e),
#             "user_id": current_user
#         }

# @router.post("/profile/regenerate")
# async def regenerate_user_profile(current_user: str = Depends(get_current_user)):
#     """Regenerate user profile from completed interview sessions"""
#     try:
#         db = get_firestore_client()
        
#         # Get all interview sessions for user (both completed and in-progress)
#         sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#         all_sessions = list(sessions_ref.stream())
        
#         completed_sessions = [s for s in all_sessions if s.to_dict().get("status") == "completed"]
#         in_progress_sessions = [s for s in all_sessions if s.to_dict().get("status") == "in_progress"]
        
#         if not completed_sessions and not in_progress_sessions:
#             raise HTTPException(
#                 status_code=400,
#                 detail="No interview sessions found. Start an interview first."
#             )
        
#         # TODO: Implement profile regeneration logic based on actual user responses
#         # This would involve:
#         # 1. Extracting responses from interview sessions
#         # 2. Building a clean profile structure
#         # 3. Saving to appropriate profile collection
        
#         return {
#             "success": True,
#             "message": "Profile regeneration initiated",
#             "user_id": current_user,
#             "completed_sessions": len(completed_sessions),
#             "in_progress_sessions": len(in_progress_sessions),
#             "note": "Profile regeneration logic needs to be implemented"
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to regenerate profile: {str(e)}"
#         )

# @router.delete("/profile/clear-contaminated")
# async def clear_contaminated_profile(current_user: str = Depends(get_current_user)):
#     """Clear contaminated profile data"""
#     try:
#         db = get_firestore_client()
        
#         # Delete the contaminated profile from all possible locations
#         profile_doc_id = f"{current_user}_profile_structure.json"
        
#         deleted_locations = []
        
#         # Try deleting from multiple locations
#         locations = [
#             ("user_profiles", profile_doc_id),
#             ("user_collection", profile_doc_id),
#             ("user_collection", "profile_strcuture.json"),  # Streamlit default
#             ("interview_profiles", f"{current_user}_profile.json"),
#         ]
        
#         for collection_name, doc_name in locations:
#             try:
#                 doc_ref = db.collection(collection_name).document(doc_name)
#                 if doc_ref.get().exists:
#                     doc_ref.delete()
#                     deleted_locations.append(f"{collection_name}/{doc_name}")
#             except Exception as e:
#                 print(f"Error deleting from {collection_name}/{doc_name}: {e}")
        
#         return {
#             "success": True,
#             "message": f"Cleared contaminated profile for user {current_user}",
#             "user_id": current_user,
#             "deleted_locations": deleted_locations,
#             "action": "profile_deleted"
#         }
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/generate", response_model=RecommendationResponse)
# async def generate_user_recommendations(
#     request: RecommendationRequest,
#     current_user: str = Depends(get_current_user)
# ):
#     """Generate recommendations using the same logic as Streamlit but enhanced for FastAPI"""
#     try:
#         start_time = datetime.utcnow()
#         settings = get_settings()
#         db = get_firestore_client()
        
#         print(f"🚀 Generating recommendations for user: {current_user}")
#         print(f"📝 Query: {request.query}")
#         print(f"🏷️ Category: {request.category}")
        
#         # Load profile (same as Streamlit)
#         user_profile = load_user_profile(current_user)
        
#         # Handle serious contamination only
#         if isinstance(user_profile, dict) and user_profile.get("error") == "contaminated_profile":
#             validation = user_profile.get("validation", {})
#             if validation.get("reason") in ["foreign_user_data_detected", "extensive_data_without_any_sessions"]:
#                 raise HTTPException(
#                     status_code=422,
#                     detail={
#                         "error": "contaminated_profile",
#                         "message": "Cannot generate recommendations with contaminated profile data",
#                         "recommended_action": "clear_profile_and_start_interview"
#                     }
#                 )
        
#         # If no profile, check if we should allow basic recommendations (same as Streamlit)
#         if not user_profile:
#             print("⚠️ No profile found - checking interview status")
            
#             # Check if user has any interview activity
#             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#             sessions = list(sessions_ref.stream())
            
#             if not sessions:
#                 # No interview started - create minimal profile for basic recommendations
#                 print("📝 No interview sessions - creating basic profile for general recommendations")
#                 user_profile = {
#                     "user_id": current_user,
#                     "generalprofile": {
#                         "corePreferences": {
#                             "note": "Basic profile - complete interview for personalized recommendations"
#                         }
#                     },
#                     "profile_completeness": "empty"
#                 }
#             else:
#                 # Has interview activity but no profile - this shouldn't happen
#                 raise HTTPException(
#                     status_code=404,
#                     detail="Interview sessions found but no profile generated. Please contact support."
#                 )
        
#         # Clean profile for AI processing (remove metadata)
#         clean_profile = {k: v for k, v in user_profile.items() if not k.startswith('_')}
        
#         # Get profile completeness info
#         validation_summary = user_profile.get("_validation", {})
#         profile_completeness = validation_summary.get("profile_completeness", "unknown")
#         questions_answered = validation_summary.get("total_questions_answered", 0)
        
#         print(f"📊 Profile completeness: {profile_completeness}")
#         print(f"📝 Questions answered: {questions_answered}")
        
#         # Generate recommendations using same function as Streamlit but with category
#         recs_json = generate_recommendations(
#             clean_profile, 
#             request.query, 
#             settings.OPENAI_API_KEY,
#             request.category  # Add category parameter
#         )
        
#         try:
#             recs = json.loads(recs_json)
            
#             # Normalize to list (same as Streamlit)
#             if isinstance(recs, dict):
#                 if "recommendations" in recs and isinstance(recs["recommendations"], list):
#                     recs = recs["recommendations"]
#                 else:
#                     recs = [recs]
            
#             if not isinstance(recs, list):
#                 raise HTTPException(
#                     status_code=500,
#                     detail="Unexpected response format – expected a list of recommendations."
#                 )
            
#             # Validate category relevance for travel
#             if request.category and request.category.lower() == "travel":
#                 travel_keywords = ["destination", "place", "visit", "travel", "city", "country", "attraction", "trip", "valley", "mountain", "beach", "street", "food", "culture", "heritage", "adventure", "pakistan", "hunza", "lahore", "skardu"]
                
#                 for i, rec in enumerate(recs):
#                     title_and_desc = (rec.get('title', '') + ' ' + rec.get('description', '')).lower()
#                     if not any(keyword in title_and_desc for keyword in travel_keywords):
#                         print(f"⚠️ Recommendation {i+1} '{rec.get('title')}' may not be travel-related")
#                         print(f"🔍 Content: {title_and_desc[:100]}...")
            
#             # Calculate processing time
#             processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
#             # Add profile completion guidance (like Streamlit would)
#             for rec in recs:
#                 if profile_completeness in ["partial_in_progress", "partial_data_exists", "empty"]:
#                     if "reasons" not in rec:
#                         rec["reasons"] = []
#                     if profile_completeness == "empty":
#                         rec["reasons"].append("Start the interview to get more personalized recommendations")
#                     else:
#                         rec["reasons"].append("Complete more interview questions for better personalization")
            
#             # Generate session ID for conversation tracking
#             session_id = str(uuid.uuid4())
            
#             # Save conversation messages (like Streamlit chat)
#             save_conversation_message(
#                 current_user, 
#                 session_id, 
#                 "user", 
#                 f"What would you like {request.category.lower() if request.category else ''} recommendations for? {request.query}", 
#                 "recommendation",
#                 f"{request.category or 'General'} Recommendation Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
#             )
            
#             # Prepare recommendation data for database
#             recommendation_data = {
#                 "user_id": current_user,
#                 "query": request.query,
#                 "category": request.category,
#                 "recommendations": recs,
#                 "processing_time_ms": int(processing_time),
#                 "search_context": search_web(f"{request.category} {request.query} recommendations 2024" if request.category else f"{request.query} recommendations 2024"),
#                 "session_id": session_id,
#                 "profile_version": clean_profile.get("version", "1.0"),
#                 "profile_completeness": profile_completeness,
#                 "questions_answered": questions_answered,
#                 "user_specific": True,
#                 "generation_method": "streamlit_compatible"
#             }
            
#             # Save to database
#             recommendation_id = save_recommendation_to_db(recommendation_data, db)
            
#             if not recommendation_id:
#                 print("⚠️ Warning: Failed to save recommendation to database")
#                 recommendation_id = str(uuid.uuid4())  # Fallback
            
#             # Format recommendations for conversation history (like Streamlit display)
#             recs_text = f"Here are your {request.category.lower() if request.category else ''} recommendations:\n\n"
            
#             for i, rec in enumerate(recs, 1):
#                 title = rec.get("title", "<no title>")
#                 description = rec.get("description", rec.get("reason", "<no description>"))
#                 reasons = rec.get("reasons", [])
                
#                 recs_text += f"**{i}. {title}**\n"
#                 recs_text += f"{description}\n"
#                 if reasons:
#                     for reason in reasons:
#                         recs_text += f"• {reason}\n"
#                 recs_text += "\n"
            
#             # Save recommendations to conversation history
#             save_conversation_message(
#                 current_user, 
#                 session_id, 
#                 "assistant", 
#                 recs_text, 
#                 "recommendation"
#             )
            
#             # Convert to RecommendationItem objects
#             recommendation_items = []
#             for rec in recs:
#                 # Use confidence score from AI or default based on profile completeness
#                 confidence_score = rec.get('confidence_score', 0.6 if profile_completeness == "empty" else 0.8)
                
#                 recommendation_items.append(RecommendationItem(
#                     title=rec.get('title', 'Recommendation'),
#                     description=rec.get('description', rec.get('reason', '')),
#                     reasons=rec.get('reasons', []),
#                     category=request.category,
#                     confidence_score=confidence_score
#                 ))
            
#             return RecommendationResponse(
#                 recommendation_id=recommendation_id,
#                 recommendations=recommendation_items,
#                 query=request.query,
#                 category=request.category,
#                 user_id=current_user,
#                 generated_at=datetime.utcnow(),
#                 processing_time_ms=int(processing_time)
#             )
            
#         except json.JSONDecodeError as e:
#             error_msg = f"Failed to parse recommendations: {str(e)}"
#             print(f"❌ JSON parsing error: {error_msg}")
#             print(f"🔍 Raw AI response: {recs_json[:500]}...")
            
#             # Save error to conversation history
#             save_conversation_message(
#                 current_user, 
#                 str(uuid.uuid4()), 
#                 "assistant", 
#                 f"Sorry, I encountered an error generating {request.category or ''} recommendations: {error_msg}", 
#                 "recommendation"
#             )
            
#             raise HTTPException(
#                 status_code=500,
#                 detail=error_msg
#             )
            
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"❌ Error generating recommendations for user {current_user}: {e}")
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to generate {request.category or ''} recommendations: {str(e)}"
#         )

# @router.post("/category")
# async def generate_category_recommendations(
#     request: RecommendationRequest,
#     current_user: str = Depends(get_current_user)
# ):
#     """Generate category-specific recommendations - redirect to main generate endpoint"""
#     # This now uses the enhanced generate endpoint
#     return await generate_user_recommendations(request, current_user)

# @router.post("/{recommendation_id}/feedback")
# async def submit_recommendation_feedback(
#     recommendation_id: str,
#     feedback: RecommendationFeedback,
#     current_user: str = Depends(get_current_user)
# ):
#     """Submit feedback for a recommendation"""
#     try:
#         db = get_firestore_client()
        
#         # Verify recommendation exists and belongs to user
#         rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
#         if not rec_doc.exists:
#             raise HTTPException(status_code=404, detail="Recommendation not found")
        
#         # Save feedback
#         feedback_data = {
#             "feedback_type": feedback.feedback_type,
#             "rating": feedback.rating,
#             "comment": feedback.comment,
#             "clicked_items": feedback.clicked_items
#         }
        
#         feedback_id = save_recommendation_feedback(recommendation_id, current_user, feedback_data, db)
        
#         if not feedback_id:
#             raise HTTPException(status_code=500, detail="Failed to save feedback")
        
#         return {
#             "success": True,
#             "message": "Feedback submitted successfully",
#             "feedback_id": feedback_id,
#             "recommendation_id": recommendation_id
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to submit feedback: {str(e)}"
#         )

# @router.delete("/{recommendation_id}")
# async def delete_recommendation(
#     recommendation_id: str,
#     current_user: str = Depends(get_current_user)
# ):
#     """Delete a recommendation from history"""
#     try:
#         db = get_firestore_client()
        
#         # Verify recommendation exists and belongs to user
#         rec_ref = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id)
#         rec_doc = rec_ref.get()
        
#         if not rec_doc.exists:
#             raise HTTPException(status_code=404, detail="Recommendation not found")
        
#         # Soft delete
#         rec_ref.update({
#             "is_active": False,
#             "deleted_at": datetime.utcnow()
#         })
        
#         # Also update in recommendation_history
#         try:
#             db.collection("recommendation_history").document(recommendation_id).update({
#                 "is_active": False,
#                 "deleted_at": datetime.utcnow()
#             })
#         except:
#             pass  # History record might not exist
        
#         return {
#             "success": True,
#             "message": f"Recommendation {recommendation_id} deleted successfully"
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to delete recommendation: {str(e)}"
#         )

# # IMPORTANT: Put parameterized routes LAST to avoid route conflicts
# @router.get("/{recommendation_id}")
# async def get_recommendation_details(
#     recommendation_id: str,
#     current_user: str = Depends(get_current_user)
# ):
#     """Get detailed information about a specific recommendation"""
#     try:
#         db = get_firestore_client()
        
#         # Get recommendation details
#         rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
#         if not rec_doc.exists:
#             raise HTTPException(status_code=404, detail="Recommendation not found")
        
#         rec_data = rec_doc.to_dict()
        
#         # Increment view count
#         current_views = rec_data.get("view_count", 0)
#         rec_doc.reference.update({
#             "view_count": current_views + 1,
#             "last_viewed": datetime.utcnow()
#         })
        
#         # Get feedback for this recommendation
#         feedback_query = db.collection("recommendation_feedback").where("recommendation_id", "==", recommendation_id).where("user_id", "==", current_user)
#         feedback_docs = feedback_query.stream()
        
#         feedback_list = []
#         for feedback_doc in feedback_docs:
#             feedback_data = feedback_doc.to_dict()
#             feedback_list.append({
#                 "feedback_id": feedback_data["feedback_id"],
#                 "feedback_type": feedback_data["feedback_type"],
#                 "rating": feedback_data.get("rating"),
#                 "comment": feedback_data.get("comment"),
#                 "created_at": feedback_data["created_at"]
#             })
        
#         return {
#             "success": True,
#             "recommendation": {
#                 "recommendation_id": rec_data["recommendation_id"],
#                 "query": rec_data["query"],
#                 "category": rec_data.get("category"),
#                 "recommendations": rec_data["recommendations"],
#                 "generated_at": rec_data["generated_at"],
#                 "processing_time_ms": rec_data.get("processing_time_ms"),
#                 "view_count": current_views + 1,
#                 "search_context": rec_data.get("search_context", []),
#                 "profile_completeness": rec_data.get("profile_completeness", "unknown"),
#                 "questions_answered": rec_data.get("questions_answered", 0),
#                 "generation_method": rec_data.get("generation_method", "unknown")
#             },
#             "feedback": feedback_list,
#             "user_id": current_user
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to get recommendation details: {str(e)}"
#         )from fastapi import APIRouter, Depends, HTTPException, status, Query
# from pydantic import BaseModel
# from typing import Dict, Any, List, Optional
# import json
# from openai import OpenAI
# from duckduckgo_search import DDGS 
# from duckduckgo_search.exceptions import DuckDuckGoSearchException
# from itertools import islice
# import time
# import uuid
# from datetime import datetime, timedelta

# from app.core.security import get_current_user
# from app.core.firebase import get_firestore_client
# from app.core.config import get_settings
# from app.routers.conversations import save_conversation_message

# router = APIRouter()

# # Enhanced Pydantic models
# class RecommendationRequest(BaseModel):
#     query: str
#     category: Optional[str] = None
#     user_id: Optional[str] = None
#     context: Optional[Dict[str, Any]] = None

# class RecommendationItem(BaseModel):
#     title: str
#     description: Optional[str] = None
#     reasons: List[str] = []
#     category: Optional[str] = None
#     confidence_score: Optional[float] = None
#     external_links: Optional[List[str]] = None

# class RecommendationResponse(BaseModel):
#     recommendation_id: str
#     recommendations: List[RecommendationItem]
#     query: str
#     category: Optional[str] = None
#     user_id: str
#     generated_at: datetime
#     processing_time_ms: Optional[int] = None

# class RecommendationFeedback(BaseModel):
#     recommendation_id: str
#     feedback_type: str  # 'like', 'dislike', 'not_relevant', 'helpful'
#     rating: Optional[int] = None  # 1-5 stars
#     comment: Optional[str] = None
#     clicked_items: List[str] = []

# # Database helper functions
# def save_recommendation_to_db(recommendation_data: Dict[str, Any], db) -> str:
#     """Save recommendation to database and return recommendation_id"""
#     try:
#         recommendation_id = str(uuid.uuid4())
        
#         # Prepare data for database
#         db_data = {
#             "recommendation_id": recommendation_id,
#             "user_id": recommendation_data["user_id"],
#             "query": recommendation_data["query"],
#             "category": recommendation_data.get("category"),
#             "recommendations": recommendation_data["recommendations"],
#             "generated_at": datetime.utcnow(),
#             "processing_time_ms": recommendation_data.get("processing_time_ms"),
#             "search_context": recommendation_data.get("search_context", []),
#             "profile_version": recommendation_data.get("profile_version"),
#             "profile_completeness": recommendation_data.get("profile_completeness"),
#             "questions_answered": recommendation_data.get("questions_answered", 0),
#             "session_id": recommendation_data.get("session_id"),
#             "generation_method": recommendation_data.get("generation_method"),
#             "is_active": True,
#             "view_count": 0,
#             "feedback_count": 0
#         }
        
#         # Save to user-specific collection
#         db.collection("user_recommendations").document(recommendation_data["user_id"]).collection("recommendations").document(recommendation_id).set(db_data)
        
#         # Also save to recommendation history for analytics
#         history_data = {
#             "recommendation_id": recommendation_id,
#             "user_id": recommendation_data["user_id"],
#             "query": recommendation_data["query"],
#             "category": recommendation_data.get("category"),
#             "recommendations_count": len(recommendation_data["recommendations"]),
#             "profile_completeness": recommendation_data.get("profile_completeness"),
#             "created_at": datetime.utcnow(),
#             "is_bookmarked": False,
#             "tags": []
#         }
        
#         db.collection("recommendation_history").document(recommendation_id).set(history_data)
        
#         return recommendation_id
        
#     except Exception as e:
#         print(f"Error saving recommendation: {e}")
#         return None

# def get_user_recommendation_history(user_id: str, db, limit: int = 20, offset: int = 0, category: str = None):
#     """Get user's recommendation history from database"""
#     try:
#         query = db.collection("user_recommendations").document(user_id).collection("recommendations").where("is_active", "==", True)
        
#         if category:
#             query = query.where("category", "==", category)
        
#         recommendations = query.order_by("generated_at", direction="DESCENDING").limit(limit).offset(offset).stream()
        
#         history = []
#         for rec in recommendations:
#             rec_data = rec.to_dict()
#             history.append({
#                 "recommendation_id": rec_data["recommendation_id"],
#                 "query": rec_data["query"],
#                 "category": rec_data.get("category"),
#                 "recommendations_count": len(rec_data.get("recommendations", [])),
#                 "generated_at": rec_data["generated_at"],
#                 "view_count": rec_data.get("view_count", 0),
#                 "feedback_count": rec_data.get("feedback_count", 0),
#                 "session_id": rec_data.get("session_id"),
#                 "profile_completeness": rec_data.get("profile_completeness"),
#                 "generation_method": rec_data.get("generation_method")
#             })
        
#         return history
        
#     except Exception as e:
#         print(f"Error getting recommendation history: {e}")
#         return []

# def save_recommendation_feedback(recommendation_id: str, user_id: str, feedback_data: Dict[str, Any], db):
#     """Save user feedback for a recommendation"""
#     try:
#         feedback_id = str(uuid.uuid4())
        
#         feedback_doc = {
#             "feedback_id": feedback_id,
#             "recommendation_id": recommendation_id,
#             "user_id": user_id,
#             "feedback_type": feedback_data["feedback_type"],
#             "rating": feedback_data.get("rating"),
#             "comment": feedback_data.get("comment"),
#             "clicked_items": feedback_data.get("clicked_items", []),
#             "created_at": datetime.utcnow()
#         }
        
#         # Save feedback
#         db.collection("recommendation_feedback").document(feedback_id).set(feedback_doc)
        
#         # Update recommendation with feedback count
#         rec_ref = db.collection("user_recommendations").document(user_id).collection("recommendations").document(recommendation_id)
#         rec_doc = rec_ref.get()
        
#         if rec_doc.exists:
#             current_feedback_count = rec_doc.to_dict().get("feedback_count", 0)
#             rec_ref.update({"feedback_count": current_feedback_count + 1})
        
#         return feedback_id
        
#     except Exception as e:
#         print(f"Error saving feedback: {e}")
#         return None

# # PERMISSIVE Profile validation and loading functions
# def validate_profile_authenticity(profile_data: Dict[str, Any], user_id: str, db) -> Dict[str, Any]:
#     """Modified validation that allows partial profiles but detects contaminated data"""
    
#     if not profile_data or not user_id:
#         return {"valid": False, "reason": "empty_profile_or_user"}
    
#     validation_result = {
#         "valid": True,
#         "warnings": [],
#         "user_id": user_id,
#         "profile_sections": {},
#         "authenticity_score": 1.0,  # Start optimistic
#         "template_indicators": [],
#         "profile_completeness": "partial"
#     }
    
#     try:
#         # Check interview sessions for this user
#         interview_sessions = db.collection("interview_sessions").where("user_id", "==", user_id).stream()
        
#         completed_phases = set()
#         in_progress_phases = set()
#         session_data = {}
#         total_questions_answered = 0
#         has_any_session = False
        
#         for session in interview_sessions:
#             has_any_session = True
#             session_dict = session.to_dict()
#             session_data[session.id] = session_dict
            
#             phase = session_dict.get("current_phase", "unknown")
            
#             if session_dict.get("status") == "completed":
#                 completed_phases.add(phase)
#                 total_questions_answered += session_dict.get("questions_answered", 0)
#             elif session_dict.get("status") == "in_progress":
#                 in_progress_phases.add(phase)
#                 total_questions_answered += session_dict.get("questions_answered", 0)
        
#         validation_result["completed_phases"] = list(completed_phases)
#         validation_result["in_progress_phases"] = list(in_progress_phases)
#         validation_result["total_questions_answered"] = total_questions_answered
#         validation_result["has_any_session"] = has_any_session
#         validation_result["session_data"] = session_data
        
#         # Analyze profile sections
#         profile_sections = profile_data.get("recommendationProfiles", {})
#         general_profile = profile_data.get("generalprofile", {})
        
#         total_detailed_responses = 0
#         total_authenticated_responses = 0
#         total_foreign_responses = 0
#         template_indicators = []
        
#         # Check recommendation profiles
#         for section_name, section_data in profile_sections.items():
#             section_validation = {
#                 "has_data": bool(section_data),
#                 "has_session_for_phase": section_name in (completed_phases | in_progress_phases),
#                 "data_authenticity": "unknown",
#                 "detailed_response_count": 0,
#                 "authenticated_response_count": 0,
#                 "foreign_response_count": 0
#             }
            
#             if section_data and isinstance(section_data, dict):
#                 def analyze_responses(data, path=""):
#                     nonlocal total_detailed_responses, total_authenticated_responses, total_foreign_responses
                    
#                     if isinstance(data, dict):
#                         for key, value in data.items():
#                             current_path = f"{path}.{key}" if path else key
                            
#                             if isinstance(value, dict) and "value" in value:
#                                 response_value = value.get("value", "")
#                                 if isinstance(response_value, str) and len(response_value.strip()) > 10:
#                                     section_validation["detailed_response_count"] += 1
#                                     total_detailed_responses += 1
                                    
#                                     # Check authentication markers
#                                     if "user_id" in value and "updated_at" in value:
#                                         if value.get("user_id") == user_id:
#                                             section_validation["authenticated_response_count"] += 1
#                                             total_authenticated_responses += 1
#                                         else:
#                                             section_validation["foreign_response_count"] += 1
#                                             total_foreign_responses += 1
#                                             template_indicators.append(
#                                                 f"Foreign user data: {section_name}.{current_path} (from {value.get('user_id')})"
#                                             )
#                                     # If no auth markers, it could be legitimate new data or template
#                                     # We'll be more lenient here
                                
#                                 # Recursively check nested structures
#                                 if isinstance(value, dict):
#                                     analyze_responses(value, current_path)
                
#                 analyze_responses(section_data)
                
#                 # Determine authenticity for this section
#                 if section_validation["foreign_response_count"] > 0:
#                     section_validation["data_authenticity"] = "foreign_user_data"
#                 elif section_validation["detailed_response_count"] > 0:
#                     if section_validation["has_session_for_phase"]:
#                         section_validation["data_authenticity"] = "legitimate"
#                     elif section_validation["authenticated_response_count"] > 0:
#                         section_validation["data_authenticity"] = "authenticated_but_no_session"
#                     else:
#                         # This could be legitimate new data or template
#                         # Check if user has ANY interview activity
#                         if has_any_session:
#                             section_validation["data_authenticity"] = "possibly_legitimate"
#                         else:
#                             section_validation["data_authenticity"] = "suspicious_no_sessions"
#                             template_indicators.append(
#                                 f"Detailed data without any interview sessions: {section_name}"
#                             )
#                 else:
#                     section_validation["data_authenticity"] = "minimal_data"
            
#             validation_result["profile_sections"][section_name] = section_validation
        
#         # Check general profile
#         general_detailed_responses = 0
#         general_authenticated_responses = 0
        
#         def check_general_profile(data, path="generalprofile"):
#             nonlocal general_detailed_responses, general_authenticated_responses
            
#             if isinstance(data, dict):
#                 for key, value in data.items():
#                     current_path = f"{path}.{key}"
                    
#                     if isinstance(value, dict):
#                         if "value" in value and isinstance(value["value"], str) and len(value["value"].strip()) > 10:
#                             general_detailed_responses += 1
#                             if "user_id" in value and value.get("user_id") == user_id:
#                                 general_authenticated_responses += 1
#                         else:
#                             check_general_profile(value, current_path)
        
#         check_general_profile(general_profile)
        
#         # Calculate totals
#         total_responses_with_general = total_detailed_responses + general_detailed_responses
#         total_auth_with_general = total_authenticated_responses + general_authenticated_responses
        
#         # Calculate authenticity score (more lenient)
#         if total_responses_with_general > 0:
#             auth_ratio = total_auth_with_general / total_responses_with_general
#             session_factor = 1.0 if has_any_session else 0.3
#             foreign_penalty = min(total_foreign_responses / max(total_responses_with_general, 1), 0.8)
            
#             validation_result["authenticity_score"] = max(0.0, (auth_ratio * 0.6 + session_factor * 0.4) - foreign_penalty)
#         else:
#             validation_result["authenticity_score"] = 1.0
        
#         # Determine profile completeness
#         if len(completed_phases) > 0:
#             validation_result["profile_completeness"] = "complete"
#         elif has_any_session and total_questions_answered > 0:
#             validation_result["profile_completeness"] = "partial_in_progress"
#         elif total_responses_with_general > 0:
#             validation_result["profile_completeness"] = "partial_data_exists"
#         else:
#             validation_result["profile_completeness"] = "empty"
        
#         validation_result["template_indicators"] = template_indicators
#         validation_result["total_detailed_responses"] = total_responses_with_general
#         validation_result["total_authenticated_responses"] = total_auth_with_general
#         validation_result["total_foreign_responses"] = total_foreign_responses
        
#         # MODIFIED validation logic - more permissive
#         # Only mark as invalid for serious contamination issues
#         if total_foreign_responses > 0:
#             validation_result["valid"] = False
#             validation_result["reason"] = "foreign_user_data_detected"
#         elif total_responses_with_general > 10 and not has_any_session:
#             # Extensive data but no interview sessions at all - suspicious
#             validation_result["valid"] = False
#             validation_result["reason"] = "extensive_data_without_any_sessions"
#         elif validation_result["authenticity_score"] < 0.2:
#             # Very low authenticity score
#             validation_result["valid"] = False
#             validation_result["reason"] = "very_low_authenticity_score"
        
#         # Add diagnostics
#         validation_result["diagnostics"] = {
#             "has_interview_activity": has_any_session,
#             "questions_answered": total_questions_answered,
#             "data_to_session_ratio": total_responses_with_general / max(len(completed_phases | in_progress_phases), 1),
#             "authentication_percentage": (total_auth_with_general / max(total_responses_with_general, 1)) * 100,
#             "foreign_data_percentage": (total_foreign_responses / max(total_responses_with_general, 1)) * 100,
#             "profile_usability": "usable" if validation_result["valid"] else "needs_cleanup"
#         }
        
#         return validation_result
        
#     except Exception as e:
#         return {
#             "valid": False, 
#             "reason": "validation_error", 
#             "error": str(e)
#         }

# def load_user_profile(user_id: str = None) -> Dict[str, Any]:
#     """Load and validate USER-SPECIFIC profile from Firestore - matches Streamlit pattern"""
#     try:
#         db = get_firestore_client()
        
#         if not user_id:
#             print("❌ No user_id provided for profile loading")
#             return {}
        
#         print(f"🔍 Looking for profile for user: {user_id}")
        
#         # Try to find profile in multiple locations (same as Streamlit logic)
#         profile_locations = [
#             {
#                 "collection": "user_profiles",
#                 "document": f"{user_id}_profile_structure.json",
#                 "description": "Primary user_profiles collection"
#             },
#             {
#                 "collection": "user_collection", 
#                 "document": f"{user_id}_profile_structure.json",
#                 "description": "Fallback user_collection with user prefix"
#             },
#             {
#                 "collection": "user_collection",
#                 "document": "profile_strcuture.json",  # Matches Streamlit typo
#                 "description": "Streamlit default profile location"
#             },
#             {
#                 "collection": "interview_profiles",
#                 "document": f"{user_id}_profile.json", 
#                 "description": "Interview-generated profile"
#             },
#             {
#                 "collection": f"user_{user_id}",
#                 "document": "profile_structure.json",
#                 "description": "User-specific collection"
#             }
#         ]
        
#         raw_profile = None
#         profile_source = None
        
#         for location in profile_locations:
#             try:
#                 doc_ref = db.collection(location["collection"]).document(location["document"])
#                 doc = doc_ref.get()
                
#                 if doc.exists:
#                     raw_profile = doc.to_dict()
#                     profile_source = f"{location['collection']}/{location['document']}"
#                     print(f"✅ Found profile at: {profile_source}")
#                     break
                    
#             except Exception as e:
#                 print(f"❌ Error checking {location['description']}: {e}")
#                 continue
        
#         if not raw_profile:
#             print(f"❌ No profile found for user: {user_id}")
#             return {}
        
#         # Validate profile authenticity with permissive validation
#         validation = validate_profile_authenticity(raw_profile, user_id, db)
        
#         print(f"🔍 Profile validation result: {validation.get('valid')} - {validation.get('reason', 'OK')}")
#         print(f"🔍 Profile completeness: {validation.get('profile_completeness', 'unknown')}")
#         print(f"🔍 Questions answered: {validation.get('total_questions_answered', 0)}")
#         print(f"🔍 Authenticity score: {validation.get('authenticity_score', 0.0):.2f}")
        
#         if validation.get("warnings"):
#             print(f"⚠️ Profile warnings: {validation['warnings']}")
        
#         # Only reject for serious contamination
#         if not validation.get("valid"):
#             serious_issues = ["foreign_user_data_detected", "extensive_data_without_any_sessions"]
#             if validation.get("reason") in serious_issues:
#                 print(f"🚨 SERIOUS PROFILE ISSUE for user {user_id}: {validation.get('reason')}")
#                 return {
#                     "error": "contaminated_profile",
#                     "user_id": user_id,
#                     "validation": validation,
#                     "message": f"Profile validation failed: {validation.get('reason')}",
#                     "profile_source": profile_source
#                 }
#             else:
#                 print(f"⚠️ Minor profile issue for user {user_id}: {validation.get('reason')} - allowing with warnings")
        
#         # Return profile with validation info (even if partial)
#         profile_with_metadata = raw_profile.copy()
#         profile_with_metadata["_validation"] = validation
#         profile_with_metadata["_source"] = profile_source
        
#         return profile_with_metadata
        
#     except Exception as e:
#         print(f"❌ Error loading user profile for {user_id}: {e}")
#         return {}

# def search_web(query, max_results=3, max_retries=3, base_delay=1.0):
#     """Query DuckDuckGo via DDGS.text(), returning up to max_results items."""
#     for attempt in range(1, max_retries + 1):
#         try:
#             with DDGS() as ddgs:
#                 return list(islice(ddgs.text(query), max_results))
#         except DuckDuckGoSearchException as e:
#             msg = str(e)
#             if "202" in msg:
#                 wait = base_delay * (2 ** (attempt - 1))
#                 print(f"[search_web] Rate‑limited (202). Retry {attempt}/{max_retries} in {wait:.1f}s…")
#                 time.sleep(wait)
#             else:
#                 raise
#         except Exception as e:
#             print(f"[search_web] Unexpected error: {e}")
#             break
    
#     print(f"[search_web] Failed to fetch results after {max_retries} attempts.")
#     return []

# def generate_recommendations(user_profile, user_query, openai_key, category=None):
#     """Generate 3 personalized recommendations using user profile and web search - STREAMLIT COMPATIBLE"""
    
#     # Enhanced search with category context
#     if category:
#         search_query = f"{category} {user_query} recommendations 2024"
#     else:
#         search_query = f"{user_query} recommendations 2024"
    
#     search_results = search_web(search_query)
    
#     # Category-specific instructions
#     category_instructions = ""
#     if category:
#         category_lower = category.lower()
        
#         if category_lower in ["travel", "travel & destinations"]:
#             category_instructions = """
#             **CATEGORY FOCUS: TRAVEL & DESTINATIONS**
#             - Recommend specific destinations, attractions, or travel experiences
#             - Include practical travel advice (best time to visit, transportation, accommodations)
#             - Consider cultural experiences, local cuisine, historical sites, natural attractions
#             - Focus on places to visit, things to do, travel itineraries
#             - DO NOT recommend economic plans, political content, or business strategies
            
#             **EXAMPLE for Pakistan Travel Query**:
#             - "Hunza Valley, Pakistan" - Mountain valley with stunning landscapes
#             - "Lahore Food Street" - Culinary travel experience in historic city
#             - "Skardu Adventures" - Trekking and mountaineering destination
#             """
            
#         elif category_lower in ["movies", "movies & tv", "entertainment"]:
#             category_instructions = """
#             **CATEGORY FOCUS: MOVIES & TV**
#             - Recommend specific movies, TV shows, or streaming content
#             - Consider genres, directors, actors, themes that match user preferences
#             - Include where to watch (streaming platforms) if possible
#             - Focus on entertainment content, not travel or other categories
#             """
            
#         elif category_lower in ["food", "food & dining", "restaurants"]:
#             category_instructions = """
#             **CATEGORY FOCUS: FOOD & DINING**
#             - Recommend specific restaurants, cuisines, or food experiences
#             - Include local specialties, popular dishes, dining venues
#             - Consider user's location and dietary preferences
#             - Focus on food and dining experiences, not travel destinations
#             """
            
#         else:
#             category_instructions = f"""
#             **CATEGORY FOCUS: {category.upper()}**
#             - Focus recommendations specifically on {category} related content
#             - Ensure all suggestions are relevant to the {category} category
#             - Do not recommend content from other categories
#             """
    
#     prompt = f"""
#     **Task**: Generate exactly 3 highly personalized {category + ' ' if category else ''}recommendations based on:
    
#     {category_instructions}
    
#     **User Profile**:
#     {json.dumps(user_profile, indent=2)}
    
#     **User Query**:
#     "{user_query}"
    
#     **Web Context** (for reference only):
#     {search_results}
    
#     **Requirements**:
#     1. Each recommendation must directly reference profile details when available
#     2. ALL recommendations MUST be relevant to the "{category}" category if specified
#     3. Blend the user's core values and preferences from their profile
#     4. Only suggest what is asked for - no extra advice
#     5. For travel queries, recommend specific destinations, attractions, or experiences
#     6. Format as JSON array with each recommendation having:
#        - title: string (specific name of place/item/experience)
#        - description: string (brief description of what it is)
#        - reasons: array of strings (why it matches the user profile)
#        - confidence_score: float (0.0-1.0)
    
#     **CRITICAL for Travel Category**: 
#     If this is a travel recommendation, suggest actual destinations, attractions, restaurants, or travel experiences.
#     DO NOT suggest economic plans, political content, or business strategies.
    
#     **Output Example for Travel**:
#     [
#       {{
#          "title": "Hunza Valley, Pakistan",
#          "description": "Breathtaking mountain valley known for stunning landscapes and rich cultural heritage",
#          "reasons": ["Matches your love for natural beauty and cultural exploration", "Perfect for peaceful mountain retreats you prefer"],
#          "confidence_score": 0.9
#       }},
#       {{
#          "title": "Lahore Food Street, Pakistan", 
#          "description": "Historic food destination offering authentic Pakistani cuisine and cultural immersion",
#          "reasons": ["Aligns with your interest in trying traditional foods", "Offers the cultural experiences you enjoy"],
#          "confidence_score": 0.85
#       }},
#       {{
#          "title": "Skardu, Pakistan",
#          "description": "Adventure destination for trekking and mountaineering with stunning natural scenery",
#          "reasons": ["Perfect for your moderate adventure seeking preferences", "Offers the peaceful outdoor experiences you value"],
#          "confidence_score": 0.8
#       }}
#     ]
    
#     Generate your response in JSON format only.
#     """
    
#     # Setting up LLM - same as Streamlit pattern
#     client = OpenAI(api_key=openai_key)

#     response = client.chat.completions.create(
#         model="gpt-4",
#         messages=[
#             {"role": "system", "content": f"You're a recommendation engine that creates hyper-personalized {category.lower() if category else ''} suggestions. You MUST focus on {category.lower() if category else 'relevant'} content only. Output valid JSON only."},
#             {"role": "user", "content": prompt}
#         ],
#         temperature=0.7  
#     )
    
#     return response.choices[0].message.content

# # ROUTE DEFINITIONS - SPECIFIC ROUTES FIRST, PARAMETERIZED ROUTES LAST

# @router.get("/profile")
# async def get_user_profile(current_user: str = Depends(get_current_user)):
#     """Get the current user's profile - allows partial profiles"""
#     try:
#         print(f"🔍 Getting profile for user: {current_user}")
#         profile = load_user_profile(current_user)
        
#         # Handle contaminated profile (only for serious issues)
#         if isinstance(profile, dict) and profile.get("error") == "contaminated_profile":
#             validation_info = profile.get("validation", {})
            
#             # Check if it's a serious contamination or just partial data
#             if validation_info.get("reason") == "foreign_user_data_detected":
#                 raise HTTPException(
#                     status_code=422,
#                     detail={
#                         "error": "contaminated_profile",
#                         "message": "Profile contains data from other users",
#                         "user_id": current_user,
#                         "validation": validation_info,
#                         "recommended_action": "clear_contaminated_profile_and_restart_interview"
#                     }
#                 )
#             elif validation_info.get("reason") == "extensive_data_without_any_sessions":
#                 raise HTTPException(
#                     status_code=422,
#                     detail={
#                         "error": "suspicious_profile",
#                         "message": "Profile has extensive data but no interview sessions",
#                         "user_id": current_user,
#                         "validation": validation_info,
#                         "recommended_action": "start_interview_to_validate_or_clear_profile"
#                     }
#                 )
#             # For other validation issues, allow profile but with warnings
        
#         if not profile:
#             # Check interview status
#             db = get_firestore_client()
#             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#             sessions = list(sessions_ref.stream())
            
#             if not sessions:
#                 raise HTTPException(
#                     status_code=404,
#                     detail="No profile found. Please start an interview to begin creating your profile."
#                 )
            
#             # If there are sessions but no profile, suggest continuing
#             in_progress_sessions = [s for s in sessions if s.to_dict().get("status") == "in_progress"]
#             if in_progress_sessions:
#                 raise HTTPException(
#                     status_code=404,
#                     detail={
#                         "message": "Interview in progress but no profile generated yet. Continue the interview to build your profile.",
#                         "sessions": [{"session_id": s.id, "phase": s.to_dict().get("current_phase")} for s in in_progress_sessions]
#                     }
#                 )
        
#         # Return profile (even if partial)
#         clean_profile = {k: v for k, v in profile.items() if not k.startswith('_')}
#         validation_summary = profile.get("_validation", {})
        
#         response = {
#             "success": True,
#             "profile": clean_profile,
#             "user_id": current_user,
#             "profile_type": "user_specific",
#             "profile_found": True,
#             "profile_completeness": validation_summary.get("profile_completeness", "unknown"),
#             "validation_summary": {
#                 "valid": validation_summary.get("valid", True),
#                 "authenticity_score": validation_summary.get("authenticity_score", 1.0),
#                 "reason": validation_summary.get("reason"),
#                 "has_interview_activity": validation_summary.get("has_any_session", False),
#                 "questions_answered": validation_summary.get("total_questions_answered", 0),
#                 "total_responses": validation_summary.get("total_detailed_responses", 0),
#                 "authenticated_responses": validation_summary.get("total_authenticated_responses", 0),
#                 "completed_phases": validation_summary.get("completed_phases", []),
#                 "in_progress_phases": validation_summary.get("in_progress_phases", [])
#             },
#             "profile_source": profile.get("_source", "unknown")
#         }
        
#         # Add guidance based on completeness
#         # Add guidance based on completeness
#         if validation_summary.get("profile_completeness") == "partial_in_progress":
#             response["message"] = "Profile is being built as you answer interview questions. Continue the interview for more personalized recommendations."
#         elif validation_summary.get("profile_completeness") == "partial_data_exists":
#             response["message"] = "Profile has some data. Start or continue an interview to enhance personalization."
#         elif validation_summary.get("profile_completeness") == "complete":
#             response["message"] = "Profile is complete and ready for personalized recommendations."
#         elif validation_summary.get("profile_completeness") == "empty":
#             response["message"] = "Profile is empty. Start an interview to begin building your personalized profile."
        
#         return response
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"❌ Error in get_user_profile: {e}")
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to load profile: {str(e)}"
#         )

# @router.get("/categories")
# async def get_recommendation_categories():
#     """Get available recommendation categories"""
#     categories = [
#         {
#             "id": "movies",
#             "name": "Movies & TV",
#             "description": "Movie and TV show recommendations",
#             "questions_file": "moviesAndTV_tiered_questions.json"
#         },
#         {
#             "id": "food",
#             "name": "Food & Dining",
#             "description": "Restaurant and food recommendations",
#             "questions_file": "foodAndDining_tiered_questions.json"
#         },
#         {
#             "id": "travel",
#             "name": "Travel",
#             "description": "Travel destination recommendations",
#             "questions_file": "travel_tiered_questions.json"
#         },
#         {
#             "id": "books",
#             "name": "Books & Reading",
#             "description": "Book recommendations",
#             "questions_file": "books_tiered_questions.json"
#         },
#         {
#             "id": "music",
#             "name": "Music",
#             "description": "Music and artist recommendations",
#             "questions_file": "music_tiered_questions.json"
#         },
#         {
#             "id": "fitness",
#             "name": "Fitness & Wellness",
#             "description": "Fitness and wellness recommendations",
#             "questions_file": "fitness_tiered_questions.json"
#         }
#     ]
    
#     return {
#         "categories": categories,
#         "default_category": "movies"
#     }

# @router.get("/history")
# async def get_recommendation_history(
#     current_user: str = Depends(get_current_user),
#     limit: int = Query(20, description="Number of recommendations to return"),
#     offset: int = Query(0, description="Number of recommendations to skip"),
#     category: Optional[str] = Query(None, description="Filter by category"),
#     date_from: Optional[datetime] = Query(None, description="Filter from date"),
#     date_to: Optional[datetime] = Query(None, description="Filter to date")
# ):
#     """Get recommendation history for the user with enhanced filtering"""
#     try:
#         db = get_firestore_client()
        
#         # Simplified query to avoid index issues - just get user's recommendations
#         query = db.collection("user_recommendations").document(current_user).collection("recommendations")
#         query = query.where("is_active", "==", True)
#         query = query.limit(limit).offset(offset)
        
#         # Get all recommendations (without complex ordering initially)
#         recommendations = list(query.stream())
        
#         # Filter and sort in Python instead of Firestore
#         filtered_recs = []
#         for rec in recommendations:
#             rec_data = rec.to_dict()
            
#             # Apply category filter
#             if category and rec_data.get("category") != category:
#                 continue
            
#             # Apply date filters
#             rec_date = rec_data.get("generated_at")
#             if date_from and rec_date and rec_date < date_from:
#                 continue
#             if date_to and rec_date and rec_date > date_to:
#                 continue
            
#             filtered_recs.append(rec_data)
        
#         # Sort by generated_at descending
#         filtered_recs.sort(key=lambda x: x.get("generated_at", datetime.min), reverse=True)
        
#         # Format response
#         history = []
#         for rec_data in filtered_recs:
#             history.append({
#                 "recommendation_id": rec_data["recommendation_id"],
#                 "query": rec_data["query"],
#                 "category": rec_data.get("category"),
#                 "recommendations_count": len(rec_data.get("recommendations", [])),
#                 "generated_at": rec_data["generated_at"],
#                 "view_count": rec_data.get("view_count", 0),
#                 "feedback_count": rec_data.get("feedback_count", 0),
#                 "session_id": rec_data.get("session_id"),
#                 "processing_time_ms": rec_data.get("processing_time_ms"),
#                 "profile_completeness": rec_data.get("profile_completeness", "unknown"),
#                 "generation_method": rec_data.get("generation_method", "unknown")
#             })
        
#         return {
#             "success": True,
#             "history": history,
#             "total_count": len(history),
#             "user_id": current_user,
#             "filters": {
#                 "category": category,
#                 "date_from": date_from,
#                 "date_to": date_to,
#                 "limit": limit,
#                 "offset": offset
#             },
#             "note": "Using simplified query to avoid Firebase index requirements"
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to get recommendation history: {str(e)}"
#         )

# @router.get("/analytics/summary")
# async def get_recommendation_analytics(
#     current_user: str = Depends(get_current_user),
#     days: int = Query(30, description="Number of days to analyze")
# ):
#     """Get recommendation analytics for the user"""
#     try:
#         db = get_firestore_client()
        
#         # Calculate date range
#         end_date = datetime.utcnow()
#         start_date = end_date - timedelta(days=days)
        
#         # Get recommendations - simplified query
#         recommendations_ref = db.collection("user_recommendations").document(current_user).collection("recommendations")
#         recommendations = recommendations_ref.where("is_active", "==", True).stream()
        
#         analytics = {
#             "total_recommendations": 0,
#             "categories_explored": set(),
#             "query_types": {},
#             "total_views": 0,
#             "total_feedback": 0,
#             "average_processing_time": 0,
#             "recommendations_by_day": {},
#             "most_popular_category": None,
#             "engagement_rate": 0,
#             "profile_completeness_breakdown": {},
#             "generation_method_breakdown": {}
#         }
        
#         processing_times = []
#         daily_counts = {}
#         category_counts = {}
#         completeness_counts = {}
#         method_counts = {}
        
#         for rec in recommendations:
#             rec_data = rec.to_dict()
            
#             # Filter by date range
#             rec_date = rec_data.get("generated_at")
#             if rec_date and rec_date < start_date:
#                 continue
                
#             analytics["total_recommendations"] += 1
            
#             # Track categories
#             category = rec_data.get("category", "general")
#             analytics["categories_explored"].add(category)
#             category_counts[category] = category_counts.get(category, 0) + 1
            
#             # Track profile completeness
#             completeness = rec_data.get("profile_completeness", "unknown")
#             completeness_counts[completeness] = completeness_counts.get(completeness, 0) + 1
            
#             # Track generation method
#             method = rec_data.get("generation_method", "unknown")
#             method_counts[method] = method_counts.get(method, 0) + 1
            
#             # Track views and feedback
#             analytics["total_views"] += rec_data.get("view_count", 0)
#             analytics["total_feedback"] += rec_data.get("feedback_count", 0)
            
#             # Track processing times
#             if rec_data.get("processing_time_ms"):
#                 processing_times.append(rec_data["processing_time_ms"])
            
#             # Track daily activity
#             if rec_date:
#                 if hasattr(rec_date, 'date'):
#                     date_str = rec_date.date().isoformat()
#                 else:
#                     date_str = datetime.fromisoformat(str(rec_date)).date().isoformat()
                
#                 daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
        
#         # Calculate averages and insights
#         if analytics["total_recommendations"] > 0:
#             analytics["engagement_rate"] = round((analytics["total_views"] / analytics["total_recommendations"]) * 100, 2)
        
#         if processing_times:
#             analytics["average_processing_time"] = round(sum(processing_times) / len(processing_times), 2)
        
#         if category_counts:
#             analytics["most_popular_category"] = max(category_counts, key=category_counts.get)
        
#         analytics["categories_explored"] = list(analytics["categories_explored"])
#         analytics["recommendations_by_day"] = daily_counts
#         analytics["category_breakdown"] = category_counts
#         analytics["profile_completeness_breakdown"] = completeness_counts
#         analytics["generation_method_breakdown"] = method_counts
        
#         return {
#             "success": True,
#             "analytics": analytics,
#             "period": {
#                 "start_date": start_date.isoformat(),
#                 "end_date": end_date.isoformat(),
#                 "days": days
#             },
#             "user_id": current_user
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to get recommendation analytics: {str(e)}"
#         )

# @router.get("/debug/profile-location")
# async def debug_profile_location(current_user: str = Depends(get_current_user)):
#     """Debug endpoint to check where user profile is stored and validate it"""
#     try:
#         db = get_firestore_client()
        
#         locations_checked = {
#             "user_profiles": False,
#             "user_collection": False,
#             "interview_profiles": False,
#             "user_specific_collection": False,
#             "streamlit_default": False,
#             "fallback_locations": {}
#         }
        
#         profile_sources = []
        
#         # Check primary location
#         profile_doc_id = f"{current_user}_profile_structure.json"
        
#         # Check user_profiles collection
#         try:
#             profile_doc = db.collection("user_profiles").document(profile_doc_id).get()
#             locations_checked["user_profiles"] = profile_doc.exists
#             if profile_doc.exists:
#                 profile_sources.append({
#                     "location": f"user_profiles/{profile_doc_id}",
#                     "data_preview": str(profile_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["user_profiles"] = f"Error: {e}"
        
#         # Check user_collection fallback
#         try:
#             fallback_doc = db.collection("user_collection").document(profile_doc_id).get()
#             locations_checked["user_collection"] = fallback_doc.exists
#             if fallback_doc.exists:
#                 profile_sources.append({
#                     "location": f"user_collection/{profile_doc_id}",
#                     "data_preview": str(fallback_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["user_collection"] = f"Error: {e}"
        
#         # Check Streamlit default location (matches typo)
#         try:
#             streamlit_doc = db.collection("user_collection").document("profile_strcuture.json").get()
#             locations_checked["streamlit_default"] = streamlit_doc.exists
#             if streamlit_doc.exists:
#                 profile_sources.append({
#                     "location": "user_collection/profile_strcuture.json",
#                     "data_preview": str(streamlit_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["streamlit_default"] = f"Error: {e}"
        
#         # Check interview_profiles
#         try:
#             interview_doc = db.collection("interview_profiles").document(f"{current_user}_profile.json").get()
#             locations_checked["interview_profiles"] = interview_doc.exists
#             if interview_doc.exists:
#                 profile_sources.append({
#                     "location": f"interview_profiles/{current_user}_profile.json",
#                     "data_preview": str(interview_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["interview_profiles"] = f"Error: {e}"
        
#         # Check user-specific collection
#         try:
#             user_specific_doc = db.collection(f"user_{current_user}").document("profile_structure.json").get()
#             locations_checked["user_specific_collection"] = user_specific_doc.exists
#             if user_specific_doc.exists:
#                 profile_sources.append({
#                     "location": f"user_{current_user}/profile_structure.json",
#                     "data_preview": str(user_specific_doc.to_dict())[:200] + "..."
#                 })
#         except Exception as e:
#             locations_checked["user_specific_collection"] = f"Error: {e}"
        
#         # Check other possible locations
#         possible_docs = [
#             ("user_collection", "profile_structure.json"),
#             ("user_collection", f"{current_user}_profile.json"),
#             ("profiles", f"{current_user}.json"),
#             ("user_data", f"{current_user}_profile.json")
#         ]
        
#         for collection_name, doc_name in possible_docs:
#             try:
#                 doc_exists = db.collection(collection_name).document(doc_name).get().exists
#                 locations_checked["fallback_locations"][f"{collection_name}/{doc_name}"] = doc_exists
#                 if doc_exists:
#                     profile_sources.append({
#                         "location": f"{collection_name}/{doc_name}",
#                         "data_preview": "Found but not retrieved"
#                     })
#             except Exception as e:
#                 locations_checked["fallback_locations"][f"{collection_name}/{doc_name}"] = f"Error: {e}"
        
#         # Get interview session info
#         interview_sessions = []
#         try:
#             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#             for session in sessions_ref.stream():
#                 session_data = session.to_dict()
#                 interview_sessions.append({
#                     "session_id": session.id,
#                     "status": session_data.get("status"),
#                     "phase": session_data.get("current_phase"),
#                     "tier": session_data.get("current_tier"),
#                     "questions_answered": session_data.get("questions_answered", 0),
#                     "created_at": session_data.get("created_at"),
#                     "updated_at": session_data.get("updated_at")
#                 })
#         except Exception as e:
#             interview_sessions = [{"error": str(e)}]
        
#         # Test the current profile loading function
#         test_profile = load_user_profile(current_user)
#         profile_validation = None
        
#         if test_profile:
#             if test_profile.get("error"):
#                 profile_validation = {
#                     "status": "error",
#                     "error_type": test_profile.get("error"),
#                     "validation_details": test_profile.get("validation", {})
#                 }
#             else:
#                 profile_validation = {
#                     "status": "loaded",
#                     "validation_summary": test_profile.get("_validation", {}),
#                     "source": test_profile.get("_source", "unknown")
#                 }
        
#         return {
#             "success": True,
#             "user_id": current_user,
#             "locations_checked": locations_checked,
#             "profile_sources_found": profile_sources,
#             "expected_document": profile_doc_id,
#             "streamlit_compatible_search": True,
#             "interview_sessions": interview_sessions,
#             "profile_load_test": profile_validation,
#             "collections_searched": [
#                 "user_profiles", "user_collection", "interview_profiles", 
#                 f"user_{current_user}", "profiles", "user_data"
#             ]
#         }
        
#     except Exception as e:
#         return {
#             "success": False,
#             "error": str(e),
#             "user_id": current_user
#         }

# @router.post("/profile/regenerate")
# async def regenerate_user_profile(current_user: str = Depends(get_current_user)):
#     """Regenerate user profile from completed interview sessions"""
#     try:
#         db = get_firestore_client()
        
#         # Get all interview sessions for user (both completed and in-progress)
#         sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#         all_sessions = list(sessions_ref.stream())
        
#         completed_sessions = [s for s in all_sessions if s.to_dict().get("status") == "completed"]
#         in_progress_sessions = [s for s in all_sessions if s.to_dict().get("status") == "in_progress"]
        
#         if not completed_sessions and not in_progress_sessions:
#             raise HTTPException(
#                 status_code=400,
#                 detail="No interview sessions found. Start an interview first."
#             )
        
#         # TODO: Implement profile regeneration logic based on actual user responses
#         # This would involve:
#         # 1. Extracting responses from interview sessions
#         # 2. Building a clean profile structure
#         # 3. Saving to appropriate profile collection
        
#         return {
#             "success": True,
#             "message": "Profile regeneration initiated",
#             "user_id": current_user,
#             "completed_sessions": len(completed_sessions),
#             "in_progress_sessions": len(in_progress_sessions),
#             "note": "Profile regeneration logic needs to be implemented"
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to regenerate profile: {str(e)}"
#         )

# @router.delete("/profile/clear-contaminated")
# async def clear_contaminated_profile(current_user: str = Depends(get_current_user)):
#     """Clear contaminated profile data"""
#     try:
#         db = get_firestore_client()
        
#         # Delete the contaminated profile from all possible locations
#         profile_doc_id = f"{current_user}_profile_structure.json"
        
#         deleted_locations = []
        
#         # Try deleting from multiple locations
#         locations = [
#             ("user_profiles", profile_doc_id),
#             ("user_collection", profile_doc_id),
#             ("user_collection", "profile_strcuture.json"),  # Streamlit default
#             ("interview_profiles", f"{current_user}_profile.json"),
#         ]
        
#         for collection_name, doc_name in locations:
#             try:
#                 doc_ref = db.collection(collection_name).document(doc_name)
#                 if doc_ref.get().exists:
#                     doc_ref.delete()
#                     deleted_locations.append(f"{collection_name}/{doc_name}")
#             except Exception as e:
#                 print(f"Error deleting from {collection_name}/{doc_name}: {e}")
        
#         return {
#             "success": True,
#             "message": f"Cleared contaminated profile for user {current_user}",
#             "user_id": current_user,
#             "deleted_locations": deleted_locations,
#             "action": "profile_deleted"
#         }
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/generate", response_model=RecommendationResponse)
# async def generate_user_recommendations(
#     request: RecommendationRequest,
#     current_user: str = Depends(get_current_user)
# ):
#     """Generate recommendations using the same logic as Streamlit but enhanced for FastAPI"""
#     try:
#         start_time = datetime.utcnow()
#         settings = get_settings()
#         db = get_firestore_client()
        
#         print(f"🚀 Generating recommendations for user: {current_user}")
#         print(f"📝 Query: {request.query}")
#         print(f"🏷️ Category: {request.category}")
        
#         # Load profile (same as Streamlit)
#         user_profile = load_user_profile(current_user)
        
#         # Handle serious contamination only
#         if isinstance(user_profile, dict) and user_profile.get("error") == "contaminated_profile":
#             validation = user_profile.get("validation", {})
#             if validation.get("reason") in ["foreign_user_data_detected", "extensive_data_without_any_sessions"]:
#                 raise HTTPException(
#                     status_code=422,
#                     detail={
#                         "error": "contaminated_profile",
#                         "message": "Cannot generate recommendations with contaminated profile data",
#                         "recommended_action": "clear_profile_and_start_interview"
#                     }
#                 )
        
#         # If no profile, check if we should allow basic recommendations (same as Streamlit)
#         if not user_profile:
#             print("⚠️ No profile found - checking interview status")
            
#             # Check if user has any interview activity
#             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#             sessions = list(sessions_ref.stream())
            
#             if not sessions:
#                 # No interview started - create minimal profile for basic recommendations
#                 print("📝 No interview sessions - creating basic profile for general recommendations")
#                 user_profile = {
#                     "user_id": current_user,
#                     "generalprofile": {
#                         "corePreferences": {
#                             "note": "Basic profile - complete interview for personalized recommendations"
#                         }
#                     },
#                     "profile_completeness": "empty"
#                 }
#             else:
#                 # Has interview activity but no profile - this shouldn't happen
#                 raise HTTPException(
#                     status_code=404,
#                     detail="Interview sessions found but no profile generated. Please contact support."
#                 )
        
#         # Clean profile for AI processing (remove metadata)
#         clean_profile = {k: v for k, v in user_profile.items() if not k.startswith('_')}
        
#         # Get profile completeness info
#         validation_summary = user_profile.get("_validation", {})
#         profile_completeness = validation_summary.get("profile_completeness", "unknown")
#         questions_answered = validation_summary.get("total_questions_answered", 0)
        
#         print(f"📊 Profile completeness: {profile_completeness}")
#         print(f"📝 Questions answered: {questions_answered}")
        
#         # Generate recommendations using same function as Streamlit but with category
#         recs_json = generate_recommendations(
#             clean_profile, 
#             request.query, 
#             settings.OPENAI_API_KEY,
#             request.category  # Add category parameter
#         )
        
#         try:
#             recs = json.loads(recs_json)
            
#             # Normalize to list (same as Streamlit)
#             if isinstance(recs, dict):
#                 if "recommendations" in recs and isinstance(recs["recommendations"], list):
#                     recs = recs["recommendations"]
#                 else:
#                     recs = [recs]
            
#             if not isinstance(recs, list):
#                 raise HTTPException(
#                     status_code=500,
#                     detail="Unexpected response format – expected a list of recommendations."
#                 )
            
#             # Validate category relevance for travel
#             if request.category and request.category.lower() == "travel":
#                 travel_keywords = ["destination", "place", "visit", "travel", "city", "country", "attraction", "trip", "valley", "mountain", "beach", "street", "food", "culture", "heritage", "adventure", "pakistan", "hunza", "lahore", "skardu"]
                
#                 for i, rec in enumerate(recs):
#                     title_and_desc = (rec.get('title', '') + ' ' + rec.get('description', '')).lower()
#                     if not any(keyword in title_and_desc for keyword in travel_keywords):
#                         print(f"⚠️ Recommendation {i+1} '{rec.get('title')}' may not be travel-related")
#                         print(f"🔍 Content: {title_and_desc[:100]}...")
            
#             # Calculate processing time
#             processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
#             # Add profile completion guidance (like Streamlit would)
#             for rec in recs:
#                 if profile_completeness in ["partial_in_progress", "partial_data_exists", "empty"]:
#                     if "reasons" not in rec:
#                         rec["reasons"] = []
#                     if profile_completeness == "empty":
#                         rec["reasons"].append("Start the interview to get more personalized recommendations")
#                     else:
#                         rec["reasons"].append("Complete more interview questions for better personalization")
            
#             # Generate session ID for conversation tracking
#             session_id = str(uuid.uuid4())
            
#             # Save conversation messages (like Streamlit chat)
#             save_conversation_message(
#                 current_user, 
#                 session_id, 
#                 "user", 
#                 f"What would you like {request.category.lower() if request.category else ''} recommendations for? {request.query}", 
#                 "recommendation",
#                 f"{request.category or 'General'} Recommendation Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
#             )
            
#             # Prepare recommendation data for database
#             recommendation_data = {
#                 "user_id": current_user,
#                 "query": request.query,
#                 "category": request.category,
#                 "recommendations": recs,
#                 "processing_time_ms": int(processing_time),
#                 "search_context": search_web(f"{request.category} {request.query} recommendations 2024" if request.category else f"{request.query} recommendations 2024"),
#                 "session_id": session_id,
#                 "profile_version": clean_profile.get("version", "1.0"),
#                 "profile_completeness": profile_completeness,
#                 "questions_answered": questions_answered,
#                 "user_specific": True,
#                 "generation_method": "streamlit_compatible"
#             }
            
#             # Save to database
#             recommendation_id = save_recommendation_to_db(recommendation_data, db)
            
#             if not recommendation_id:
#                 print("⚠️ Warning: Failed to save recommendation to database")
#                 recommendation_id = str(uuid.uuid4())  # Fallback
            
#             # Format recommendations for conversation history (like Streamlit display)
#             recs_text = f"Here are your {request.category.lower() if request.category else ''} recommendations:\n\n"
            
#             for i, rec in enumerate(recs, 1):
#                 title = rec.get("title", "<no title>")
#                 description = rec.get("description", rec.get("reason", "<no description>"))
#                 reasons = rec.get("reasons", [])
                
#                 recs_text += f"**{i}. {title}**\n"
#                 recs_text += f"{description}\n"
#                 if reasons:
#                     for reason in reasons:
#                         recs_text += f"• {reason}\n"
#                 recs_text += "\n"
            
#             # Save recommendations to conversation history
#             save_conversation_message(
#                 current_user, 
#                 session_id, 
#                 "assistant", 
#                 recs_text, 
#                 "recommendation"
#             )
            
#             # Convert to RecommendationItem objects
#             recommendation_items = []
#             for rec in recs:
#                 # Use confidence score from AI or default based on profile completeness
#                 confidence_score = rec.get('confidence_score', 0.6 if profile_completeness == "empty" else 0.8)
                
#                 recommendation_items.append(RecommendationItem(
#                     title=rec.get('title', 'Recommendation'),
#                     description=rec.get('description', rec.get('reason', '')),
#                     reasons=rec.get('reasons', []),
#                     category=request.category,
#                     confidence_score=confidence_score
#                 ))
            
#             return RecommendationResponse(
#                 recommendation_id=recommendation_id,
#                 recommendations=recommendation_items,
#                 query=request.query,
#                 category=request.category,
#                 user_id=current_user,
#                 generated_at=datetime.utcnow(),
#                 processing_time_ms=int(processing_time)
#             )
            
#         except json.JSONDecodeError as e:
#             error_msg = f"Failed to parse recommendations: {str(e)}"
#             print(f"❌ JSON parsing error: {error_msg}")
#             print(f"🔍 Raw AI response: {recs_json[:500]}...")
            
#             # Save error to conversation history
#             save_conversation_message(
#                 current_user, 
#                 str(uuid.uuid4()), 
#                 "assistant", 
#                 f"Sorry, I encountered an error generating {request.category or ''} recommendations: {error_msg}", 
#                 "recommendation"
#             )
            
#             raise HTTPException(
#                 status_code=500,
#                 detail=error_msg
#             )
            
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"❌ Error generating recommendations for user {current_user}: {e}")
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to generate {request.category or ''} recommendations: {str(e)}"
#         )

# @router.post("/category")
# async def generate_category_recommendations(
#     request: RecommendationRequest,
#     current_user: str = Depends(get_current_user)
# ):
#     """Generate category-specific recommendations - redirect to main generate endpoint"""
#     # This now uses the enhanced generate endpoint
#     return await generate_user_recommendations(request, current_user)

# @router.post("/{recommendation_id}/feedback")
# async def submit_recommendation_feedback(
#     recommendation_id: str,
#     feedback: RecommendationFeedback,
#     current_user: str = Depends(get_current_user)
# ):
#     """Submit feedback for a recommendation"""
#     try:
#         db = get_firestore_client()
        
#         # Verify recommendation exists and belongs to user
#         rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
#         if not rec_doc.exists:
#             raise HTTPException(status_code=404, detail="Recommendation not found")
        
#         # Save feedback
#         feedback_data = {
#             "feedback_type": feedback.feedback_type,
#             "rating": feedback.rating,
#             "comment": feedback.comment,
#             "clicked_items": feedback.clicked_items
#         }
        
#         feedback_id = save_recommendation_feedback(recommendation_id, current_user, feedback_data, db)
        
#         if not feedback_id:
#             raise HTTPException(status_code=500, detail="Failed to save feedback")
        
#         return {
#             "success": True,
#             "message": "Feedback submitted successfully",
#             "feedback_id": feedback_id,
#             "recommendation_id": recommendation_id
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to submit feedback: {str(e)}"
#         )

# @router.delete("/{recommendation_id}")
# async def delete_recommendation(
#     recommendation_id: str,
#     current_user: str = Depends(get_current_user)
# ):
#     """Delete a recommendation from history"""
#     try:
#         db = get_firestore_client()
        
#         # Verify recommendation exists and belongs to user
#         rec_ref = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id)
#         rec_doc = rec_ref.get()
        
#         if not rec_doc.exists:
#             raise HTTPException(status_code=404, detail="Recommendation not found")
        
#         # Soft delete
#         rec_ref.update({
#             "is_active": False,
#             "deleted_at": datetime.utcnow()
#         })
        
#         # Also update in recommendation_history
#         try:
#             db.collection("recommendation_history").document(recommendation_id).update({
#                 "is_active": False,
#                 "deleted_at": datetime.utcnow()
#             })
#         except:
#             pass  # History record might not exist
        
#         return {
#             "success": True,
#             "message": f"Recommendation {recommendation_id} deleted successfully"
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to delete recommendation: {str(e)}"
#         )

# # IMPORTANT: Put parameterized routes LAST to avoid route conflicts
# @router.get("/{recommendation_id}")
# async def get_recommendation_details(
#     recommendation_id: str,
#     current_user: str = Depends(get_current_user)
# ):
#     """Get detailed information about a specific recommendation"""
#     try:
#         db = get_firestore_client()
        
#         # Get recommendation details
#         rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
#         if not rec_doc.exists:
#             raise HTTPException(status_code=404, detail="Recommendation not found")
        
#         rec_data = rec_doc.to_dict()
        
#         # Increment view count
#         current_views = rec_data.get("view_count", 0)
#         rec_doc.reference.update({
#             "view_count": current_views + 1,
#             "last_viewed": datetime.utcnow()
#         })
        
#         # Get feedback for this recommendation
#         feedback_query = db.collection("recommendation_feedback").where("recommendation_id", "==", recommendation_id).where("user_id", "==", current_user)
#         feedback_docs = feedback_query.stream()
        
#         feedback_list = []
#         for feedback_doc in feedback_docs:
#             feedback_data = feedback_doc.to_dict()
#             feedback_list.append({
#                 "feedback_id": feedback_data["feedback_id"],
#                 "feedback_type": feedback_data["feedback_type"],
#                 "rating": feedback_data.get("rating"),
#                 "comment": feedback_data.get("comment"),
#                 "created_at": feedback_data["created_at"]
#             })
        
#         return {
#             "success": True,
#             "recommendation": {
#                 "recommendation_id": rec_data["recommendation_id"],
#                 "query": rec_data["query"],
#                 "category": rec_data.get("category"),
#                 "recommendations": rec_data["recommendations"],
#                 "generated_at": rec_data["generated_at"],
#                 "processing_time_ms": rec_data.get("processing_time_ms"),
#                 "view_count": current_views + 1,
#                 "search_context": rec_data.get("search_context", []),
#                 "profile_completeness": rec_data.get("profile_completeness", "unknown"),
#                 "questions_answered": rec_data.get("questions_answered", 0),
#                 "generation_method": rec_data.get("generation_method", "unknown")
#             },
#             "feedback": feedback_list,
#             "user_id": current_user
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to get recommendation details: {str(e)}"
#         )from fastapi import APIRouter, Depends, HTTPException, status, Query
# from pydantic import BaseModel
# from typing import Dict, Any, List, Optional
# import json
# from openai import OpenAI
# from duckduckgo_search import DDGS 
# from duckduckgo_search.exceptions import DuckDuckGoSearchException
# from itertools import islice
# import time
# import uuid
# from datetime import datetime, timedelta

# from app.core.security import get_current_user
# from app.core.firebase import get_firestore_client
# from app.core.config import get_settings
# from app.routers.conversations import save_conversation_message

# router = APIRouter()

# # Enhanced Pydantic models
# class RecommendationRequest(BaseModel):
#     query: str
#     category: Optional[str] = None
#     user_id: Optional[str] = None
#     context: Optional[Dict[str, Any]] = None

# class RecommendationItem(BaseModel):
#     title: str
#     description: Optional[str] = None
#     reasons: List[str] = []
#     category: Optional[str] = None
#     confidence_score: Optional[float] = None
#     external_links: Optional[List[str]] = None

# class RecommendationResponse(BaseModel):
#     recommendation_id: str
#     recommendations: List[RecommendationItem]
#     query: str
#     category: Optional[str] = None
#     user_id: str
#     generated_at: datetime
#     processing_time_ms: Optional[int] = None

# class RecommendationFeedback(BaseModel):
#     recommendation_id: str
#     feedback_type: str  # 'like', 'dislike', 'not_relevant', 'helpful'
#     rating: Optional[int] = None  # 1-5 stars
#     comment: Optional[str] = None
#     clicked_items: List[str] = []

# # Database helper functions
# def save_recommendation_to_db(recommendation_data: Dict[str, Any], db) -> str:
#     """Save recommendation to database and return recommendation_id"""
#     try:
#         recommendation_id = str(uuid.uuid4())
        
#         # Prepare data for database
#         db_data = {
#             "recommendation_id": recommendation_id,
#             "user_id": recommendation_data["user_id"],
#             "query": recommendation_data["query"],
#             "category": recommendation_data.get("category"),
#             "recommendations": recommendation_data["recommendations"],
#             "generated_at": datetime.utcnow(),
#             "processing_time_ms": recommendation_data.get("processing_time_ms"),
#             "search_context": recommendation_data.get("search_context", []),
#             "profile_version": recommendation_data.get("profile_version"),
#             "profile_completeness": recommendation_data.get("profile_completeness"),
#             "questions_answered": recommendation_data.get("questions_answered", 0),
#             "session_id": recommendation_data.get("session_id"),
#             "generation_method": recommendation_data.get("generation_method"),
#             "is_active": True,
#             "view_count": 0,
#             "feedback_count": 0
#         }
        
#         # Save to user-specific collection
#         db.collection("user_recommendations").document(recommendation_data["user_id"]).collection("recommendations").document(recommendation_id).set(db_data)
        
#         # Also save to recommendation history for analytics
#         history_data = {
#             "recommendation_id": recommendation_id,
#             "user_id": recommendation_data["user_id"],
#             "query": recommendation_data["query"],
#             "category": recommendation_data.get("category"),
#             "recommendations_count": len(recommendation_data["recommendations"]),
#             "profile_completeness": recommendation_data.get("profile_completeness"),
#             "created_at": datetime.utcnow(),
#             "is_bookmarked": False,
#             "tags": []
#         }
        
#         db.collection("recommendation_history").document(recommendation_id).set(history_data)
        
#         return recommendation_id
        
#     except Exception as e:
#         print(f"Error saving recommendation: {e}")
#         return None

# def get_user_recommendation_history(user_id: str, db, limit: int = 20, offset: int = 0, category: str = None):
#     """Get user's recommendation history from database"""
#     try:
#         query = db.collection("user_recommendations").document(user_id).collection("recommendations").where("is_active", "==", True)
        
#         if category:
#             query = query.where("category", "==", category)
        
#         recommendations = query.order_by("generated_at", direction="DESCENDING").limit(limit).offset(offset).stream()
        
#         history = []
#         for rec in recommendations:
#             rec_data = rec.to_dict()
#             history.append({
#                 "recommendation_id": rec_data["recommendation_id"],
#                 "query": rec_data["query"],
#                 "category": rec_data.get("category"),
#                 "recommendations_count": len(rec_data.get("recommendations", [])),
#                 "generated_at": rec_data["generated_at"],
#                 "view_count": rec_data.get("view_count", 0),
#                 "feedback_count": rec_data.get("feedback_count", 0),
#                 "session_id": rec_data.get("session_id"),
#                 "profile_completeness": rec_data.get("profile_completeness"),
#                 "generation_method": rec_data.get("generation_method")
#             })
        
#         return history
        
#     except Exception as e:
#         print(f"Error getting recommendation history: {e}")
#         return []

# def save_recommendation_feedback(recommendation_id: str, user_id: str, feedback_data: Dict[str, Any], db):
#     """Save user feedback for a recommendation"""
#     try:
#         feedback_id = str(uuid.uuid4())
        
#         feedback_doc = {
#             "feedback_id": feedback_id,
#             "recommendation_id": recommendation_id,
#             "user_id": user_id,
#             "feedback_type": feedback_data["feedback_type"],
#             "rating": feedback_data.get("rating"),
#             "comment": feedback_data.get("comment"),
#             "clicked_items": feedback_data.get("clicked_items", []),
#             "created_at": datetime.utcnow()
#         }
        
#         # Save feedback
#         db.collection("recommendation_feedback").document(feedback_id).set(feedback_doc)
        
#         # Update recommendation with feedback count
#         rec_ref = db.collection("user_recommendations").document(user_id).collection("recommendations").document(recommendation_id)
#         rec_doc = rec_ref.get()
        
#         if rec_doc.exists:
#             current_feedback_count = rec_doc.to_dict().get("feedback_count", 0)
#             rec_ref.update({"feedback_count": current_feedback_count + 1})
        
#         return feedback_id
        
#     except Exception as e:
#         print(f"Error saving feedback: {e}")
#         return None

# # PERMISSIVE Profile validation and loading functions
# def validate_profile_authenticity(profile_data: Dict[str, Any], user_id: str, db) -> Dict[str, Any]:
#     """Modified validation that allows partial profiles but detects contaminated data"""
    
#     if not profile_data or not user_id:
#         return {"valid": False, "reason": "empty_profile_or_user"}
    
#     validation_result = {
#         "valid": True,
#         "warnings": [],
#         "user_id": user_id,
#         "profile_sections": {},
#         "authenticity_score": 1.0,  # Start optimistic
#         "template_indicators": [],
#         "profile_completeness": "partial"
#     }
    
#     try:
#         # Check interview sessions for this user
#         interview_sessions = db.collection("interview_sessions").where("user_id", "==", user_id).stream()
        
#         completed_phases = set()
#         in_progress_phases = set()
#         session_data = {}
#         total_questions_answered = 0
#         has_any_session = False
        
#         for session in interview_sessions:
#             has_any_session = True
#             session_dict = session.to_dict()
#             session_data[session.id] = session_dict
            
#             phase = session_dict.get("current_phase", "unknown")
            
#             if session_dict.get("status") == "completed":
#                 completed_phases.add(phase)
#                 total_questions_answered += session_dict.get("questions_answered", 0)
#             elif session_dict.get("status") == "in_progress":
#                 in_progress_phases.add(phase)
#                 total_questions_answered += session_dict.get("questions_answered", 0)
        
#         validation_result["completed_phases"] = list(completed_phases)
#         validation_result["in_progress_phases"] = list(in_progress_phases)
#         validation_result["total_questions_answered"] = total_questions_answered
#         validation_result["has_any_session"] = has_any_session
#         validation_result["session_data"] = session_data
        
#         # Analyze profile sections
#         profile_sections = profile_data.get("recommendationProfiles", {})
#         general_profile = profile_data.get("generalprofile", {})
        
#         total_detailed_responses = 0
#         total_authenticated_responses = 0
#         total_foreign_responses = 0
#         template_indicators = []
        
#         # Check recommendation profiles
#         for section_name, section_data in profile_sections.items():
#             section_validation = {
#                 "has_data": bool(section_data),
#                 "has_session_for_phase": section_name in (completed_phases | in_progress_phases),
#                 "data_authenticity": "unknown",
#                 "detailed_response_count": 0,
#                 "authenticated_response_count": 0,
#                 "foreign_response_count": 0
#             }
            
#             if section_data and isinstance(section_data, dict):
#                 def analyze_responses(data, path=""):
#                     nonlocal total_detailed_responses, total_authenticated_responses, total_foreign_responses
                    
#                     if isinstance(data, dict):
#                         for key, value in data.items():
#                             current_path = f"{path}.{key}" if path else key
                            
#                             if isinstance(value, dict) and "value" in value:
#                                 response_value = value.get("value", "")
#                                 if isinstance(response_value, str) and len(response_value.strip()) > 10:
#                                     section_validation["detailed_response_count"] += 1
#                                     total_detailed_responses += 1
                                    
#                                     # Check authentication markers
#                                     if "user_id" in value and "updated_at" in value:
#                                         if value.get("user_id") == user_id:
#                                             section_validation["authenticated_response_count"] += 1
#                                             total_authenticated_responses += 1
#                                         else:
#                                             section_validation["foreign_response_count"] += 1
#                                             total_foreign_responses += 1
#                                             template_indicators.append(
#                                                 f"Foreign user data: {section_name}.{current_path} (from {value.get('user_id')})"
#                                             )
#                                     # If no auth markers, it could be legitimate new data or template
#                                     # We'll be more lenient here
                                
#                                 # Recursively check nested structures
#                                 if isinstance(value, dict):
#                                     analyze_responses(value, current_path)
                
#                 analyze_responses(section_data)
                
#                 # Determine authenticity for this section
#                 if section_validation["foreign_response_count"] > 0:
#                     section_validation["data_authenticity"] = "foreign_user_data"
#                 elif section_validation["detailed_response_count"] > 0:
#                     if section_validation["has_session_for_phase"]:
#                         section_validation["data_authenticity"] = "legitimate"
#                     elif section_validation["authenticated_response_count"] > 0:
#                         section_validation["data_authenticity"] = "authenticated_but_no_session"
#                     else:
#                         # This could be legitimate new data or template
#                         # Check if user has ANY interview activity
#                         if has_any_session:
#                             section_validation["data_authenticity"] = "possibly_legitimate"
#                         else:
#                             section_validation["data_authenticity"] = "suspicious_no_sessions"
#                             template_indicators.append(
#                                 f"Detailed data without any interview sessions: {section_name}"
#                             )
#                 else:
#                     section_validation["data_authenticity"] = "minimal_data"
            
#             validation_result["profile_sections"][section_name] = section_validation
        
#         # Check general profile
#         general_detailed_responses = 0
#         general_authenticated_responses = 0
        
#         def check_general_profile(data, path="generalprofile"):
#             nonlocal general_detailed_responses, general_authenticated_responses
            
#             if isinstance(data, dict):
#                 for key, value in data.items():
#                     current_path = f"{path}.{key}"
                    
#                     if isinstance(value, dict):
#                         if "value" in value and isinstance(value["value"], str) and len(value["value"].strip()) > 10:
#                             general_detailed_responses += 1
#                             if "user_id" in value and value.get("user_id") == user_id:
#                                 general_authenticated_responses += 1
#                         else:
#                             check_general_profile(value, current_path)
        
#         check_general_profile(general_profile)
        
#         # Calculate totals
#         total_responses_with_general = total_detailed_responses + general_detailed_responses
#         total_auth_with_general = total_authenticated_responses + general_authenticated_responses
        
#         # Calculate authenticity score (more lenient)
#         if total_responses_with_general > 0:
#             auth_ratio = total_auth_with_general / total_responses_with_general
#             session_factor = 1.0 if has_any_session else 0.3
#             foreign_penalty = min(total_foreign_responses / max(total_responses_with_general, 1), 0.8)
            
#             validation_result["authenticity_score"] = max(0.0, (auth_ratio * 0.6 + session_factor * 0.4) - foreign_penalty)
#         else:
#             validation_result["authenticity_score"] = 1.0
        
#         # Determine profile completeness
#         if len(completed_phases) > 0:
#             validation_result["profile_completeness"] = "complete"
#         elif has_any_session and total_questions_answered > 0:
#             validation_result["profile_completeness"] = "partial_in_progress"
#         elif total_responses_with_general > 0:
#             validation_result["profile_completeness"] = "partial_data_exists"
#         else:
#             validation_result["profile_completeness"] = "empty"
        
#         validation_result["template_indicators"] = template_indicators
#         validation_result["total_detailed_responses"] = total_responses_with_general
#         validation_result["total_authenticated_responses"] = total_auth_with_general
#         validation_result["total_foreign_responses"] = total_foreign_responses
        
#         # MODIFIED validation logic - more permissive
#         # Only mark as invalid for serious contamination issues
#         if total_foreign_responses > 0:
#             validation_result["valid"] = False
#             validation_result["reason"] = "foreign_user_data_detected"
#         elif total_responses_with_general > 10 and not has_any_session:
#             # Extensive data but no interview sessions at all - suspicious
#             validation_result["valid"] = False
#             validation_result["reason"] = "extensive_data_without_any_sessions"
#         elif validation_result["authenticity_score"] < 0.2:
#             # Very low authenticity score
#             validation_result["valid"] = False
#             validation_result["reason"] = "very_low_authenticity_score"
        
#         # Add diagnostics
#         validation_result["diagnostics"] = {
#             "has_interview_activity": has_any_session,
#             "questions_answered": total_questions_answered,
#             "data_to_session_ratio": total_responses_with_general / max(len(completed_phases | in_progress_phases), 1),
#             "authentication_percentage": (total_auth_with_general / max(total_responses_with_general, 1)) * 100,
#             "foreign_data_percentage": (total_foreign_responses / max(total_responses_with_general, 1)) * 100,
#             "profile_usability": "usable" if validation_result["valid"] else "needs_cleanup"
#         }
        
#         return validation_result
        
#     except Exception as e:
#         return {
#             "valid": False, 
#             "reason": "validation_error", 
#             "error": str(e)
#         }

# def load_user_profile(user_id: str = None) -> Dict[str, Any]:
#     """Load and validate USER-SPECIFIC profile from Firestore - matches Streamlit pattern"""
#     try:
#         db = get_firestore_client()
        
#         if not user_id:
#             print("❌ No user_id provided for profile loading")
#             return {}
        
#         print(f"🔍 Looking for profile for user: {user_id}")
        
#         # Try to find profile in multiple locations (same as Streamlit logic)
#         profile_locations = [
#             {
#                 "collection": "user_profiles",
#                 "document": f"{user_id}_profile_structure.json",
#                 "description": "Primary user_profiles collection"
#             },
#             {
#                 "collection": "user_collection", 
#                 "document": f"{user_id}_profile_structure.json",
#                 "description": "Fallback user_collection with user prefix"
#             },
#             {
#                 "collection": "user_collection",
#                 "document": "profile_strcuture.json",  # Matches Streamlit typo
#                 "description": "Streamlit default profile location"
#             },
#             {
#                 "collection": "interview_profiles",
#                 "document": f"{user_id}_profile.json", 
#                 "description": "Interview-generated profile"
#             },
#             {
#                 "collection": f"user_{user_id}",
#                 "document": "profile_structure.json",
#                 "description": "User-specific collection"
#             }
#         ]
        
#         raw_profile = None
#         profile_source = None
        
#         for location in profile_locations:
#             try:
#                 doc_ref = db.collection(location["collection"]).document(location["document"])
#                 doc = doc_ref.get()
                
#                 if doc.exists:
#                     raw_profile = doc.to_dict()
#                     profile_source = f"{location['collection']}/{location['document']}"
#                     print(f"✅ Found profile at: {profile_source}")
#                     break
                    
#             except Exception as e:
#                 print(f"❌ Error checking {location['description']}: {e}")
#                 continue
        
#         if not raw_profile:
#             print(f"❌ No profile found for user: {user_id}")
#             return {}
        
#         # Validate profile authenticity with permissive validation
#         validation = validate_profile_authenticity(raw_profile, user_id, db)
        
#         print(f"🔍 Profile validation result: {validation.get('valid')} - {validation.get('reason', 'OK')}")
#         print(f"🔍 Profile completeness: {validation.get('profile_completeness', 'unknown')}")
#         print(f"🔍 Questions answered: {validation.get('total_questions_answered', 0)}")
#         print(f"🔍 Authenticity score: {validation.get('authenticity_score', 0.0):.2f}")
        
#         if validation.get("warnings"):
#             print(f"⚠️ Profile warnings: {validation['warnings']}")
        
#         # Only reject for serious contamination
#         if not validation.get("valid"):
#             serious_issues = ["foreign_user_data_detected", "extensive_data_without_any_sessions"]
#             if validation.get("reason") in serious_issues:
#                 print(f"🚨 SERIOUS PROFILE ISSUE for user {user_id}: {validation.get('reason')}")
#                 return {
#                     "error": "contaminated_profile",
#                     "user_id": user_id,
#                     "validation": validation,
#                     "message": f"Profile validation failed: {validation.get('reason')}",
#                     "profile_source": profile_source
#                 }
#             else:
#                 print(f"⚠️ Minor profile issue for user {user_id}: {validation.get('reason')} - allowing with warnings")
        
#         # Return profile with validation info (even if partial)
#         profile_with_metadata = raw_profile.copy()
#         profile_with_metadata["_validation"] = validation
#         profile_with_metadata["_source"] = profile_source
        
#         return profile_with_metadata
        
#     except Exception as e:
#         print(f"❌ Error loading user profile for {user_id}: {e}")
#         return {}

# def search_web(query, max_results=3, max_retries=3, base_delay=1.0):
#     """Query DuckDuckGo via DDGS.text(), returning up to max_results items."""
#     for attempt in range(1, max_retries + 1):
#         try:
#             with DDGS() as ddgs:
#                 return list(islice(ddgs.text(query), max_results))
#         except DuckDuckGoSearchException as e:
#             msg = str(e)
#             if "202" in msg:
#                 wait = base_delay * (2 ** (attempt - 1))
#                 print(f"[search_web] Rate‑limited (202). Retry {attempt}/{max_retries} in {wait:.1f}s…")
#                 time.sleep(wait)
#             else:
#                 raise
#         except Exception as e:
#             print(f"[search_web] Unexpected error: {e}")
#             break
    
#     print(f"[search_web] Failed to fetch results after {max_retries} attempts.")
#     return []

# def generate_recommendations(user_profile, user_query, openai_key, category=None):
#     """Generate 3 personalized recommendations using user profile and web search - STREAMLIT COMPATIBLE"""
    
#     # Enhanced search with category context
#     if category:
#         search_query = f"{category} {user_query} recommendations 2024"
#     else:
#         search_query = f"{user_query} recommendations 2024"
    
#     search_results = search_web(search_query)
    
#     # Category-specific instructions
#     category_instructions = ""
#     if category:
#         category_lower = category.lower()
        
#         if category_lower in ["travel", "travel & destinations"]:
#             category_instructions = """
#             **CATEGORY FOCUS: TRAVEL & DESTINATIONS**
#             - Recommend specific destinations, attractions, or travel experiences
#             - Include practical travel advice (best time to visit, transportation, accommodations)
#             - Consider cultural experiences, local cuisine, historical sites, natural attractions
#             - Focus on places to visit, things to do, travel itineraries
#             - DO NOT recommend economic plans, political content, or business strategies
            
#             **EXAMPLE for Pakistan Travel Query**:
#             - "Hunza Valley, Pakistan" - Mountain valley with stunning landscapes
#             - "Lahore Food Street" - Culinary travel experience in historic city
#             - "Skardu Adventures" - Trekking and mountaineering destination
#             """
            
#         elif category_lower in ["movies", "movies & tv", "entertainment"]:
#             category_instructions = """
#             **CATEGORY FOCUS: MOVIES & TV**
#             - Recommend specific movies, TV shows, or streaming content
#             - Consider genres, directors, actors, themes that match user preferences
#             - Include where to watch (streaming platforms) if possible
#             - Focus on entertainment content, not travel or other categories
#             """
            
#         elif category_lower in ["food", "food & dining", "restaurants"]:
#             category_instructions = """
#             **CATEGORY FOCUS: FOOD & DINING**
#             - Recommend specific restaurants, cuisines, or food experiences
#             - Include local specialties, popular dishes, dining venues
#             - Consider user's location and dietary preferences
#             - Focus on food and dining experiences, not travel destinations
#             """
            
#         else:
#             category_instructions = f"""
#             **CATEGORY FOCUS: {category.upper()}**
#             - Focus recommendations specifically on {category} related content
#             - Ensure all suggestions are relevant to the {category} category
#             - Do not recommend content from other categories
#             """
    
#     prompt = f"""
#     **Task**: Generate exactly 3 highly personalized {category + ' ' if category else ''}recommendations based on:
    
#     {category_instructions}
    
#     **User Profile**:
#     {json.dumps(user_profile, indent=2)}
    
#     **User Query**:
#     "{user_query}"
    
#     **Web Context** (for reference only):
#     {search_results}
    
#     **Requirements**:
#     1. Each recommendation must directly reference profile details when available
#     2. ALL recommendations MUST be relevant to the "{category}" category if specified
#     3. Blend the user's core values and preferences from their profile
#     4. Only suggest what is asked for - no extra advice
#     5. For travel queries, recommend specific destinations, attractions, or experiences
#     6. Format as JSON array with each recommendation having:
#        - title: string (specific name of place/item/experience)
#        - description: string (brief description of what it is)
#        - reasons: array of strings (why it matches the user profile)
#        - confidence_score: float (0.0-1.0)
    
#     **CRITICAL for Travel Category**: 
#     If this is a travel recommendation, suggest actual destinations, attractions, restaurants, or travel experiences.
#     DO NOT suggest economic plans, political content, or business strategies.
    
#     **Output Example for Travel**:
#     [
#       {{
#          "title": "Hunza Valley, Pakistan",
#          "description": "Breathtaking mountain valley known for stunning landscapes and rich cultural heritage",
#          "reasons": ["Matches your love for natural beauty and cultural exploration", "Perfect for peaceful mountain retreats you prefer"],
#          "confidence_score": 0.9
#       }},
#       {{
#          "title": "Lahore Food Street, Pakistan", 
#          "description": "Historic food destination offering authentic Pakistani cuisine and cultural immersion",
#          "reasons": ["Aligns with your interest in trying traditional foods", "Offers the cultural experiences you enjoy"],
#          "confidence_score": 0.85
#       }},
#       {{
#          "title": "Skardu, Pakistan",
#          "description": "Adventure destination for trekking and mountaineering with stunning natural scenery",
#          "reasons": ["Perfect for your moderate adventure seeking preferences", "Offers the peaceful outdoor experiences you value"],
#          "confidence_score": 0.8
#       }}
#     ]
    
#     Generate your response in JSON format only.
#     """
    
#     # Setting up LLM - same as Streamlit pattern
#     client = OpenAI(api_key=openai_key)

#     response = client.chat.completions.create(
#         model="gpt-4",
#         messages=[
#             {"role": "system", "content": f"You're a recommendation engine that creates hyper-personalized {category.lower() if category else ''} suggestions. You MUST focus on {category.lower() if category else 'relevant'} content only. Output valid JSON only."},
#             {"role": "user", "content": prompt}
#         ],
#         temperature=0.7  
#     )
    
#     return response.choices[0].message.content

# # ROUTE DEFINITIONS - SPECIFIC ROUTES FIRST, PARAMETERIZED ROUTES LAST

# @router.get("/profile")
# async def get_user_profile(current_user: str = Depends(get_current_user)):
#     """Get the current user's profile - allows partial profiles"""
#     try:
#         print(f"🔍 Getting profile for user: {current_user}")
#         profile = load_user_profile(current_user)
        
#         # Handle contaminated profile (only for serious issues)
#         if isinstance(profile, dict) and profile.get("error") == "contaminated_profile":
#             validation_info = profile.get("validation", {})
            
#             # Check if it's a serious contamination or just partial data
#             if validation_info.get("reason") == "foreign_user_data_detected":
#                 raise HTTPException(
#                     status_code=422,
#                     detail={
#                         "error": "contaminated_profile",
#                         "message": "Profile contains data from other users",
#                         "user_id": current_user,
#                         "validation": validation_info,
#                         "recommended_action": "clear_contaminated_profile_and_restart_interview"
#                     }
#                 )
#             elif validation_info.get("reason") == "extensive_data_without_any_sessions":
#                 raise HTTPException(
#                     status_code=422,
#                     detail={
#                         "error": "suspicious_profile",
#                         "message": "Profile has extensive data but no interview sessions",
#                         "user_id": current_user,
#                         "validation": validation_info,
#                         "recommended_action": "start_interview_to_validate_or_clear_profile"
#                     }
#                 )
#             # For other validation issues, allow profile but with warnings
        
#         if not profile:
#             # Check interview status
#             db = get_firestore_client()
#             sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#             sessions = list(sessions_ref.stream())
            
#             if not sessions:
#                 raise HTTPException(
#                     status_code=404,
#                     detail="No profile found. Please start an interview to begin creating your profile."
#                 )
            
#             # If there are sessions but no profile, suggest continuing
#             in_progress_sessions = [s for s in sessions if s.to_dict().get("status") == "in_progress"]
#             if in_progress_sessions:
#                 raise HTTPException(
#                     status_code=404,
#                     detail={
#                         "message": "Interview in progress but no profile generated yet. Continue the interview to build your profile.",
#                         "sessions": [{"session_id": s.id, "phase": s.to_dict().get("current_phase")} for s in in_progress_sessions]
#                     }
#                 )
        
#         # Return profile (even if partial)
#         clean_profile = {k: v for k, v in profile.items() if not k.startswith('_')}
#         validation_summary = profile.get("_validation", {})
        
#         response = {
#             "success": True,
#             "profile": clean_profile,
#             "user_id": current_user,
#             "profile_type": "user_specific",
#             "profile_found": True,
#             "profile_completeness": validation_summary.get("profile_completeness", "unknown"),
#             "validation_summary": {
#                 "valid": validation_summary.get("valid", True),
#                 "authenticity_score": validation_summary.get("authenticity_score", 1.0),
#                 "reason": validation_summary.get("reason"),
#                 "has_interview_activity": validation_summary.get("has_any_session", False),
#                 "questions_answered": validation_summary.get("total_questions_answered", 0),
#                 "total_responses": validation_summary.get("total_detailed_responses", 0),
#                 "authenticated_responses": validation_summary.get("total_authenticated_responses", 0),
#                 "completed_phases": validation_summary.get("completed_phases", []),
#                 "in_progress_phases": validation_summary.get("in_progress_phases", [])
#             },
#             "profile_source": profile.get("_source", "unknown")
#         }
        
#         # Add guidance based on completeness
#         if validation_summary.get("profile_completeness") == "partial_in_progress":
#             response["message"] = "Profile is being built as you answer interview questions. Continue the interview for more personalized recommendations."
#         elif validation_summary.get("profile_completeness") == "partial_data_exists":
#             response["message"] = "Profile has some data. Start or continue an interview to enhance personalization."
#         elif validation_summary.get("profile_completeness


# app/routers/recommendations.py - Complete Enhanced with Category Management

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
from openai import OpenAI
from duckduckgo_search import DDGS 
from duckduckgo_search.exceptions import DuckDuckGoSearchException
from itertools import islice
import time
import uuid
from datetime import datetime, timedelta

from app.core.security import get_current_user
from app.core.firebase import get_firestore_client
from app.core.config import get_settings
from app.routers.conversations import save_conversation_message

router = APIRouter()

# Enhanced Pydantic models
class RecommendationRequest(BaseModel):
    query: str
    category: Optional[str] = None
    user_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class RecommendationItem(BaseModel):
    title: str
    description: Optional[str] = None
    reasons: List[str] = []
    category: Optional[str] = None
    confidence_score: Optional[float] = None
    external_links: Optional[List[str]] = None

class RecommendationResponse(BaseModel):
    recommendation_id: str
    recommendations: List[RecommendationItem]
    query: str
    category: Optional[str] = None
    user_id: str
    generated_at: datetime
    processing_time_ms: Optional[int] = None

class RecommendationFeedback(BaseModel):
    recommendation_id: str
    feedback_type: str  # 'like', 'dislike', 'not_relevant', 'helpful'
    rating: Optional[int] = None  # 1-5 stars
    comment: Optional[str] = None
    clicked_items: List[str] = []

# Database helper functions
def save_recommendation_to_db(recommendation_data: Dict[str, Any], db) -> str:
    """Save recommendation to database and return recommendation_id"""
    try:
        recommendation_id = str(uuid.uuid4())
        
        # Prepare data for database
        db_data = {
            "recommendation_id": recommendation_id,
            "user_id": recommendation_data["user_id"],
            "query": recommendation_data["query"],
            "category": recommendation_data.get("category"),
            "recommendations": recommendation_data["recommendations"],
            "generated_at": datetime.utcnow(),
            "processing_time_ms": recommendation_data.get("processing_time_ms"),
            "search_context": recommendation_data.get("search_context", []),
            "profile_version": recommendation_data.get("profile_version"),
            "profile_completeness": recommendation_data.get("profile_completeness"),
            "questions_answered": recommendation_data.get("questions_answered", 0),
            "session_id": recommendation_data.get("session_id"),
            "generation_method": recommendation_data.get("generation_method"),
            "is_active": True,
            "view_count": 0,
            "feedback_count": 0
        }
        
        # Save to user-specific collection
        db.collection("user_recommendations").document(recommendation_data["user_id"]).collection("recommendations").document(recommendation_id).set(db_data)
        
        # Also save to recommendation history for analytics
        history_data = {
            "recommendation_id": recommendation_id,
            "user_id": recommendation_data["user_id"],
            "query": recommendation_data["query"],
            "category": recommendation_data.get("category"),
            "recommendations_count": len(recommendation_data["recommendations"]),
            "profile_completeness": recommendation_data.get("profile_completeness"),
            "created_at": datetime.utcnow(),
            "is_bookmarked": False,
            "tags": []
        }
        
        db.collection("recommendation_history").document(recommendation_id).set(history_data)
        
        return recommendation_id
        
    except Exception as e:
        print(f"Error saving recommendation: {e}")
        return None

def save_recommendation_feedback(recommendation_id: str, user_id: str, feedback_data: Dict[str, Any], db):
    """Save user feedback for a recommendation"""
    try:
        feedback_id = str(uuid.uuid4())
        
        feedback_doc = {
            "feedback_id": feedback_id,
            "recommendation_id": recommendation_id,
            "user_id": user_id,
            "feedback_type": feedback_data["feedback_type"],
            "rating": feedback_data.get("rating"),
            "comment": feedback_data.get("comment"),
            "clicked_items": feedback_data.get("clicked_items", []),
            "created_at": datetime.utcnow()
        }
        
        # Save feedback
        db.collection("recommendation_feedback").document(feedback_id).set(feedback_doc)
        
        # Update recommendation with feedback count
        rec_ref = db.collection("user_recommendations").document(user_id).collection("recommendations").document(recommendation_id)
        rec_doc = rec_ref.get()
        
        if rec_doc.exists:
            current_feedback_count = rec_doc.to_dict().get("feedback_count", 0)
            rec_ref.update({"feedback_count": current_feedback_count + 1})
        
        return feedback_id
        
    except Exception as e:
        print(f"Error saving feedback: {e}")
        return None

# ENHANCED Category-Aware Profile validation and loading functions
def validate_profile_authenticity(profile_data: Dict[str, Any], user_id: str, db) -> Dict[str, Any]:
    """Enhanced validation that's category-aware and allows partial profiles"""
    
    if not profile_data or not user_id:
        return {"valid": False, "reason": "empty_profile_or_user"}
    
    validation_result = {
        "valid": True,
        "warnings": [],
        "user_id": user_id,
        "profile_sections": {},
        "authenticity_score": 1.0,
        "template_indicators": [],
        "profile_completeness": "partial",
        "category_completeness": {}  # NEW: Track completeness per category
    }
    
    try:
        # Check interview sessions for this user (grouped by category)
        interview_sessions = db.collection("interview_sessions").where("user_id", "==", user_id).stream()
        
        completed_phases_by_category = {}
        in_progress_phases_by_category = {}
        session_data = {}
        total_questions_answered = 0
        has_any_session = False
        
        for session in interview_sessions:
            has_any_session = True
            session_dict = session.to_dict()
            session_data[session.id] = session_dict
            
            category = session_dict.get("selected_category", "unknown")
            phase = session_dict.get("current_phase", "general")
            
            if category not in completed_phases_by_category:
                completed_phases_by_category[category] = set()
            if category not in in_progress_phases_by_category:
                in_progress_phases_by_category[category] = set()
            
            if session_dict.get("status") == "completed":
                completed_phases_by_category[category].add(phase)
                total_questions_answered += session_dict.get("questions_answered", 0)
            elif session_dict.get("status") == "in_progress":
                in_progress_phases_by_category[category].add(phase)
                total_questions_answered += session_dict.get("questions_answered", 0)
        
        # Convert sets to lists for JSON serialization
        completed_phases_by_category = {k: list(v) for k, v in completed_phases_by_category.items()}
        in_progress_phases_by_category = {k: list(v) for k, v in in_progress_phases_by_category.items()}
        
        validation_result["completed_phases_by_category"] = completed_phases_by_category
        validation_result["in_progress_phases_by_category"] = in_progress_phases_by_category
        validation_result["total_questions_answered"] = total_questions_answered
        validation_result["has_any_session"] = has_any_session
        validation_result["session_data"] = session_data
        
        # Analyze profile sections with category awareness
        profile_sections = profile_data.get("recommendationProfiles", {})
        general_profile = profile_data.get("generalprofile", {})
        
        total_detailed_responses = 0
        total_authenticated_responses = 0
        total_foreign_responses = 0
        template_indicators = []
        
        # Map profile section names to categories
        section_to_category = {
            "moviesandtv": "Movies",
            "movies": "Movies", 
            "travel": "Travel",
            "food": "Food",
            "foodanddining": "Food",
            "books": "Books",
            "music": "Music",
            "fitness": "Fitness"
        }
        
        # Check each recommendation profile section
        for section_name, section_data in profile_sections.items():
            section_lower = section_name.lower()
            mapped_category = section_to_category.get(section_lower, section_name)
            
            section_validation = {
                "has_data": bool(section_data),
                "mapped_category": mapped_category,
                "has_session_for_category": mapped_category in completed_phases_by_category or mapped_category in in_progress_phases_by_category,
                "interview_completed_for_category": mapped_category in completed_phases_by_category and len(completed_phases_by_category[mapped_category]) > 0,
                "interview_in_progress_for_category": mapped_category in in_progress_phases_by_category and len(in_progress_phases_by_category[mapped_category]) > 0,
                "data_authenticity": "unknown",
                "detailed_response_count": 0,
                "authenticated_response_count": 0,
                "foreign_response_count": 0
            }
            
            if section_data and isinstance(section_data, dict):
                def analyze_responses(data, path=""):
                    nonlocal total_detailed_responses, total_authenticated_responses, total_foreign_responses
                    
                    if isinstance(data, dict):
                        for key, value in data.items():
                            current_path = f"{path}.{key}" if path else key
                            
                            if isinstance(value, dict) and "value" in value:
                                response_value = value.get("value", "")
                                if isinstance(response_value, str) and len(response_value.strip()) > 10:
                                    section_validation["detailed_response_count"] += 1
                                    total_detailed_responses += 1
                                    
                                    # Check authentication markers
                                    if "user_id" in value and "updated_at" in value:
                                        if value.get("user_id") == user_id:
                                            section_validation["authenticated_response_count"] += 1
                                            total_authenticated_responses += 1
                                        else:
                                            section_validation["foreign_response_count"] += 1
                                            total_foreign_responses += 1
                                            template_indicators.append(
                                                f"Foreign user data: {section_name}.{current_path} (from {value.get('user_id')})"
                                            )
                                
                                # Recursively check nested structures
                                if isinstance(value, dict):
                                    analyze_responses(value, current_path)
                
                analyze_responses(section_data)
                
                # Enhanced authenticity determination with category awareness
                if section_validation["foreign_response_count"] > 0:
                    section_validation["data_authenticity"] = "foreign_user_data"
                elif section_validation["detailed_response_count"] > 0:
                    if section_validation["interview_completed_for_category"]:
                        section_validation["data_authenticity"] = "authentic"
                    elif section_validation["interview_in_progress_for_category"]:
                        section_validation["data_authenticity"] = "in_progress_authentic"
                    elif section_validation["authenticated_response_count"] > 0:
                        section_validation["data_authenticity"] = "authenticated_but_no_session"
                    else:
                        # Check if user has ANY interview activity
                        if has_any_session:
                            section_validation["data_authenticity"] = "possibly_legitimate"
                        else:
                            section_validation["data_authenticity"] = "suspicious_no_sessions"
                            template_indicators.append(
                                f"Detailed data without any interview sessions: {section_name}"
                            )
                else:
                    section_validation["data_authenticity"] = "minimal_data"
            
            validation_result["profile_sections"][section_name] = section_validation
            
            # Track category completeness
            if mapped_category not in validation_result["category_completeness"]:
                validation_result["category_completeness"][mapped_category] = {
                    "has_profile_data": section_validation["has_data"],
                    "has_interview_sessions": section_validation["has_session_for_category"],
                    "interview_completed": section_validation["interview_completed_for_category"],
                    "interview_in_progress": section_validation["interview_in_progress_for_category"],
                    "data_authenticity": section_validation["data_authenticity"],
                    "detailed_responses": section_validation["detailed_response_count"],
                    "authenticated_responses": section_validation["authenticated_response_count"]
                }
        
        # Check general profile
        general_detailed_responses = 0
        general_authenticated_responses = 0
        
        def check_general_profile(data, path="generalprofile"):
            nonlocal general_detailed_responses, general_authenticated_responses
            
            if isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}.{key}"
                    
                    if isinstance(value, dict):
                        if "value" in value and isinstance(value["value"], str) and len(value["value"].strip()) > 10:
                            general_detailed_responses += 1
                            if "user_id" in value and value.get("user_id") == user_id:
                                general_authenticated_responses += 1
                        else:
                            check_general_profile(value, current_path)
        
        check_general_profile(general_profile)
        
        # Calculate totals
        total_responses_with_general = total_detailed_responses + general_detailed_responses
        total_auth_with_general = total_authenticated_responses + general_authenticated_responses
        
        # Calculate authenticity score (more lenient)
        if total_responses_with_general > 0:
            auth_ratio = total_auth_with_general / total_responses_with_general
            session_factor = 1.0 if has_any_session else 0.3
            foreign_penalty = min(total_foreign_responses / max(total_responses_with_general, 1), 0.8)
            
            validation_result["authenticity_score"] = max(0.0, (auth_ratio * 0.6 + session_factor * 0.4) - foreign_penalty)
        else:
            validation_result["authenticity_score"] = 1.0
        
        # Determine overall profile completeness
        completed_categories = len([cat for cat in validation_result["category_completeness"].values() if cat["interview_completed"]])
        total_categories_with_data = len(validation_result["category_completeness"])
        
        if completed_categories > 0:
            if completed_categories == total_categories_with_data:
                validation_result["profile_completeness"] = "complete"
            else:
                validation_result["profile_completeness"] = "partially_complete"
        elif has_any_session and total_questions_answered > 0:
            validation_result["profile_completeness"] = "partial_in_progress"
        elif total_responses_with_general > 0:
            validation_result["profile_completeness"] = "partial_data_exists"
        else:
            validation_result["profile_completeness"] = "empty"
        
        validation_result["template_indicators"] = template_indicators
        validation_result["total_detailed_responses"] = total_responses_with_general
        validation_result["total_authenticated_responses"] = total_auth_with_general
        validation_result["total_foreign_responses"] = total_foreign_responses
        
        # MODIFIED validation logic - more permissive but category-aware
        if total_foreign_responses > 0:
            validation_result["valid"] = False
            validation_result["reason"] = "foreign_user_data_detected"
        elif total_responses_with_general > 10 and not has_any_session:
            validation_result["valid"] = False
            validation_result["reason"] = "extensive_data_without_any_sessions"
        elif validation_result["authenticity_score"] < 0.2:
            validation_result["valid"] = False
            validation_result["reason"] = "very_low_authenticity_score"
        
        # Add enhanced diagnostics
        validation_result["diagnostics"] = {
            "has_interview_activity": has_any_session,
            "questions_answered": total_questions_answered,
            "categories_with_data": total_categories_with_data,
            "completed_categories": completed_categories,
            "authentication_percentage": (total_auth_with_general / max(total_responses_with_general, 1)) * 100,
            "foreign_data_percentage": (total_foreign_responses / max(total_responses_with_general, 1)) * 100,
            "profile_usability": "usable" if validation_result["valid"] else "needs_cleanup"
        }
        
        return validation_result
        
    except Exception as e:
        return {
            "valid": False, 
            "reason": "validation_error", 
            "error": str(e)
        }

def load_user_profile(user_id: str = None) -> Dict[str, Any]:
    """Load and validate USER-SPECIFIC profile from Firestore - matches Streamlit pattern with category awareness"""
    try:
        db = get_firestore_client()
        
        if not user_id:
            print("❌ No user_id provided for profile loading")
            return {}
        
        print(f"🔍 Looking for profile for user: {user_id}")
        
        # Try to find profile in multiple locations (same as Streamlit logic)
        profile_locations = [
            {
                "collection": "user_profiles",
                "document": f"{user_id}_profile_structure.json",
                "description": "Primary user_profiles collection"
            },
            {
                "collection": "user_collection", 
                "document": f"{user_id}_profile_structure.json",
                "description": "Fallback user_collection with user prefix"
            },
            {
                "collection": "user_collection",
                "document": "profile_strcuture.json",  # Matches Streamlit typo
                "description": "Streamlit default profile location"
            },
            {
                "collection": "interview_profiles",
                "document": f"{user_id}_profile.json", 
                "description": "Interview-generated profile"
            },
            {
                "collection": f"user_{user_id}",
                "document": "profile_structure.json",
                "description": "User-specific collection"
            }
        ]
        
        raw_profile = None
        profile_source = None
        
        for location in profile_locations:
            try:
                doc_ref = db.collection(location["collection"]).document(location["document"])
                doc = doc_ref.get()
                
                if doc.exists:
                    raw_profile = doc.to_dict()
                    profile_source = f"{location['collection']}/{location['document']}"
                    print(f"✅ Found profile at: {profile_source}")
                    break
                    
            except Exception as e:
                print(f"❌ Error checking {location['description']}: {e}")
                continue
        
        if not raw_profile:
            print(f"❌ No profile found for user: {user_id}")
            return {}
        
        # Validate profile authenticity with enhanced category-aware validation
        validation = validate_profile_authenticity(raw_profile, user_id, db)
        
        print(f"🔍 Profile validation result: {validation.get('valid')} - {validation.get('reason', 'OK')}")
        print(f"🔍 Profile completeness: {validation.get('profile_completeness', 'unknown')}")
        print(f"🔍 Questions answered: {validation.get('total_questions_answered', 0)}")
        print(f"🔍 Authenticity score: {validation.get('authenticity_score', 0.0):.2f}")
        print(f"🔍 Category completeness: {list(validation.get('category_completeness', {}).keys())}")
        
        if validation.get("warnings"):
            print(f"⚠️ Profile warnings: {validation['warnings']}")
        
        # Only reject for serious contamination
        if not validation.get("valid"):
            serious_issues = ["foreign_user_data_detected", "extensive_data_without_any_sessions"]
            if validation.get("reason") in serious_issues:
                print(f"🚨 SERIOUS PROFILE ISSUE for user {user_id}: {validation.get('reason')}")
                return {
                    "error": "contaminated_profile",
                    "user_id": user_id,
                    "validation": validation,
                    "message": f"Profile validation failed: {validation.get('reason')}",
                    "profile_source": profile_source
                }
            else:
                print(f"⚠️ Minor profile issue for user {user_id}: {validation.get('reason')} - allowing with warnings")
        
        # Return profile with validation info (even if partial)
        profile_with_metadata = raw_profile.copy()
        profile_with_metadata["_validation"] = validation
        profile_with_metadata["_source"] = profile_source
        
        return profile_with_metadata
        
    except Exception as e:
        print(f"❌ Error loading user profile for {user_id}: {e}")
        return {}

def search_web(query, max_results=3, max_retries=3, base_delay=1.0):
    """Query DuckDuckGo via DDGS.text(), returning up to max_results items."""
    for attempt in range(1, max_retries + 1):
        try:
            with DDGS() as ddgs:
                return list(islice(ddgs.text(query), max_results))
        except DuckDuckGoSearchException as e:
            msg = str(e)
            if "202" in msg:
                wait = base_delay * (2 ** (attempt - 1))
                print(f"[search_web] Rate‑limited (202). Retry {attempt}/{max_retries} in {wait:.1f}s…")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            print(f"[search_web] Unexpected error: {e}")
            break
    
    print(f"[search_web] Failed to fetch results after {max_retries} attempts.")
    return []

def generate_recommendations(user_profile, user_query, openai_key, category=None):
    """Generate 3 personalized recommendations using user profile and web search - STREAMLIT COMPATIBLE"""
    
    # Enhanced search with category context
    if category:
        search_query = f"{category} {user_query} recommendations 2024"
    else:
        search_query = f"{user_query} recommendations 2024"
    
    search_results = search_web(search_query)
    
    # Category-specific instructions
    category_instructions = ""
    if category:
        category_lower = category.lower()
        
        if category_lower in ["travel", "travel & destinations"]:
            category_instructions = """
            **CATEGORY FOCUS: TRAVEL & DESTINATIONS**
            - Recommend specific destinations, attractions, or travel experiences
            - Include practical travel advice (best time to visit, transportation, accommodations)
            - Consider cultural experiences, local cuisine, historical sites, natural attractions
            - Focus on places to visit, things to do, travel itineraries
            - DO NOT recommend economic plans, political content, or business strategies
            
            **EXAMPLE for Pakistan Travel Query**:
            - "Hunza Valley, Pakistan" - Mountain valley with stunning landscapes
            - "Lahore Food Street" - Culinary travel experience in historic city
            - "Skardu Adventures" - Trekking and mountaineering destination
            """
            
        elif category_lower in ["movies", "movies & tv", "entertainment"]:
            category_instructions = """
            **CATEGORY FOCUS: MOVIES & TV**
            - Recommend specific movies, TV shows, or streaming content
            - Consider genres, directors, actors, themes that match user preferences
            - Include where to watch (streaming platforms) if possible
            - Focus on entertainment content, not travel or other categories
            """
            
        elif category_lower in ["food", "food & dining", "restaurants"]:
            category_instructions = """
            **CATEGORY FOCUS: FOOD & DINING**
            - Recommend specific restaurants, cuisines, or food experiences
            - Include local specialties, popular dishes, dining venues
            - Consider user's location and dietary preferences
            - Focus on food and dining experiences, not travel destinations
            """
            
        else:
            category_instructions = f"""
            **CATEGORY FOCUS: {category.upper()}**
            - Focus recommendations specifically on {category} related content
            - Ensure all suggestions are relevant to the {category} category
            - Do not recommend content from other categories
            """
    
    prompt = f"""
    **Task**: Generate exactly 3 highly personalized {category + ' ' if category else ''}recommendations based on:
    
    {category_instructions}
    
    **User Profile**:
    {json.dumps(user_profile, indent=2)}
    
    **User Query**:
    "{user_query}"
    
    **Web Context** (for reference only):
    {search_results}
    
    **Requirements**:
    1. Each recommendation must directly reference profile details when available
    2. ALL recommendations MUST be relevant to the "{category}" category if specified
    3. Blend the user's core values and preferences from their profile
    4. Only suggest what is asked for - no extra advice
    5. For travel queries, recommend specific destinations, attractions, or experiences
    6. Format as JSON array with each recommendation having:
       - title: string (specific name of place/item/experience)
       - description: string (brief description of what it is)
       - reasons: array of strings (why it matches the user profile)
       - confidence_score: float (0.0-1.0)
    
    **CRITICAL for Travel Category**: 
    If this is a travel recommendation, suggest actual destinations, attractions, restaurants, or travel experiences.
    DO NOT suggest economic plans, political content, or business strategies.
    
    **Output Example for Travel**:
    [
      {{
         "title": "Hunza Valley, Pakistan",
         "description": "Breathtaking mountain valley known for stunning landscapes and rich cultural heritage",
         "reasons": ["Matches your love for natural beauty and cultural exploration", "Perfect for peaceful mountain retreats you prefer"],
         "confidence_score": 0.9
      }},
      {{
         "title": "Lahore Food Street, Pakistan", 
         "description": "Historic food destination offering authentic Pakistani cuisine and cultural immersion",
         "reasons": ["Aligns with your interest in trying traditional foods", "Offers the cultural experiences you enjoy"],
         "confidence_score": 0.85
      }},
      {{
         "title": "Skardu, Pakistan",
         "description": "Adventure destination for trekking and mountaineering with stunning natural scenery",
         "reasons": ["Perfect for your moderate adventure seeking preferences", "Offers the peaceful outdoor experiences you value"],
         "confidence_score": 0.8
      }}
    ]
    
    Generate your response in JSON format only.
    """
    
    # Setting up LLM - same as Streamlit pattern
    client = OpenAI(api_key=openai_key)

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": f"You're a recommendation engine that creates hyper-personalized {category.lower() if category else ''} suggestions. You MUST focus on {category.lower() if category else 'relevant'} content only. Output valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7  
    )
    
    return response.choices[0].message.content

# ROUTE DEFINITIONS - SPECIFIC ROUTES FIRST, PARAMETERIZED ROUTES LAST

@router.get("/profile")
async def get_user_profile(current_user: str = Depends(get_current_user)):
    """Get the current user's profile with category-specific completeness info"""
    try:
        print(f"🔍 Getting profile for user: {current_user}")
        profile = load_user_profile(current_user)
        
        # Handle contaminated profile (only for serious issues)
        if isinstance(profile, dict) and profile.get("error") == "contaminated_profile":
            validation_info = profile.get("validation", {})
            
            if validation_info.get("reason") == "foreign_user_data_detected":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "contaminated_profile",
                        "message": "Profile contains data from other users",
                        "user_id": current_user,
                        "validation": validation_info,
                        "recommended_action": "clear_contaminated_profile_and_restart_interview"
                    }
                )
            elif validation_info.get("reason") == "extensive_data_without_any_sessions":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "suspicious_profile",
                        "message": "Profile has extensive data but no interview sessions",
                        "user_id": current_user,
                        "validation": validation_info,
                        "recommended_action": "start_interview_to_validate_or_clear_profile"
                    }
                )
        
        if not profile:
            # Check interview status
            db = get_firestore_client()
            sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
            sessions = list(sessions_ref.stream())
            
            if not sessions:
                raise HTTPException(
                    status_code=404,
                    detail="No profile found. Please start an interview to begin creating your profile."
                )
            
            # If there are sessions but no profile, suggest continuing
            in_progress_sessions = [s for s in sessions if s.to_dict().get("status") == "in_progress"]
            if in_progress_sessions:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "message": "Interview in progress but no profile generated yet. Continue the interview to build your profile.",
                        "sessions": [{"session_id": s.id, "phase": s.to_dict().get("current_phase"), "category": s.to_dict().get("selected_category")} for s in in_progress_sessions]
                    }
                )
        
        # Return profile with enhanced category information
        clean_profile = {k: v for k, v in profile.items() if not k.startswith('_')}
        validation_summary = profile.get("_validation", {})
        
        response = {
            "success": True,
            "profile": clean_profile,
            "user_id": current_user,
            "profile_type": "user_specific",
            "profile_found": True,
            "profile_completeness": validation_summary.get("profile_completeness", "unknown"),
            "category_completeness": validation_summary.get("category_completeness", {}),
            "validation_summary": {
                "valid": validation_summary.get("valid", True),
                "authenticity_score": validation_summary.get("authenticity_score", 1.0),
                "reason": validation_summary.get("reason"),
                "has_interview_activity": validation_summary.get("has_any_session", False),
                "questions_answered": validation_summary.get("total_questions_answered", 0),
                "total_responses": validation_summary.get("total_detailed_responses", 0),
                "authenticated_responses": validation_summary.get("total_authenticated_responses", 0),
                "completed_phases_by_category": validation_summary.get("completed_phases_by_category", {}),
                "in_progress_phases_by_category": validation_summary.get("in_progress_phases_by_category", {})
            },
            "profile_source": profile.get("_source", "unknown")
        }
        
        # Add enhanced guidance based on category completeness
        category_completeness = validation_summary.get("category_completeness", {})
        completed_categories = [cat for cat, data in category_completeness.items() if data.get("interview_completed")]
        in_progress_categories = [cat for cat, data in category_completeness.items() if data.get("interview_in_progress")]
        available_categories = ["Movies", "Food", "Travel", "Books", "Music", "Fitness"]
        not_started_categories = [cat for cat in available_categories if cat not in category_completeness]
        
        if len(completed_categories) == len(category_completeness) and len(completed_categories) > 0:
            response["message"] = f"Profile complete for {len(completed_categories)} categories: {', '.join(completed_categories)}. You can start interviews for other categories or update existing ones."
        elif len(completed_categories) > 0:
            response["message"] = f"Profile complete for: {', '.join(completed_categories)}. Continue in-progress categories or start new ones."
        elif len(in_progress_categories) > 0:
            response["message"] = f"Interviews in progress for: {', '.join(in_progress_categories)}. Continue these or start new category interviews."
        else:
            response["message"] = "Start category interviews to build your personalized profile."
        
        # Add actionable suggestions
        response["suggestions"] = {
            "completed_categories": completed_categories,
            "in_progress_categories": in_progress_categories,
            "available_to_start": not_started_categories,
            "can_update": completed_categories,
            "should_continue": in_progress_categories
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in get_user_profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load profile: {str(e)}"
        )

@router.get("/profile/category/{category}")
async def get_category_profile_status(
    category: str,
    current_user: str = Depends(get_current_user)
):
    """Get profile status for a specific category"""
    try:
        profile = load_user_profile(current_user)
        
        if not profile:
            return {
                "success": False,
                "user_id": current_user,
                "category": category,
                "has_data": False,
                "message": f"No profile found. Start a {category} interview to begin."
            }
        
        validation_summary = profile.get("_validation", {})
        category_completeness = validation_summary.get("category_completeness", {})
        
        if category in category_completeness:
            category_data = category_completeness[category]
            return {
                "success": True,
                "user_id": current_user,
                "category": category,
                "has_data": category_data.get("has_profile_data", False),
                "interview_completed": category_data.get("interview_completed", False),
                "interview_in_progress": category_data.get("interview_in_progress", False),
                "data_authenticity": category_data.get("data_authenticity", "unknown"),
                "detailed_responses": category_data.get("detailed_responses", 0),
                "authenticated_responses": category_data.get("authenticated_responses", 0),
                "status": "completed" if category_data.get("interview_completed") else "in_progress" if category_data.get("interview_in_progress") else "has_data",
                "message": f"{category} profile status: {category_data.get('data_authenticity', 'unknown')}"
            }
        else:
            return {
                "success": True,
                "user_id": current_user,
                "category": category,
                "has_data": False,
                "interview_completed": False,
                "interview_in_progress": False,
                "status": "not_started",
                "message": f"No {category} profile data found. Start a {category} interview to begin building this section."
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get category profile status: {str(e)}"
        )

@router.post("/restart/{category}")
async def restart_category_interview(
    category: str,
    current_user: str = Depends(get_current_user)
):
    """Restart interview for a specific category"""
    try:
        db = get_firestore_client()
        
        # Find existing sessions for this category
        sessions_query = db.collection("interview_sessions")\
            .where("user_id", "==", current_user)\
            .where("selected_category", "==", category)
        
        existing_sessions = list(sessions_query.stream())
        
        # Archive all existing sessions for this category
        for session in existing_sessions:
            session.reference.update({
                "status": "archived",
                "archived_at": datetime.utcnow(),
                "archived_reason": "category_restart"
            })
        
        # Create new session
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "user_id": current_user,
            "selected_category": category,
            "status": "in_progress",
            "current_tier": 1,
            "current_phase": "general",
            "questions_answered": 0,
            "total_tiers": 3,
            "is_complete": False,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "user_specific": True,
            "restart_count": len(existing_sessions)
        }
        
        # Save new session
        db.collection("interview_sessions").document(session_id).set(session_data)
        
        return {
            "success": True,
            "message": f"Restarted {category} interview",
            "session_id": session_id,
            "user_id": current_user,
            "category": category,
            "archived_sessions": len(existing_sessions),
            "status": "in_progress"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restart {category} interview: {str(e)}"
        )

@router.get("/categories")
async def get_recommendation_categories():
    """Get available recommendation categories"""
    categories = [
        {
            "id": "movies",
            "name": "Movies & TV",
            "description": "Movie and TV show recommendations",
            "questions_file": "moviesAndTV_tiered_questions.json"
        },
        {
            "id": "food",
            "name": "Food & Dining",
            "description": "Restaurant and food recommendations",
            "questions_file": "foodAndDining_tiered_questions.json"
        },
        {
            "id": "travel",
            "name": "Travel",
            "description": "Travel destination recommendations",
            "questions_file": "travel_tiered_questions.json"
        },
        {
            "id": "books",
            "name": "Books & Reading",
            "description": "Book recommendations",
            "questions_file": "books_tiered_questions.json"
        },
        {
            "id": "music",
            "name": "Music",
            "description": "Music and artist recommendations",
            "questions_file": "music_tiered_questions.json"
        },
        {
            "id": "fitness",
            "name": "Fitness & Wellness",
            "description": "Fitness and wellness recommendations",
            "questions_file": "fitness_tiered_questions.json"
        }
    ]
    
    return {
        "categories": categories,
        "default_category": "movies"
    }

@router.post("/generate", response_model=RecommendationResponse)
async def generate_user_recommendations(
    request: RecommendationRequest,
    current_user: str = Depends(get_current_user)
):
    """Generate recommendations using the same logic as Streamlit but enhanced for FastAPI"""
    try:
        start_time = datetime.utcnow()
        settings = get_settings()
        db = get_firestore_client()
        
        print(f"🚀 Generating recommendations for user: {current_user}")
        print(f"📝 Query: {request.query}")
        print(f"🏷️ Category: {request.category}")
        
        # Load profile (same as Streamlit)
        user_profile = load_user_profile(current_user)
        
        # Handle serious contamination only
        if isinstance(user_profile, dict) and user_profile.get("error") == "contaminated_profile":
            validation = user_profile.get("validation", {})
            if validation.get("reason") in ["foreign_user_data_detected", "extensive_data_without_any_sessions"]:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "contaminated_profile",
                        "message": "Cannot generate recommendations with contaminated profile data",
                        "recommended_action": "clear_profile_and_start_interview"
                    }
                )
        
        # If no profile, check if we should allow basic recommendations (same as Streamlit)
        if not user_profile:
            print("⚠️ No profile found - checking interview status")
            
            # Check if user has any interview activity
            sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
            sessions = list(sessions_ref.stream())
            
            if not sessions:
                # No interview started - create minimal profile for basic recommendations
                print("📝 No interview sessions - creating basic profile for general recommendations")
                user_profile = {
                    "user_id": current_user,
                    "generalprofile": {
                        "corePreferences": {
                            "note": f"Basic profile - complete interview for personalized {request.category or 'recommendations'}"
                        }
                    },
                    "profile_completeness": "empty"
                }
            else:
                # Has interview activity but no profile - this shouldn't happen
                raise HTTPException(
                    status_code=404,
                    detail="Interview sessions found but no profile generated. Please contact support."
                )
        
        # Clean profile for AI processing (remove metadata)
        clean_profile = {k: v for k, v in user_profile.items() if not k.startswith('_')}
        
        # Get profile completeness info
        validation_summary = user_profile.get("_validation", {})
        profile_completeness = validation_summary.get("profile_completeness", "unknown")
        questions_answered = validation_summary.get("total_questions_answered", 0)
        category_completeness = validation_summary.get("category_completeness", {})
        
        print(f"📊 Profile completeness: {profile_completeness}")
        print(f"📝 Questions answered: {questions_answered}")
        print(f"🏷️ Category completeness: {list(category_completeness.keys())}")
        
        # Check if the requested category has data
        category_has_data = False
        category_status = "not_started"
        if request.category and request.category in category_completeness:
            category_data = category_completeness[request.category]
            category_has_data = category_data.get("has_profile_data", False)
            if category_data.get("interview_completed"):
                category_status = "completed"
            elif category_data.get("interview_in_progress"):
                category_status = "in_progress"
            else:
                category_status = "has_data"
        
        print(f"🎯 Category {request.category} status: {category_status}, has_data: {category_has_data}")
        
        # Generate category-aware recommendations
        recs_json = generate_recommendations(
            clean_profile, 
            request.query, 
            settings.OPENAI_API_KEY,
            request.category  # Add category parameter
        )
        
        try:
            recs = json.loads(recs_json)
            
            # Normalize to list (same as Streamlit)
            if isinstance(recs, dict):
                if "recommendations" in recs and isinstance(recs["recommendations"], list):
                    recs = recs["recommendations"]
                else:
                    recs = [recs]
            
            if not isinstance(recs, list):
                raise HTTPException(
                    status_code=500,
                    detail="Unexpected response format – expected a list of recommendations."
                )
            
            # Validate category relevance for travel
            if request.category and request.category.lower() == "travel":
                travel_keywords = ["destination", "place", "visit", "travel", "city", "country", "attraction", "trip", "valley", "mountain", "beach", "street", "food", "culture", "heritage", "adventure", "pakistan", "hunza", "lahore", "skardu"]
                
                for i, rec in enumerate(recs):
                    title_and_desc = (rec.get('title', '') + ' ' + rec.get('description', '')).lower()
                    if not any(keyword in title_and_desc for keyword in travel_keywords):
                        print(f"⚠️ Recommendation {i+1} '{rec.get('title')}' may not be travel-related")
                        print(f"🔍 Content: {title_and_desc[:100]}...")
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Add profile completion guidance based on category status
            for rec in recs:
                if "reasons" not in rec:
                    rec["reasons"] = []
                
                if request.category and category_status == "not_started":
                    rec["reasons"].append(f"Start a {request.category} interview for more personalized recommendations")
                elif request.category and category_status == "in_progress":
                    rec["reasons"].append(f"Continue your {request.category} interview for better personalization")
                elif profile_completeness == "empty":
                    rec["reasons"].append("Start an interview to get more personalized recommendations")
                elif profile_completeness in ["partial_in_progress", "partial_data_exists"]:
                    rec["reasons"].append("Complete more interview questions for better personalization")
            
            # Generate session ID for conversation tracking
            session_id = str(uuid.uuid4())
            
            # Save conversation messages (like Streamlit chat)
            save_conversation_message(
                current_user, 
                session_id, 
                "user", 
                f"What would you like {request.category.lower() if request.category else ''} recommendations for? {request.query}", 
                "recommendation",
                f"{request.category or 'General'} Recommendation Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
            # Prepare recommendation data for database
            recommendation_data = {
                "user_id": current_user,
                "query": request.query,
                "category": request.category,
                "recommendations": recs,
                "processing_time_ms": int(processing_time),
                "search_context": search_web(f"{request.category} {request.query} recommendations 2024" if request.category else f"{request.query} recommendations 2024"),
                "session_id": session_id,
                "profile_version": clean_profile.get("version", "1.0"),
                "profile_completeness": profile_completeness,
                "category_status": category_status,
                "category_has_data": category_has_data,
                "questions_answered": questions_answered,
                "user_specific": True,
                "generation_method": "streamlit_compatible"
            }
            
            # Save to database
            recommendation_id = save_recommendation_to_db(recommendation_data, db)
            
            if not recommendation_id:
                print("⚠️ Warning: Failed to save recommendation to database")
                recommendation_id = str(uuid.uuid4())  # Fallback
            
            # Format recommendations for conversation history (like Streamlit display)
            recs_text = f"Here are your {request.category.lower() if request.category else ''} recommendations:\n\n"
            
            for i, rec in enumerate(recs, 1):
                title = rec.get("title", "<no title>")
                description = rec.get("description", rec.get("reason", "<no description>"))
                reasons = rec.get("reasons", [])
                
                recs_text += f"**{i}. {title}**\n"
                recs_text += f"{description}\n"
                if reasons:
                    for reason in reasons:
                        recs_text += f"• {reason}\n"
                recs_text += "\n"
            
            # Save recommendations to conversation history
            save_conversation_message(
                current_user, 
                session_id, 
                "assistant", 
                recs_text, 
                "recommendation"
            )
            
            # Convert to RecommendationItem objects
            recommendation_items = []
            for rec in recs:
                # Use confidence score from AI or default based on profile completeness
                base_confidence = 0.6 if profile_completeness == "empty" or category_status == "not_started" else 0.8
                confidence_score = rec.get('confidence_score', base_confidence)
                
                recommendation_items.append(RecommendationItem(
                    title=rec.get('title', 'Recommendation'),
                    description=rec.get('description', rec.get('reason', '')),
                    reasons=rec.get('reasons', []),
                    category=request.category,
                    confidence_score=confidence_score
                ))
            
            return RecommendationResponse(
                recommendation_id=recommendation_id,
                recommendations=recommendation_items,
                query=request.query,
                category=request.category,
                user_id=current_user,
                generated_at=datetime.utcnow(),
                processing_time_ms=int(processing_time)
            )
            
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse recommendations: {str(e)}"
            print(f"❌ JSON parsing error: {error_msg}")
            print(f"🔍 Raw AI response: {recs_json[:500]}...")
            
            # Save error to conversation history
            save_conversation_message(
                current_user, 
                str(uuid.uuid4()), 
                "assistant", 
                f"Sorry, I encountered an error generating {request.category or ''} recommendations: {error_msg}", 
                "recommendation"
            )
            
            raise HTTPException(
                status_code=500,
                detail=error_msg
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error generating recommendations for user {current_user}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate {request.category or ''} recommendations: {str(e)}"
        )

@router.get("/history")
async def get_recommendation_history(
    current_user: str = Depends(get_current_user),
    limit: int = Query(20, description="Number of recommendations to return"),
    offset: int = Query(0, description="Number of recommendations to skip"),
    category: Optional[str] = Query(None, description="Filter by category")
):
    """Get recommendation history for the user with enhanced filtering"""
    try:
        db = get_firestore_client()
        
        # Simplified query to avoid index issues
        query = db.collection("user_recommendations").document(current_user).collection("recommendations")
        query = query.where("is_active", "==", True)
        query = query.limit(limit).offset(offset)
        
        recommendations = list(query.stream())
        
        # Filter and sort in Python
        filtered_recs = []
        for rec in recommendations:
            rec_data = rec.to_dict()
            
            # Apply category filter
            if category and rec_data.get("category") != category:
                continue
            
            filtered_recs.append(rec_data)
        
        # Sort by generated_at descending
        filtered_recs.sort(key=lambda x: x.get("generated_at", datetime.min), reverse=True)
        
        # Format response
        history = []
        for rec_data in filtered_recs:
            history.append({
                "recommendation_id": rec_data["recommendation_id"],
                "query": rec_data["query"],
                "category": rec_data.get("category"),
                "recommendations_count": len(rec_data.get("recommendations", [])),
                "generated_at": rec_data["generated_at"],
                "view_count": rec_data.get("view_count", 0),
                "feedback_count": rec_data.get("feedback_count", 0),
                "session_id": rec_data.get("session_id"),
                "processing_time_ms": rec_data.get("processing_time_ms"),
                "profile_completeness": rec_data.get("profile_completeness", "unknown"),
                "category_status": rec_data.get("category_status", "unknown"),
                "generation_method": rec_data.get("generation_method", "unknown")
            })
        
        return {
            "success": True,
            "history": history,
            "total_count": len(history),
            "user_id": current_user,
            "filters": {
                "category": category,
                "limit": limit,
                "offset": offset
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recommendation history: {str(e)}"
        )

@router.post("/{recommendation_id}/feedback")
async def submit_recommendation_feedback(
    recommendation_id: str,
    feedback: RecommendationFeedback,
    current_user: str = Depends(get_current_user)
):
    """Submit feedback for a recommendation"""
    try:
        db = get_firestore_client()
        
        # Verify recommendation exists and belongs to user
        rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
        if not rec_doc.exists:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        # Save feedback
        feedback_data = {
            "feedback_type": feedback.feedback_type,
            "rating": feedback.rating,
            "comment": feedback.comment,
            "clicked_items": feedback.clicked_items
        }
        
        feedback_id = save_recommendation_feedback(recommendation_id, current_user, feedback_data, db)
        
        if not feedback_id:
            raise HTTPException(status_code=500, detail="Failed to save feedback")
        
        return {
            "success": True,
            "message": "Feedback submitted successfully",
            "feedback_id": feedback_id,
            "recommendation_id": recommendation_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit feedback: {str(e)}"
        )

# IMPORTANT: Put parameterized routes LAST to avoid route conflicts
@router.get("/{recommendation_id}")
async def get_recommendation_details(
    recommendation_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get detailed information about a specific recommendation"""
    try:
        db = get_firestore_client()
        
        # Get recommendation details
        rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
        if not rec_doc.exists:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        rec_data = rec_doc.to_dict()
        
        # Increment view count
        current_views = rec_data.get("view_count", 0)
        rec_doc.reference.update({
            "view_count": current_views + 1,
            "last_viewed": datetime.utcnow()
        })
        
        return {
            "success": True,
            "recommendation": {
                "recommendation_id": rec_data["recommendation_id"],
                "query": rec_data["query"],
                "category": rec_data.get("category"),
                "recommendations": rec_data["recommendations"],
                "generated_at": rec_data["generated_at"],
                "processing_time_ms": rec_data.get("processing_time_ms"),
                "view_count": current_views + 1,
                "search_context": rec_data.get("search_context", []),
                "profile_completeness": rec_data.get("profile_completeness", "unknown"),
                "category_status": rec_data.get("category_status", "unknown"),
                "questions_answered": rec_data.get("questions_answered", 0),
                "generation_method": rec_data.get("generation_method", "unknown")
            },
            "user_id": current_user
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recommendation details: {str(e)}"
        )# app/routers/recommendations.py - Complete Enhanced with Category Management

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
from openai import OpenAI
from duckduckgo_search import DDGS 
from duckduckgo_search.exceptions import DuckDuckGoSearchException
from itertools import islice
import time
import uuid
from datetime import datetime, timedelta

from app.core.security import get_current_user
from app.core.firebase import get_firestore_client
from app.core.config import get_settings
from app.routers.conversations import save_conversation_message

router = APIRouter()

# Enhanced Pydantic models
class RecommendationRequest(BaseModel):
    query: str
    category: Optional[str] = None
    user_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class RecommendationItem(BaseModel):
    title: str
    description: Optional[str] = None
    reasons: List[str] = []
    category: Optional[str] = None
    confidence_score: Optional[float] = None
    external_links: Optional[List[str]] = None

class RecommendationResponse(BaseModel):
    recommendation_id: str
    recommendations: List[RecommendationItem]
    query: str
    category: Optional[str] = None
    user_id: str
    generated_at: datetime
    processing_time_ms: Optional[int] = None

class RecommendationFeedback(BaseModel):
    recommendation_id: str
    feedback_type: str  # 'like', 'dislike', 'not_relevant', 'helpful'
    rating: Optional[int] = None  # 1-5 stars
    comment: Optional[str] = None
    clicked_items: List[str] = []

# Database helper functions
def save_recommendation_to_db(recommendation_data: Dict[str, Any], db) -> str:
    """Save recommendation to database and return recommendation_id"""
    try:
        recommendation_id = str(uuid.uuid4())
        
        # Prepare data for database
        db_data = {
            "recommendation_id": recommendation_id,
            "user_id": recommendation_data["user_id"],
            "query": recommendation_data["query"],
            "category": recommendation_data.get("category"),
            "recommendations": recommendation_data["recommendations"],
            "generated_at": datetime.utcnow(),
            "processing_time_ms": recommendation_data.get("processing_time_ms"),
            "search_context": recommendation_data.get("search_context", []),
            "profile_version": recommendation_data.get("profile_version"),
            "profile_completeness": recommendation_data.get("profile_completeness"),
            "questions_answered": recommendation_data.get("questions_answered", 0),
            "session_id": recommendation_data.get("session_id"),
            "generation_method": recommendation_data.get("generation_method"),
            "is_active": True,
            "view_count": 0,
            "feedback_count": 0
        }
        
        # Save to user-specific collection
        db.collection("user_recommendations").document(recommendation_data["user_id"]).collection("recommendations").document(recommendation_id).set(db_data)
        
        # Also save to recommendation history for analytics
        history_data = {
            "recommendation_id": recommendation_id,
            "user_id": recommendation_data["user_id"],
            "query": recommendation_data["query"],
            "category": recommendation_data.get("category"),
            "recommendations_count": len(recommendation_data["recommendations"]),
            "profile_completeness": recommendation_data.get("profile_completeness"),
            "created_at": datetime.utcnow(),
            "is_bookmarked": False,
            "tags": []
        }
        
        db.collection("recommendation_history").document(recommendation_id).set(history_data)
        
        return recommendation_id
        
    except Exception as e:
        print(f"Error saving recommendation: {e}")
        return None

def save_recommendation_feedback(recommendation_id: str, user_id: str, feedback_data: Dict[str, Any], db):
    """Save user feedback for a recommendation"""
    try:
        feedback_id = str(uuid.uuid4())
        
        feedback_doc = {
            "feedback_id": feedback_id,
            "recommendation_id": recommendation_id,
            "user_id": user_id,
            "feedback_type": feedback_data["feedback_type"],
            "rating": feedback_data.get("rating"),
            "comment": feedback_data.get("comment"),
            "clicked_items": feedback_data.get("clicked_items", []),
            "created_at": datetime.utcnow()
        }
        
        # Save feedback
        db.collection("recommendation_feedback").document(feedback_id).set(feedback_doc)
        
        # Update recommendation with feedback count
        rec_ref = db.collection("user_recommendations").document(user_id).collection("recommendations").document(recommendation_id)
        rec_doc = rec_ref.get()
        
        if rec_doc.exists:
            current_feedback_count = rec_doc.to_dict().get("feedback_count", 0)
            rec_ref.update({"feedback_count": current_feedback_count + 1})
        
        return feedback_id
        
    except Exception as e:
        print(f"Error saving feedback: {e}")
        return None

# ENHANCED Category-Aware Profile validation and loading functions
def validate_profile_authenticity(profile_data: Dict[str, Any], user_id: str, db) -> Dict[str, Any]:
    """Enhanced validation that's category-aware and allows partial profiles"""
    
    if not profile_data or not user_id:
        return {"valid": False, "reason": "empty_profile_or_user"}
    
    validation_result = {
        "valid": True,
        "warnings": [],
        "user_id": user_id,
        "profile_sections": {},
        "authenticity_score": 1.0,
        "template_indicators": [],
        "profile_completeness": "partial",
        "category_completeness": {}  # NEW: Track completeness per category
    }
    
    try:
        # Check interview sessions for this user (grouped by category)
        interview_sessions = db.collection("interview_sessions").where("user_id", "==", user_id).stream()
        
        completed_phases_by_category = {}
        in_progress_phases_by_category = {}
        session_data = {}
        total_questions_answered = 0
        has_any_session = False
        
        for session in interview_sessions:
            has_any_session = True
            session_dict = session.to_dict()
            session_data[session.id] = session_dict
            
            category = session_dict.get("selected_category", "unknown")
            phase = session_dict.get("current_phase", "general")
            
            if category not in completed_phases_by_category:
                completed_phases_by_category[category] = set()
            if category not in in_progress_phases_by_category:
                in_progress_phases_by_category[category] = set()
            
            if session_dict.get("status") == "completed":
                completed_phases_by_category[category].add(phase)
                total_questions_answered += session_dict.get("questions_answered", 0)
            elif session_dict.get("status") == "in_progress":
                in_progress_phases_by_category[category].add(phase)
                total_questions_answered += session_dict.get("questions_answered", 0)
        
        # Convert sets to lists for JSON serialization
        completed_phases_by_category = {k: list(v) for k, v in completed_phases_by_category.items()}
        in_progress_phases_by_category = {k: list(v) for k, v in in_progress_phases_by_category.items()}
        
        validation_result["completed_phases_by_category"] = completed_phases_by_category
        validation_result["in_progress_phases_by_category"] = in_progress_phases_by_category
        validation_result["total_questions_answered"] = total_questions_answered
        validation_result["has_any_session"] = has_any_session
        validation_result["session_data"] = session_data
        
        # Analyze profile sections with category awareness
        profile_sections = profile_data.get("recommendationProfiles", {})
        general_profile = profile_data.get("generalprofile", {})
        
        total_detailed_responses = 0
        total_authenticated_responses = 0
        total_foreign_responses = 0
        template_indicators = []
        
        # Map profile section names to categories
        section_to_category = {
            "moviesandtv": "Movies",
            "movies": "Movies", 
            "travel": "Travel",
            "food": "Food",
            "foodanddining": "Food",
            "books": "Books",
            "music": "Music",
            "fitness": "Fitness"
        }
        
        # Check each recommendation profile section
        for section_name, section_data in profile_sections.items():
            section_lower = section_name.lower()
            mapped_category = section_to_category.get(section_lower, section_name)
            
            section_validation = {
                "has_data": bool(section_data),
                "mapped_category": mapped_category,
                "has_session_for_category": mapped_category in completed_phases_by_category or mapped_category in in_progress_phases_by_category,
                "interview_completed_for_category": mapped_category in completed_phases_by_category and len(completed_phases_by_category[mapped_category]) > 0,
                "interview_in_progress_for_category": mapped_category in in_progress_phases_by_category and len(in_progress_phases_by_category[mapped_category]) > 0,
                "data_authenticity": "unknown",
                "detailed_response_count": 0,
                "authenticated_response_count": 0,
                "foreign_response_count": 0
            }
            
            if section_data and isinstance(section_data, dict):
                def analyze_responses(data, path=""):
                    nonlocal total_detailed_responses, total_authenticated_responses, total_foreign_responses
                    
                    if isinstance(data, dict):
                        for key, value in data.items():
                            current_path = f"{path}.{key}" if path else key
                            
                            if isinstance(value, dict) and "value" in value:
                                response_value = value.get("value", "")
                                if isinstance(response_value, str) and len(response_value.strip()) > 10:
                                    section_validation["detailed_response_count"] += 1
                                    total_detailed_responses += 1
                                    
                                    # Check authentication markers
                                    if "user_id" in value and "updated_at" in value:
                                        if value.get("user_id") == user_id:
                                            section_validation["authenticated_response_count"] += 1
                                            total_authenticated_responses += 1
                                        else:
                                            section_validation["foreign_response_count"] += 1
                                            total_foreign_responses += 1
                                            template_indicators.append(
                                                f"Foreign user data: {section_name}.{current_path} (from {value.get('user_id')})"
                                            )
                                
                                # Recursively check nested structures
                                if isinstance(value, dict):
                                    analyze_responses(value, current_path)
                
                analyze_responses(section_data)
                
                # Enhanced authenticity determination with category awareness
                if section_validation["foreign_response_count"] > 0:
                    section_validation["data_authenticity"] = "foreign_user_data"
                elif section_validation["detailed_response_count"] > 0:
                    if section_validation["interview_completed_for_category"]:
                        section_validation["data_authenticity"] = "authentic"
                    elif section_validation["interview_in_progress_for_category"]:
                        section_validation["data_authenticity"] = "in_progress_authentic"
                    elif section_validation["authenticated_response_count"] > 0:
                        section_validation["data_authenticity"] = "authenticated_but_no_session"
                    else:
                        # Check if user has ANY interview activity
                        if has_any_session:
                            section_validation["data_authenticity"] = "possibly_legitimate"
                        else:
                            section_validation["data_authenticity"] = "suspicious_no_sessions"
                            template_indicators.append(
                                f"Detailed data without any interview sessions: {section_name}"
                            )
                else:
                    section_validation["data_authenticity"] = "minimal_data"
            
            validation_result["profile_sections"][section_name] = section_validation
            
            # Track category completeness
            if mapped_category not in validation_result["category_completeness"]:
                validation_result["category_completeness"][mapped_category] = {
                    "has_profile_data": section_validation["has_data"],
                    "has_interview_sessions": section_validation["has_session_for_category"],
                    "interview_completed": section_validation["interview_completed_for_category"],
                    "interview_in_progress": section_validation["interview_in_progress_for_category"],
                    "data_authenticity": section_validation["data_authenticity"],
                    "detailed_responses": section_validation["detailed_response_count"],
                    "authenticated_responses": section_validation["authenticated_response_count"]
                }
        
        # Check general profile
        general_detailed_responses = 0
        general_authenticated_responses = 0
        
        def check_general_profile(data, path="generalprofile"):
            nonlocal general_detailed_responses, general_authenticated_responses
            
            if isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}.{key}"
                    
                    if isinstance(value, dict):
                        if "value" in value and isinstance(value["value"], str) and len(value["value"].strip()) > 10:
                            general_detailed_responses += 1
                            if "user_id" in value and value.get("user_id") == user_id:
                                general_authenticated_responses += 1
                        else:
                            check_general_profile(value, current_path)
        
        check_general_profile(general_profile)
        
        # Calculate totals
        total_responses_with_general = total_detailed_responses + general_detailed_responses
        total_auth_with_general = total_authenticated_responses + general_authenticated_responses
        
        # Calculate authenticity score (more lenient)
        if total_responses_with_general > 0:
            auth_ratio = total_auth_with_general / total_responses_with_general
            session_factor = 1.0 if has_any_session else 0.3
            foreign_penalty = min(total_foreign_responses / max(total_responses_with_general, 1), 0.8)
            
            validation_result["authenticity_score"] = max(0.0, (auth_ratio * 0.6 + session_factor * 0.4) - foreign_penalty)
        else:
            validation_result["authenticity_score"] = 1.0
        
        # Determine overall profile completeness
        completed_categories = len([cat for cat in validation_result["category_completeness"].values() if cat["interview_completed"]])
        total_categories_with_data = len(validation_result["category_completeness"])
        
        if completed_categories > 0:
            if completed_categories == total_categories_with_data:
                validation_result["profile_completeness"] = "complete"
            else:
                validation_result["profile_completeness"] = "partially_complete"
        elif has_any_session and total_questions_answered > 0:
            validation_result["profile_completeness"] = "partial_in_progress"
        elif total_responses_with_general > 0:
            validation_result["profile_completeness"] = "partial_data_exists"
        else:
            validation_result["profile_completeness"] = "empty"
        
        validation_result["template_indicators"] = template_indicators
        validation_result["total_detailed_responses"] = total_responses_with_general
        validation_result["total_authenticated_responses"] = total_auth_with_general
        validation_result["total_foreign_responses"] = total_foreign_responses
        
        # MODIFIED validation logic - more permissive but category-aware
        if total_foreign_responses > 0:
            validation_result["valid"] = False
            validation_result["reason"] = "foreign_user_data_detected"
        elif total_responses_with_general > 10 and not has_any_session:
            validation_result["valid"] = False
            validation_result["reason"] = "extensive_data_without_any_sessions"
        elif validation_result["authenticity_score"] < 0.2:
            validation_result["valid"] = False
            validation_result["reason"] = "very_low_authenticity_score"
        
        # Add enhanced diagnostics
        validation_result["diagnostics"] = {
            "has_interview_activity": has_any_session,
            "questions_answered": total_questions_answered,
            "categories_with_data": total_categories_with_data,
            "completed_categories": completed_categories,
            "authentication_percentage": (total_auth_with_general / max(total_responses_with_general, 1)) * 100,
            "foreign_data_percentage": (total_foreign_responses / max(total_responses_with_general, 1)) * 100,
            "profile_usability": "usable" if validation_result["valid"] else "needs_cleanup"
        }
        
        return validation_result
        
    except Exception as e:
        return {
            "valid": False, 
            "reason": "validation_error", 
            "error": str(e)
        }

def load_user_profile(user_id: str = None) -> Dict[str, Any]:
    """Load and validate USER-SPECIFIC profile from Firestore - matches Streamlit pattern with category awareness"""
    try:
        db = get_firestore_client()
        
        if not user_id:
            print("❌ No user_id provided for profile loading")
            return {}
        
        print(f"🔍 Looking for profile for user: {user_id}")
        
        # Try to find profile in multiple locations (same as Streamlit logic)
        profile_locations = [
            {
                "collection": "user_profiles",
                "document": f"{user_id}_profile_structure.json",
                "description": "Primary user_profiles collection"
            },
            {
                "collection": "user_collection", 
                "document": f"{user_id}_profile_structure.json",
                "description": "Fallback user_collection with user prefix"
            },
            {
                "collection": "user_collection",
                "document": "profile_strcuture.json",  # Matches Streamlit typo
                "description": "Streamlit default profile location"
            },
            {
                "collection": "interview_profiles",
                "document": f"{user_id}_profile.json", 
                "description": "Interview-generated profile"
            },
            {
                "collection": f"user_{user_id}",
                "document": "profile_structure.json",
                "description": "User-specific collection"
            }
        ]
        
        raw_profile = None
        profile_source = None
        
        for location in profile_locations:
            try:
                doc_ref = db.collection(location["collection"]).document(location["document"])
                doc = doc_ref.get()
                
                if doc.exists:
                    raw_profile = doc.to_dict()
                    profile_source = f"{location['collection']}/{location['document']}"
                    print(f"✅ Found profile at: {profile_source}")
                    break
                    
            except Exception as e:
                print(f"❌ Error checking {location['description']}: {e}")
                continue
        
        if not raw_profile:
            print(f"❌ No profile found for user: {user_id}")
            return {}
        
        # Validate profile authenticity with enhanced category-aware validation
        validation = validate_profile_authenticity(raw_profile, user_id, db)
        
        print(f"🔍 Profile validation result: {validation.get('valid')} - {validation.get('reason', 'OK')}")
        print(f"🔍 Profile completeness: {validation.get('profile_completeness', 'unknown')}")
        print(f"🔍 Questions answered: {validation.get('total_questions_answered', 0)}")
        print(f"🔍 Authenticity score: {validation.get('authenticity_score', 0.0):.2f}")
        print(f"🔍 Category completeness: {list(validation.get('category_completeness', {}).keys())}")
        
        if validation.get("warnings"):
            print(f"⚠️ Profile warnings: {validation['warnings']}")
        
        # Only reject for serious contamination
        if not validation.get("valid"):
            serious_issues = ["foreign_user_data_detected", "extensive_data_without_any_sessions"]
            if validation.get("reason") in serious_issues:
                print(f"🚨 SERIOUS PROFILE ISSUE for user {user_id}: {validation.get('reason')}")
                return {
                    "error": "contaminated_profile",
                    "user_id": user_id,
                    "validation": validation,
                    "message": f"Profile validation failed: {validation.get('reason')}",
                    "profile_source": profile_source
                }
            else:
                print(f"⚠️ Minor profile issue for user {user_id}: {validation.get('reason')} - allowing with warnings")
        
        # Return profile with validation info (even if partial)
        profile_with_metadata = raw_profile.copy()
        profile_with_metadata["_validation"] = validation
        profile_with_metadata["_source"] = profile_source
        
        return profile_with_metadata
        
    except Exception as e:
        print(f"❌ Error loading user profile for {user_id}: {e}")
        return {}

def search_web(query, max_results=3, max_retries=3, base_delay=1.0):
    """Query DuckDuckGo via DDGS.text(), returning up to max_results items."""
    for attempt in range(1, max_retries + 1):
        try:
            with DDGS() as ddgs:
                return list(islice(ddgs.text(query), max_results))
        except DuckDuckGoSearchException as e:
            msg = str(e)
            if "202" in msg:
                wait = base_delay * (2 ** (attempt - 1))
                print(f"[search_web] Rate‑limited (202). Retry {attempt}/{max_retries} in {wait:.1f}s…")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            print(f"[search_web] Unexpected error: {e}")
            break
    
    print(f"[search_web] Failed to fetch results after {max_retries} attempts.")
    return []

def generate_recommendations(user_profile, user_query, openai_key, category=None):
    """Generate 3 personalized recommendations using user profile and web search - STREAMLIT COMPATIBLE"""
    
    # Enhanced search with category context
    if category:
        search_query = f"{category} {user_query} recommendations 2024"
    else:
        search_query = f"{user_query} recommendations 2024"
    
    search_results = search_web(search_query)
    
    # Category-specific instructions
    category_instructions = ""
    if category:
        category_lower = category.lower()
        
        if category_lower in ["travel", "travel & destinations"]:
            category_instructions = """
            **CATEGORY FOCUS: TRAVEL & DESTINATIONS**
            - Recommend specific destinations, attractions, or travel experiences
            - Include practical travel advice (best time to visit, transportation, accommodations)
            - Consider cultural experiences, local cuisine, historical sites, natural attractions
            - Focus on places to visit, things to do, travel itineraries
            - DO NOT recommend economic plans, political content, or business strategies
            
            **EXAMPLE for Pakistan Travel Query**:
            - "Hunza Valley, Pakistan" - Mountain valley with stunning landscapes
            - "Lahore Food Street" - Culinary travel experience in historic city
            - "Skardu Adventures" - Trekking and mountaineering destination
            """
            
        elif category_lower in ["movies", "movies & tv", "entertainment"]:
            category_instructions = """
            **CATEGORY FOCUS: MOVIES & TV**
            - Recommend specific movies, TV shows, or streaming content
            - Consider genres, directors, actors, themes that match user preferences
            - Include where to watch (streaming platforms) if possible
            - Focus on entertainment content, not travel or other categories
            """
            
        elif category_lower in ["food", "food & dining", "restaurants"]:
            category_instructions = """
            **CATEGORY FOCUS: FOOD & DINING**
            - Recommend specific restaurants, cuisines, or food experiences
            - Include local specialties, popular dishes, dining venues
            - Consider user's location and dietary preferences
            - Focus on food and dining experiences, not travel destinations
            """
            
        else:
            category_instructions = f"""
            **CATEGORY FOCUS: {category.upper()}**
            - Focus recommendations specifically on {category} related content
            - Ensure all suggestions are relevant to the {category} category
            - Do not recommend content from other categories
            """
    
    prompt = f"""
    **Task**: Generate exactly 3 highly personalized {category + ' ' if category else ''}recommendations based on:
    
    {category_instructions}
    
    **User Profile**:
    {json.dumps(user_profile, indent=2)}
    
    **User Query**:
    "{user_query}"
    
    **Web Context** (for reference only):
    {search_results}
    
    **Requirements**:
    1. Each recommendation must directly reference profile details when available
    2. ALL recommendations MUST be relevant to the "{category}" category if specified
    3. Blend the user's core values and preferences from their profile
    4. Only suggest what is asked for - no extra advice
    5. For travel queries, recommend specific destinations, attractions, or experiences
    6. Format as JSON array with each recommendation having:
       - title: string (specific name of place/item/experience)
       - description: string (brief description of what it is)
       - reasons: array of strings (why it matches the user profile)
       - confidence_score: float (0.0-1.0)
    
    **CRITICAL for Travel Category**: 
    If this is a travel recommendation, suggest actual destinations, attractions, restaurants, or travel experiences.
    DO NOT suggest economic plans, political content, or business strategies.
    
    **Output Example for Travel**:
    [
      {{
         "title": "Hunza Valley, Pakistan",
         "description": "Breathtaking mountain valley known for stunning landscapes and rich cultural heritage",
         "reasons": ["Matches your love for natural beauty and cultural exploration", "Perfect for peaceful mountain retreats you prefer"],
         "confidence_score": 0.9
      }},
      {{
         "title": "Lahore Food Street, Pakistan", 
         "description": "Historic food destination offering authentic Pakistani cuisine and cultural immersion",
         "reasons": ["Aligns with your interest in trying traditional foods", "Offers the cultural experiences you enjoy"],
         "confidence_score": 0.85
      }},
      {{
         "title": "Skardu, Pakistan",
         "description": "Adventure destination for trekking and mountaineering with stunning natural scenery",
         "reasons": ["Perfect for your moderate adventure seeking preferences", "Offers the peaceful outdoor experiences you value"],
         "confidence_score": 0.8
      }}
    ]
    
    Generate your response in JSON format only.
    """
    
    # Setting up LLM - same as Streamlit pattern
    client = OpenAI(api_key=openai_key)

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": f"You're a recommendation engine that creates hyper-personalized {category.lower() if category else ''} suggestions. You MUST focus on {category.lower() if category else 'relevant'} content only. Output valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7  
    )
    
    return response.choices[0].message.content

# ROUTE DEFINITIONS - SPECIFIC ROUTES FIRST, PARAMETERIZED ROUTES LAST

@router.get("/profile")
async def get_user_profile(current_user: str = Depends(get_current_user)):
    """Get the current user's profile with category-specific completeness info"""
    try:
        print(f"🔍 Getting profile for user: {current_user}")
        profile = load_user_profile(current_user)
        
        # Handle contaminated profile (only for serious issues)
        if isinstance(profile, dict) and profile.get("error") == "contaminated_profile":
            validation_info = profile.get("validation", {})
            
            if validation_info.get("reason") == "foreign_user_data_detected":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "contaminated_profile",
                        "message": "Profile contains data from other users",
                        "user_id": current_user,
                        "validation": validation_info,
                        "recommended_action": "clear_contaminated_profile_and_restart_interview"
                    }
                )
            elif validation_info.get("reason") == "extensive_data_without_any_sessions":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "suspicious_profile",
                        "message": "Profile has extensive data but no interview sessions",
                        "user_id": current_user,
                        "validation": validation_info,
                        "recommended_action": "start_interview_to_validate_or_clear_profile"
                    }
                )
        
        if not profile:
            # Check interview status
            db = get_firestore_client()
            sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
            sessions = list(sessions_ref.stream())
            
            if not sessions:
                raise HTTPException(
                    status_code=404,
                    detail="No profile found. Please start an interview to begin creating your profile."
                )
            
            # If there are sessions but no profile, suggest continuing
            in_progress_sessions = [s for s in sessions if s.to_dict().get("status") == "in_progress"]
            if in_progress_sessions:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "message": "Interview in progress but no profile generated yet. Continue the interview to build your profile.",
                        "sessions": [{"session_id": s.id, "phase": s.to_dict().get("current_phase"), "category": s.to_dict().get("selected_category")} for s in in_progress_sessions]
                    }
                )
        
        # Return profile with enhanced category information
        clean_profile = {k: v for k, v in profile.items() if not k.startswith('_')}
        validation_summary = profile.get("_validation", {})
        
        response = {
            "success": True,
            "profile": clean_profile,
            "user_id": current_user,
            "profile_type": "user_specific",
            "profile_found": True,
            "profile_completeness": validation_summary.get("profile_completeness", "unknown"),
            "category_completeness": validation_summary.get("category_completeness", {}),
            "validation_summary": {
                "valid": validation_summary.get("valid", True),
                "authenticity_score": validation_summary.get("authenticity_score", 1.0),
                "reason": validation_summary.get("reason"),
                "has_interview_activity": validation_summary.get("has_any_session", False),
                "questions_answered": validation_summary.get("total_questions_answered", 0),
                "total_responses": validation_summary.get("total_detailed_responses", 0),
                "authenticated_responses": validation_summary.get("total_authenticated_responses", 0),
                "completed_phases_by_category": validation_summary.get("completed_phases_by_category", {}),
                "in_progress_phases_by_category": validation_summary.get("in_progress_phases_by_category", {})
            },
            "profile_source": profile.get("_source", "unknown")
        }
        
        # Add enhanced guidance based on category completeness
        category_completeness = validation_summary.get("category_completeness", {})
        completed_categories = [cat for cat, data in category_completeness.items() if data.get("interview_completed")]
        in_progress_categories = [cat for cat, data in category_completeness.items() if data.get("interview_in_progress")]
        available_categories = ["Movies", "Food", "Travel", "Books", "Music", "Fitness"]
        not_started_categories = [cat for cat in available_categories if cat not in category_completeness]
        
        if len(completed_categories) == len(category_completeness) and len(completed_categories) > 0:
            response["message"] = f"Profile complete for {len(completed_categories)} categories: {', '.join(completed_categories)}. You can start interviews for other categories or update existing ones."
        elif len(completed_categories) > 0:
            response["message"] = f"Profile complete for: {', '.join(completed_categories)}. Continue in-progress categories or start new ones."
        elif len(in_progress_categories) > 0:
            response["message"] = f"Interviews in progress for: {', '.join(in_progress_categories)}. Continue these or start new category interviews."
        else:
            response["message"] = "Start category interviews to build your personalized profile."
        
        # Add actionable suggestions
        response["suggestions"] = {
            "completed_categories": completed_categories,
            "in_progress_categories": in_progress_categories,
            "available_to_start": not_started_categories,
            "can_update": completed_categories,
            "should_continue": in_progress_categories
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in get_user_profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load profile: {str(e)}"
        )

@router.get("/profile/category/{category}")
async def get_category_profile_status(
    category: str,
    current_user: str = Depends(get_current_user)
):
    """Get profile status for a specific category"""
    try:
        profile = load_user_profile(current_user)
        
        if not profile:
            return {
                "success": False,
                "user_id": current_user,
                "category": category,
                "has_data": False,
                "message": f"No profile found. Start a {category} interview to begin."
            }
        
        validation_summary = profile.get("_validation", {})
        category_completeness = validation_summary.get("category_completeness", {})
        
        if category in category_completeness:
            category_data = category_completeness[category]
            return {
                "success": True,
                "user_id": current_user,
                "category": category,
                "has_data": category_data.get("has_profile_data", False),
                "interview_completed": category_data.get("interview_completed", False),
                "interview_in_progress": category_data.get("interview_in_progress", False),
                "data_authenticity": category_data.get("data_authenticity", "unknown"),
                "detailed_responses": category_data.get("detailed_responses", 0),
                "authenticated_responses": category_data.get("authenticated_responses", 0),
                "status": "completed" if category_data.get("interview_completed") else "in_progress" if category_data.get("interview_in_progress") else "has_data",
                "message": f"{category} profile status: {category_data.get('data_authenticity', 'unknown')}"
            }
        else:
            return {
                "success": True,
                "user_id": current_user,
                "category": category,
                "has_data": False,
                "interview_completed": False,
                "interview_in_progress": False,
                "status": "not_started",
                "message": f"No {category} profile data found. Start a {category} interview to begin building this section."
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get category profile status: {str(e)}"
        )

@router.post("/restart/{category}")
async def restart_category_interview(
    category: str,
    current_user: str = Depends(get_current_user)
):
    """Restart interview for a specific category"""
    try:
        db = get_firestore_client()
        
        # Find existing sessions for this category
        sessions_query = db.collection("interview_sessions")\
            .where("user_id", "==", current_user)\
            .where("selected_category", "==", category)
        
        existing_sessions = list(sessions_query.stream())
        
        # Archive all existing sessions for this category
        for session in existing_sessions:
            session.reference.update({
                "status": "archived",
                "archived_at": datetime.utcnow(),
                "archived_reason": "category_restart"
            })
        
        # Create new session
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "user_id": current_user,
            "selected_category": category,
            "status": "in_progress",
            "current_tier": 1,
            "current_phase": "general",
            "questions_answered": 0,
            "total_tiers": 3,
            "is_complete": False,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "user_specific": True,
            "restart_count": len(existing_sessions)
        }
        
        # Save new session
        db.collection("interview_sessions").document(session_id).set(session_data)
        
        return {
            "success": True,
            "message": f"Restarted {category} interview",
            "session_id": session_id,
            "user_id": current_user,
            "category": category,
            "archived_sessions": len(existing_sessions),
            "status": "in_progress"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restart {category} interview: {str(e)}"
        )

@router.get("/categories")
async def get_recommendation_categories():
    """Get available recommendation categories"""
    categories = [
        {
            "id": "movies",
            "name": "Movies & TV",
            "description": "Movie and TV show recommendations",
            "questions_file": "moviesAndTV_tiered_questions.json"
        },
        {
            "id": "food",
            "name": "Food & Dining",
            "description": "Restaurant and food recommendations",
            "questions_file": "foodAndDining_tiered_questions.json"
        },
        {
            "id": "travel",
            "name": "Travel",
            "description": "Travel destination recommendations",
            "questions_file": "travel_tiered_questions.json"
        },
        {
            "id": "books",
            "name": "Books & Reading",
            "description": "Book recommendations",
            "questions_file": "books_tiered_questions.json"
        },
        {
            "id": "music",
            "name": "Music",
            "description": "Music and artist recommendations",
            "questions_file": "music_tiered_questions.json"
        },
        {
            "id": "fitness",
            "name": "Fitness & Wellness",
            "description": "Fitness and wellness recommendations",
            "questions_file": "fitness_tiered_questions.json"
        }
    ]
    
    return {
        "categories": categories,
        "default_category": "movies"
    }

@router.post("/generate", response_model=RecommendationResponse)
async def generate_user_recommendations(
    request: RecommendationRequest,
    current_user: str = Depends(get_current_user)
):
    """Generate recommendations using the same logic as Streamlit but enhanced for FastAPI"""
    try:
        start_time = datetime.utcnow()
        settings = get_settings()
        db = get_firestore_client()
        
        print(f"🚀 Generating recommendations for user: {current_user}")
        print(f"📝 Query: {request.query}")
        print(f"🏷️ Category: {request.category}")
        
        # Load profile (same as Streamlit)
        user_profile = load_user_profile(current_user)
        
        # Handle serious contamination only
        if isinstance(user_profile, dict) and user_profile.get("error") == "contaminated_profile":
            validation = user_profile.get("validation", {})
            if validation.get("reason") in ["foreign_user_data_detected", "extensive_data_without_any_sessions"]:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "contaminated_profile",
                        "message": "Cannot generate recommendations with contaminated profile data",
                        "recommended_action": "clear_profile_and_start_interview"
                    }
                )
        
        # If no profile, check if we should allow basic recommendations (same as Streamlit)
        if not user_profile:
            print("⚠️ No profile found - checking interview status")
            
            # Check if user has any interview activity
            sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
            sessions = list(sessions_ref.stream())
            
            if not sessions:
                # No interview started - create minimal profile for basic recommendations
                print("📝 No interview sessions - creating basic profile for general recommendations")
                user_profile = {
                    "user_id": current_user,
                    "generalprofile": {
                        "corePreferences": {
                            "note": f"Basic profile - complete interview for personalized {request.category or 'recommendations'}"
                        }
                    },
                    "profile_completeness": "empty"
                }
            else:
                # Has interview activity but no profile - this shouldn't happen
                raise HTTPException(
                    status_code=404,
                    detail="Interview sessions found but no profile generated. Please contact support."
                )
        
        # Clean profile for AI processing (remove metadata)
        clean_profile = {k: v for k, v in user_profile.items() if not k.startswith('_')}
        
        # Get profile completeness info
        validation_summary = user_profile.get("_validation", {})
        profile_completeness = validation_summary.get("profile_completeness", "unknown")
        questions_answered = validation_summary.get("total_questions_answered", 0)
        category_completeness = validation_summary.get("category_completeness", {})
        
        print(f"📊 Profile completeness: {profile_completeness}")
        print(f"📝 Questions answered: {questions_answered}")
        print(f"🏷️ Category completeness: {list(category_completeness.keys())}")
        
        # Check if the requested category has data
        category_has_data = False
        category_status = "not_started"
        if request.category and request.category in category_completeness:
            category_data = category_completeness[request.category]
            category_has_data = category_data.get("has_profile_data", False)
            if category_data.get("interview_completed"):
                category_status = "completed"
            elif category_data.get("interview_in_progress"):
                category_status = "in_progress"
            else:
                category_status = "has_data"
        
        print(f"🎯 Category {request.category} status: {category_status}, has_data: {category_has_data}")
        
        # Generate category-aware recommendations
        recs_json = generate_recommendations(
            clean_profile, 
            request.query, 
            settings.OPENAI_API_KEY,
            request.category  # Add category parameter
        )
        
        try:
            recs = json.loads(recs_json)
            
            # Normalize to list (same as Streamlit)
            if isinstance(recs, dict):
                if "recommendations" in recs and isinstance(recs["recommendations"], list):
                    recs = recs["recommendations"]
                else:
                    recs = [recs]
            
            if not isinstance(recs, list):
                raise HTTPException(
                    status_code=500,
                    detail="Unexpected response format – expected a list of recommendations."
                )
            
            # Validate category relevance for travel
            if request.category and request.category.lower() == "travel":
                travel_keywords = ["destination", "place", "visit", "travel", "city", "country", "attraction", "trip", "valley", "mountain", "beach", "street", "food", "culture", "heritage", "adventure", "pakistan", "hunza", "lahore", "skardu"]
                
                for i, rec in enumerate(recs):
                    title_and_desc = (rec.get('title', '') + ' ' + rec.get('description', '')).lower()
                    if not any(keyword in title_and_desc for keyword in travel_keywords):
                        print(f"⚠️ Recommendation {i+1} '{rec.get('title')}' may not be travel-related")
                        print(f"🔍 Content: {title_and_desc[:100]}...")
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Add profile completion guidance based on category status
            for rec in recs:
                if "reasons" not in rec:
                    rec["reasons"] = []
                
                if request.category and category_status == "not_started":
                    rec["reasons"].append(f"Start a {request.category} interview for more personalized recommendations")
                elif request.category and category_status == "in_progress":
                    rec["reasons"].append(f"Continue your {request.category} interview for better personalization")
                elif profile_completeness == "empty":
                    rec["reasons"].append("Start an interview to get more personalized recommendations")
                elif profile_completeness in ["partial_in_progress", "partial_data_exists"]:
                    rec["reasons"].append("Complete more interview questions for better personalization")
            
            # Generate session ID for conversation tracking
            session_id = str(uuid.uuid4())
            
            # Save conversation messages (like Streamlit chat)
            save_conversation_message(
                current_user, 
                session_id, 
                "user", 
                f"What would you like {request.category.lower() if request.category else ''} recommendations for? {request.query}", 
                "recommendation",
                f"{request.category or 'General'} Recommendation Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
            # Prepare recommendation data for database
            recommendation_data = {
                "user_id": current_user,
                "query": request.query,
                "category": request.category,
                "recommendations": recs,
                "processing_time_ms": int(processing_time),
                "search_context": search_web(f"{request.category} {request.query} recommendations 2024" if request.category else f"{request.query} recommendations 2024"),
                "session_id": session_id,
                "profile_version": clean_profile.get("version", "1.0"),
                "profile_completeness": profile_completeness,
                "category_status": category_status,
                "category_has_data": category_has_data,
                "questions_answered": questions_answered,
                "user_specific": True,
                "generation_method": "streamlit_compatible"
            }
            
            # Save to database
            recommendation_id = save_recommendation_to_db(recommendation_data, db)
            
            if not recommendation_id:
                print("⚠️ Warning: Failed to save recommendation to database")
                recommendation_id = str(uuid.uuid4())  # Fallback
            
            # Format recommendations for conversation history (like Streamlit display)
            recs_text = f"Here are your {request.category.lower() if request.category else ''} recommendations:\n\n"
            
            for i, rec in enumerate(recs, 1):
                title = rec.get("title", "<no title>")
                description = rec.get("description", rec.get("reason", "<no description>"))
                reasons = rec.get("reasons", [])
                
                recs_text += f"**{i}. {title}**\n"
                recs_text += f"{description}\n"
                if reasons:
                    for reason in reasons:
                        recs_text += f"• {reason}\n"
                recs_text += "\n"
            
            # Save recommendations to conversation history
            save_conversation_message(
                current_user, 
                session_id, 
                "assistant", 
                recs_text, 
                "recommendation"
            )
            
            # Convert to RecommendationItem objects
            recommendation_items = []
            for rec in recs:
                # Use confidence score from AI or default based on profile completeness
                base_confidence = 0.6 if profile_completeness == "empty" or category_status == "not_started" else 0.8
                confidence_score = rec.get('confidence_score', base_confidence)
                
                recommendation_items.append(RecommendationItem(
                    title=rec.get('title', 'Recommendation'),
                    description=rec.get('description', rec.get('reason', '')),
                    reasons=rec.get('reasons', []),
                    category=request.category,
                    confidence_score=confidence_score
                ))
            
            return RecommendationResponse(
                recommendation_id=recommendation_id,
                recommendations=recommendation_items,
                query=request.query,
                category=request.category,
                user_id=current_user,
                generated_at=datetime.utcnow(),
                processing_time_ms=int(processing_time)
            )
            
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse recommendations: {str(e)}"
            print(f"❌ JSON parsing error: {error_msg}")
            print(f"🔍 Raw AI response: {recs_json[:500]}...")
            
            # Save error to conversation history
            save_conversation_message(
                current_user, 
                str(uuid.uuid4()), 
                "assistant", 
                f"Sorry, I encountered an error generating {request.category or ''} recommendations: {error_msg}", 
                "recommendation"
            )
            
            raise HTTPException(
                status_code=500,
                detail=error_msg
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error generating recommendations for user {current_user}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate {request.category or ''} recommendations: {str(e)}"
        )

@router.get("/history")
async def get_recommendation_history(
    current_user: str = Depends(get_current_user),
    limit: int = Query(20, description="Number of recommendations to return"),
    offset: int = Query(0, description="Number of recommendations to skip"),
    category: Optional[str] = Query(None, description="Filter by category")
):
    """Get recommendation history for the user with enhanced filtering"""
    try:
        db = get_firestore_client()
        
        # Simplified query to avoid index issues
        query = db.collection("user_recommendations").document(current_user).collection("recommendations")
        query = query.where("is_active", "==", True)
        query = query.limit(limit).offset(offset)
        
        recommendations = list(query.stream())
        
        # Filter and sort in Python
        filtered_recs = []
        for rec in recommendations:
            rec_data = rec.to_dict()
            
            # Apply category filter
            if category and rec_data.get("category") != category:
                continue
            
            filtered_recs.append(rec_data)
        
        # Sort by generated_at descending
        filtered_recs.sort(key=lambda x: x.get("generated_at", datetime.min), reverse=True)
        
        # Format response
        history = []
        for rec_data in filtered_recs:
            history.append({
                "recommendation_id": rec_data["recommendation_id"],
                "query": rec_data["query"],
                "category": rec_data.get("category"),
                "recommendations_count": len(rec_data.get("recommendations", [])),
                "generated_at": rec_data["generated_at"],
                "view_count": rec_data.get("view_count", 0),
                "feedback_count": rec_data.get("feedback_count", 0),
                "session_id": rec_data.get("session_id"),
                "processing_time_ms": rec_data.get("processing_time_ms"),
                "profile_completeness": rec_data.get("profile_completeness", "unknown"),
                "category_status": rec_data.get("category_status", "unknown"),
                "generation_method": rec_data.get("generation_method", "unknown")
            })
        
        return {
            "success": True,
            "history": history,
            "total_count": len(history),
            "user_id": current_user,
            "filters": {
                "category": category,
                "limit": limit,
                "offset": offset
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recommendation history: {str(e)}"
        )

@router.post("/{recommendation_id}/feedback")
async def submit_recommendation_feedback(
    recommendation_id: str,
    feedback: RecommendationFeedback,
    current_user: str = Depends(get_current_user)
):
    """Submit feedback for a recommendation"""
    try:
        db = get_firestore_client()
        
        # Verify recommendation exists and belongs to user
        rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
        if not rec_doc.exists:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        # Save feedback
        feedback_data = {
            "feedback_type": feedback.feedback_type,
            "rating": feedback.rating,
            "comment": feedback.comment,
            "clicked_items": feedback.clicked_items
        }
        
        feedback_id = save_recommendation_feedback(recommendation_id, current_user, feedback_data, db)
        
        if not feedback_id:
            raise HTTPException(status_code=500, detail="Failed to save feedback")
        
        return {
            "success": True,
            "message": "Feedback submitted successfully",
            "feedback_id": feedback_id,
            "recommendation_id": recommendation_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit feedback: {str(e)}"
        )

# IMPORTANT: Put parameterized routes LAST to avoid route conflicts
@router.get("/{recommendation_id}")
async def get_recommendation_details(
    recommendation_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get detailed information about a specific recommendation"""
    try:
        db = get_firestore_client()
        
        # Get recommendation details
        rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
        if not rec_doc.exists:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        rec_data = rec_doc.to_dict()
        
        # Increment view count
        current_views = rec_data.get("view_count", 0)
        rec_doc.reference.update({
            "view_count": current_views + 1,
            "last_viewed": datetime.utcnow()
        })
        
        return {
            "success": True,
            "recommendation": {
                "recommendation_id": rec_data["recommendation_id"],
                "query": rec_data["query"],
                "category": rec_data.get("category"),
                "recommendations": rec_data["recommendations"],
                "generated_at": rec_data["generated_at"],
                "processing_time_ms": rec_data.get("processing_time_ms"),
                "view_count": current_views + 1,
                "search_context": rec_data.get("search_context", []),
                "profile_completeness": rec_data.get("profile_completeness", "unknown"),
                "category_status": rec_data.get("category_status", "unknown"),
                "questions_answered": rec_data.get("questions_answered", 0),
                "generation_method": rec_data.get("generation_method", "unknown")
            },
            "user_id": current_user
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recommendation details: {str(e)}"
        )# app/routers/recommendations.py - Complete Enhanced with Category Management

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
from openai import OpenAI
from duckduckgo_search import DDGS 
from duckduckgo_search.exceptions import DuckDuckGoSearchException
from itertools import islice
import time
import uuid
from datetime import datetime, timedelta

from app.core.security import get_current_user
from app.core.firebase import get_firestore_client
from app.core.config import get_settings
from app.routers.conversations import save_conversation_message

router = APIRouter()

# Enhanced Pydantic models
class RecommendationRequest(BaseModel):
    query: str
    category: Optional[str] = None
    user_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class RecommendationItem(BaseModel):
    title: str
    description: Optional[str] = None
    reasons: List[str] = []
    category: Optional[str] = None
    confidence_score: Optional[float] = None
    external_links: Optional[List[str]] = None

class RecommendationResponse(BaseModel):
    recommendation_id: str
    recommendations: List[RecommendationItem]
    query: str
    category: Optional[str] = None
    user_id: str
    generated_at: datetime
    processing_time_ms: Optional[int] = None
class RecommendationFeedback(BaseModel):
    recommendation_id: str
    feedback_type: str  # 'like', 'dislike', 'not_relevant', 'helpful'
    rating: Optional[int] = None  # 1-5 stars
    comment: Optional[str] = None
    clicked_items: List[str] = []

# Database helper functions
def save_recommendation_to_db(recommendation_data: Dict[str, Any], db) -> str:
    """Save recommendation to database and return recommendation_id"""
    try:
        recommendation_id = str(uuid.uuid4())
        
        # Prepare data for database
        db_data = {
            "recommendation_id": recommendation_id,
            "user_id": recommendation_data["user_id"],
            "query": recommendation_data["query"],
            "category": recommendation_data.get("category"),
            "recommendations": recommendation_data["recommendations"],
            "generated_at": datetime.utcnow(),
            "processing_time_ms": recommendation_data.get("processing_time_ms"),
            "search_context": recommendation_data.get("search_context", []),
            "profile_version": recommendation_data.get("profile_version"),
            "profile_completeness": recommendation_data.get("profile_completeness"),
            "questions_answered": recommendation_data.get("questions_answered", 0),
            "session_id": recommendation_data.get("session_id"),
            "generation_method": recommendation_data.get("generation_method"),
            "is_active": True,
            "view_count": 0,
            "feedback_count": 0
        }
        
        # Save to user-specific collection
        db.collection("user_recommendations").document(recommendation_data["user_id"]).collection("recommendations").document(recommendation_id).set(db_data)
        
        # Also save to recommendation history for analytics
        history_data = {
            "recommendation_id": recommendation_id,
            "user_id": recommendation_data["user_id"],
            "query": recommendation_data["query"],
            "category": recommendation_data.get("category"),
            "recommendations_count": len(recommendation_data["recommendations"]),
            "profile_completeness": recommendation_data.get("profile_completeness"),
            "created_at": datetime.utcnow(),
            "is_bookmarked": False,
            "tags": []
        }
        
        db.collection("recommendation_history").document(recommendation_id).set(history_data)
        
        return recommendation_id
        
    except Exception as e:
        print(f"Error saving recommendation: {e}")
        return None

def save_recommendation_feedback(recommendation_id: str, user_id: str, feedback_data: Dict[str, Any], db):
    """Save user feedback for a recommendation"""
    try:
        feedback_id = str(uuid.uuid4())
        
        feedback_doc = {
            "feedback_id": feedback_id,
            "recommendation_id": recommendation_id,
            "user_id": user_id,
            "feedback_type": feedback_data["feedback_type"],
            "rating": feedback_data.get("rating"),
            "comment": feedback_data.get("comment"),
            "clicked_items": feedback_data.get("clicked_items", []),
            "created_at": datetime.utcnow()
        }
        
        # Save feedback
        db.collection("recommendation_feedback").document(feedback_id).set(feedback_doc)
        
        # Update recommendation with feedback count
        rec_ref = db.collection("user_recommendations").document(user_id).collection("recommendations").document(recommendation_id)
        rec_doc = rec_ref.get()
        
        if rec_doc.exists:
            current_feedback_count = rec_doc.to_dict().get("feedback_count", 0)
            rec_ref.update({"feedback_count": current_feedback_count + 1})
        
        return feedback_id
        
    except Exception as e:
        print(f"Error saving feedback: {e}")
        return None

# ENHANCED Category-Aware Profile validation and loading functions
def validate_profile_authenticity(profile_data: Dict[str, Any], user_id: str, db) -> Dict[str, Any]:
    """Enhanced validation that's category-aware and allows partial profiles"""
    
    if not profile_data or not user_id:
        return {"valid": False, "reason": "empty_profile_or_user"}
    
    validation_result = {
        "valid": True,
        "warnings": [],
        "user_id": user_id,
        "profile_sections": {},
        "authenticity_score": 1.0,
        "template_indicators": [],
        "profile_completeness": "partial",
        "category_completeness": {}  # NEW: Track completeness per category
    }
    
    try:
        # Check interview sessions for this user (grouped by category)
        interview_sessions = db.collection("interview_sessions").where("user_id", "==", user_id).stream()
        
        completed_phases_by_category = {}
        in_progress_phases_by_category = {}
        session_data = {}
        total_questions_answered = 0
        has_any_session = False
        
        for session in interview_sessions:
            has_any_session = True
            session_dict = session.to_dict()
            session_data[session.id] = session_dict
            
            category = session_dict.get("selected_category", "unknown")
            phase = session_dict.get("current_phase", "general")
            
            if category not in completed_phases_by_category:
                completed_phases_by_category[category] = set()
            if category not in in_progress_phases_by_category:
                in_progress_phases_by_category[category] = set()
            
            if session_dict.get("status") == "completed":
                completed_phases_by_category[category].add(phase)
                total_questions_answered += session_dict.get("questions_answered", 0)
            elif session_dict.get("status") == "in_progress":
                in_progress_phases_by_category[category].add(phase)
                total_questions_answered += session_dict.get("questions_answered", 0)
        
        # Convert sets to lists for JSON serialization
        completed_phases_by_category = {k: list(v) for k, v in completed_phases_by_category.items()}
        in_progress_phases_by_category = {k: list(v) for k, v in in_progress_phases_by_category.items()}
        
        validation_result["completed_phases_by_category"] = completed_phases_by_category
        validation_result["in_progress_phases_by_category"] = in_progress_phases_by_category
        validation_result["total_questions_answered"] = total_questions_answered
        validation_result["has_any_session"] = has_any_session
        validation_result["session_data"] = session_data
        
        # Analyze profile sections with category awareness
        profile_sections = profile_data.get("recommendationProfiles", {})
        general_profile = profile_data.get("generalprofile", {})
        
        total_detailed_responses = 0
        total_authenticated_responses = 0
        total_foreign_responses = 0
        template_indicators = []
        
        # Map profile section names to categories
        section_to_category = {
            "moviesandtv": "Movies",
            "movies": "Movies", 
            "travel": "Travel",
            "food": "Food",
            "foodanddining": "Food",
            "books": "Books",
            "music": "Music",
            "fitness": "Fitness"
        }
        
        # Check each recommendation profile section
        for section_name, section_data in profile_sections.items():
            section_lower = section_name.lower()
            mapped_category = section_to_category.get(section_lower, section_name)
            
            section_validation = {
                "has_data": bool(section_data),
                "mapped_category": mapped_category,
                "has_session_for_category": mapped_category in completed_phases_by_category or mapped_category in in_progress_phases_by_category,
                "interview_completed_for_category": mapped_category in completed_phases_by_category and len(completed_phases_by_category[mapped_category]) > 0,
                "interview_in_progress_for_category": mapped_category in in_progress_phases_by_category and len(in_progress_phases_by_category[mapped_category]) > 0,
                "data_authenticity": "unknown",
                "detailed_response_count": 0,
                "authenticated_response_count": 0,
                "foreign_response_count": 0
            }
            
            if section_data and isinstance(section_data, dict):
                def analyze_responses(data, path=""):
                    nonlocal total_detailed_responses, total_authenticated_responses, total_foreign_responses
                    
                    if isinstance(data, dict):
                        for key, value in data.items():
                            current_path = f"{path}.{key}" if path else key
                            
                            if isinstance(value, dict) and "value" in value:
                                response_value = value.get("value", "")
                                if isinstance(response_value, str) and len(response_value.strip()) > 10:
                                    section_validation["detailed_response_count"] += 1
                                    total_detailed_responses += 1
                                    
                                    # Check authentication markers
                                    if "user_id" in value and "updated_at" in value:
                                        if value.get("user_id") == user_id:
                                            section_validation["authenticated_response_count"] += 1
                                            total_authenticated_responses += 1
                                        else:
                                            section_validation["foreign_response_count"] += 1
                                            total_foreign_responses += 1
                                            template_indicators.append(
                                                f"Foreign user data: {section_name}.{current_path} (from {value.get('user_id')})"
                                            )
                                
                                # Recursively check nested structures
                                if isinstance(value, dict):
                                    analyze_responses(value, current_path)
                
                analyze_responses(section_data)
                
                # Enhanced authenticity determination with category awareness
                if section_validation["foreign_response_count"] > 0:
                    section_validation["data_authenticity"] = "foreign_user_data"
                elif section_validation["detailed_response_count"] > 0:
                    if section_validation["interview_completed_for_category"]:
                        section_validation["data_authenticity"] = "authentic"
                    elif section_validation["interview_in_progress_for_category"]:
                        section_validation["data_authenticity"] = "in_progress_authentic"
                    elif section_validation["authenticated_response_count"] > 0:
                        section_validation["data_authenticity"] = "authenticated_but_no_session"
                    else:
                        # Check if user has ANY interview activity
                        if has_any_session:
                            section_validation["data_authenticity"] = "possibly_legitimate"
                        else:
                            section_validation["data_authenticity"] = "suspicious_no_sessions"
                            template_indicators.append(
                                f"Detailed data without any interview sessions: {section_name}"
                            )
                else:
                    section_validation["data_authenticity"] = "minimal_data"
            
            validation_result["profile_sections"][section_name] = section_validation
            
            # Track category completeness
            if mapped_category not in validation_result["category_completeness"]:
                validation_result["category_completeness"][mapped_category] = {
                    "has_profile_data": section_validation["has_data"],
                    "has_interview_sessions": section_validation["has_session_for_category"],
                    "interview_completed": section_validation["interview_completed_for_category"],
                    "interview_in_progress": section_validation["interview_in_progress_for_category"],
                    "data_authenticity": section_validation["data_authenticity"],
                    "detailed_responses": section_validation["detailed_response_count"],
                    "authenticated_responses": section_validation["authenticated_response_count"]
                }
        
        # Check general profile
        general_detailed_responses = 0
        general_authenticated_responses = 0
        
        def check_general_profile(data, path="generalprofile"):
            nonlocal general_detailed_responses, general_authenticated_responses
            
            if isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}.{key}"
                    
                    if isinstance(value, dict):
                        if "value" in value and isinstance(value["value"], str) and len(value["value"].strip()) > 10:
                            general_detailed_responses += 1
                            if "user_id" in value and value.get("user_id") == user_id:
                                general_authenticated_responses += 1
                        else:
                            check_general_profile(value, current_path)
        
        check_general_profile(general_profile)
        
        # Calculate totals
        total_responses_with_general = total_detailed_responses + general_detailed_responses
        total_auth_with_general = total_authenticated_responses + general_authenticated_responses
        
        # Calculate authenticity score (more lenient)
        if total_responses_with_general > 0:
            auth_ratio = total_auth_with_general / total_responses_with_general
            session_factor = 1.0 if has_any_session else 0.3
            foreign_penalty = min(total_foreign_responses / max(total_responses_with_general, 1), 0.8)
            
            validation_result["authenticity_score"] = max(0.0, (auth_ratio * 0.6 + session_factor * 0.4) - foreign_penalty)
        else:
            validation_result["authenticity_score"] = 1.0
        
        # Determine overall profile completeness
        completed_categories = len([cat for cat in validation_result["category_completeness"].values() if cat["interview_completed"]])
        total_categories_with_data = len(validation_result["category_completeness"])
        
        if completed_categories > 0:
            if completed_categories == total_categories_with_data:
                validation_result["profile_completeness"] = "complete"
            else:
                validation_result["profile_completeness"] = "partially_complete"
        elif has_any_session and total_questions_answered > 0:
            validation_result["profile_completeness"] = "partial_in_progress"
        elif total_responses_with_general > 0:
            validation_result["profile_completeness"] = "partial_data_exists"
        else:
            validation_result["profile_completeness"] = "empty"
        
        validation_result["template_indicators"] = template_indicators
        validation_result["total_detailed_responses"] = total_responses_with_general
        validation_result["total_authenticated_responses"] = total_auth_with_general
        validation_result["total_foreign_responses"] = total_foreign_responses
        
        # MODIFIED validation logic - more permissive but category-aware
        if total_foreign_responses > 0:
            validation_result["valid"] = False
            validation_result["reason"] = "foreign_user_data_detected"
        elif total_responses_with_general > 10 and not has_any_session:
            validation_result["valid"] = False
            validation_result["reason"] = "extensive_data_without_any_sessions"
        elif validation_result["authenticity_score"] < 0.2:
            validation_result["valid"] = False
            validation_result["reason"] = "very_low_authenticity_score"
        
        # Add enhanced diagnostics
        validation_result["diagnostics"] = {
            "has_interview_activity": has_any_session,
            "questions_answered": total_questions_answered,
            "categories_with_data": total_categories_with_data,
            "completed_categories": completed_categories,
            "authentication_percentage": (total_auth_with_general / max(total_responses_with_general, 1)) * 100,
            "foreign_data_percentage": (total_foreign_responses / max(total_responses_with_general, 1)) * 100,
            "profile_usability": "usable" if validation_result["valid"] else "needs_cleanup"
        }
        
        return validation_result
        
    except Exception as e:
        return {
            "valid": False, 
            "reason": "validation_error", 
            "error": str(e)
        }

def load_user_profile(user_id: str = None) -> Dict[str, Any]:
    """Load and validate USER-SPECIFIC profile from Firestore - matches Streamlit pattern with category awareness"""
    try:
        db = get_firestore_client()
        
        if not user_id:
            print("❌ No user_id provided for profile loading")
            return {}
        
        print(f"🔍 Looking for profile for user: {user_id}")
        
        # Try to find profile in multiple locations (same as Streamlit logic)
        profile_locations = [
            {
                "collection": "user_profiles",
                "document": f"{user_id}_profile_structure.json",
                "description": "Primary user_profiles collection"
            },
            {
                "collection": "user_collection", 
                "document": f"{user_id}_profile_structure.json",
                "description": "Fallback user_collection with user prefix"
            },
            {
                "collection": "user_collection",
                "document": "profile_strcuture.json",  # Matches Streamlit typo
                "description": "Streamlit default profile location"
            },
            {
                "collection": "interview_profiles",
                "document": f"{user_id}_profile.json", 
                "description": "Interview-generated profile"
            },
            {
                "collection": f"user_{user_id}",
                "document": "profile_structure.json",
                "description": "User-specific collection"
            }
        ]
        
        raw_profile = None
        profile_source = None
        
        for location in profile_locations:
            try:
                doc_ref = db.collection(location["collection"]).document(location["document"])
                doc = doc_ref.get()
                
                if doc.exists:
                    raw_profile = doc.to_dict()
                    profile_source = f"{location['collection']}/{location['document']}"
                    print(f"✅ Found profile at: {profile_source}")
                    break
                    
            except Exception as e:
                print(f"❌ Error checking {location['description']}: {e}")
                continue
        
        if not raw_profile:
            print(f"❌ No profile found for user: {user_id}")
            return {}
        
        # Validate profile authenticity with enhanced category-aware validation
        validation = validate_profile_authenticity(raw_profile, user_id, db)
        
        print(f"🔍 Profile validation result: {validation.get('valid')} - {validation.get('reason', 'OK')}")
        print(f"🔍 Profile completeness: {validation.get('profile_completeness', 'unknown')}")
        print(f"🔍 Questions answered: {validation.get('total_questions_answered', 0)}")
        print(f"🔍 Authenticity score: {validation.get('authenticity_score', 0.0):.2f}")
        print(f"🔍 Category completeness: {list(validation.get('category_completeness', {}).keys())}")
        
        if validation.get("warnings"):
            print(f"⚠️ Profile warnings: {validation['warnings']}")
        
        # Only reject for serious contamination
        if not validation.get("valid"):
            serious_issues = ["foreign_user_data_detected", "extensive_data_without_any_sessions"]
            if validation.get("reason") in serious_issues:
                print(f"🚨 SERIOUS PROFILE ISSUE for user {user_id}: {validation.get('reason')}")
                return {
                    "error": "contaminated_profile",
                    "user_id": user_id,
                    "validation": validation,
                    "message": f"Profile validation failed: {validation.get('reason')}",
                    "profile_source": profile_source
                }
            else:
                print(f"⚠️ Minor profile issue for user {user_id}: {validation.get('reason')} - allowing with warnings")
        
        # Return profile with validation info (even if partial)
        profile_with_metadata = raw_profile.copy()
        profile_with_metadata["_validation"] = validation
        profile_with_metadata["_source"] = profile_source
        
        return profile_with_metadata
        
    except Exception as e:
        print(f"❌ Error loading user profile for {user_id}: {e}")
        return {}

def search_web(query, max_results=3, max_retries=3, base_delay=1.0):
    """Query DuckDuckGo via DDGS.text(), returning up to max_results items."""
    for attempt in range(1, max_retries + 1):
        try:
            with DDGS() as ddgs:
                return list(islice(ddgs.text(query), max_results))
        except DuckDuckGoSearchException as e:
            msg = str(e)
            if "202" in msg:
                wait = base_delay * (2 ** (attempt - 1))
                print(f"[search_web] Rate‑limited (202). Retry {attempt}/{max_retries} in {wait:.1f}s…")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            print(f"[search_web] Unexpected error: {e}")
            break
    
    print(f"[search_web] Failed to fetch results after {max_retries} attempts.")
    return []

def generate_recommendations(user_profile, user_query, openai_key, category=None):
    """Generate 3 personalized recommendations using user profile and web search - STREAMLIT COMPATIBLE"""
    
    # Enhanced search with category context
    if category:
        search_query = f"{category} {user_query} recommendations 2024"
    else:
        search_query = f"{user_query} recommendations 2024"
    
    search_results = search_web(search_query)
    
    # Category-specific instructions
    category_instructions = ""
    if category:
        category_lower = category.lower()
        
        if category_lower in ["travel", "travel & destinations"]:
            category_instructions = """
            **CATEGORY FOCUS: TRAVEL & DESTINATIONS**
            - Recommend specific destinations, attractions, or travel experiences
            - Include practical travel advice (best time to visit, transportation, accommodations)
            - Consider cultural experiences, local cuisine, historical sites, natural attractions
            - Focus on places to visit, things to do, travel itineraries
            - DO NOT recommend economic plans, political content, or business strategies
            
            **EXAMPLE for Pakistan Travel Query**:
            - "Hunza Valley, Pakistan" - Mountain valley with stunning landscapes
            - "Lahore Food Street" - Culinary travel experience in historic city
            - "Skardu Adventures" - Trekking and mountaineering destination
            """
            
        elif category_lower in ["movies", "movies & tv", "entertainment"]:
            category_instructions = """
            **CATEGORY FOCUS: MOVIES & TV**
            - Recommend specific movies, TV shows, or streaming content
            - Consider genres, directors, actors, themes that match user preferences
            - Include where to watch (streaming platforms) if possible
            - Focus on entertainment content, not travel or other categories
            """
            
        elif category_lower in ["food", "food & dining", "restaurants"]:
            category_instructions = """
            **CATEGORY FOCUS: FOOD & DINING**
            - Recommend specific restaurants, cuisines, or food experiences
            - Include local specialties, popular dishes, dining venues
            - Consider user's location and dietary preferences
            - Focus on food and dining experiences, not travel destinations
            """
            
        else:
            category_instructions = f"""
            **CATEGORY FOCUS: {category.upper()}**
            - Focus recommendations specifically on {category} related content
            - Ensure all suggestions are relevant to the {category} category
            - Do not recommend content from other categories
            """
    
    prompt = f"""
    **Task**: Generate exactly 3 highly personalized {category + ' ' if category else ''}recommendations based on:
    
    {category_instructions}
    
    **User Profile**:
    {json.dumps(user_profile, indent=2)}
    
    **User Query**:
    "{user_query}"
    
    **Web Context** (for reference only):
    {search_results}
    
    **Requirements**:
    1. Each recommendation must directly reference profile details when available
    2. ALL recommendations MUST be relevant to the "{category}" category if specified
    3. Blend the user's core values and preferences from their profile
    4. Only suggest what is asked for - no extra advice
    5. For travel queries, recommend specific destinations, attractions, or experiences
    6. Format as JSON array with each recommendation having:
       - title: string (specific name of place/item/experience)
       - description: string (brief description of what it is)
       - reasons: array of strings (why it matches the user profile)
       - confidence_score: float (0.0-1.0)
    
    **CRITICAL for Travel Category**: 
    If this is a travel recommendation, suggest actual destinations, attractions, restaurants, or travel experiences.
    DO NOT suggest economic plans, political content, or business strategies.
    
    **Output Example for Travel**:
    [
      {{
         "title": "Hunza Valley, Pakistan",
         "description": "Breathtaking mountain valley known for stunning landscapes and rich cultural heritage",
         "reasons": ["Matches your love for natural beauty and cultural exploration", "Perfect for peaceful mountain retreats you prefer"],
         "confidence_score": 0.9
      }},
      {{
         "title": "Lahore Food Street, Pakistan", 
         "description": "Historic food destination offering authentic Pakistani cuisine and cultural immersion",
         "reasons": ["Aligns with your interest in trying traditional foods", "Offers the cultural experiences you enjoy"],
         "confidence_score": 0.85
      }},
      {{
         "title": "Skardu, Pakistan",
         "description": "Adventure destination for trekking and mountaineering with stunning natural scenery",
         "reasons": ["Perfect for your moderate adventure seeking preferences", "Offers the peaceful outdoor experiences you value"],
         "confidence_score": 0.8
      }}
    ]
    
    Generate your response in JSON format only.
    """
    
    # Setting up LLM - same as Streamlit pattern
    client = OpenAI(api_key=openai_key)

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": f"You're a recommendation engine that creates hyper-personalized {category.lower() if category else ''} suggestions. You MUST focus on {category.lower() if category else 'relevant'} content only. Output valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7  
    )
    
    return response.choices[0].message.content

# ROUTE DEFINITIONS - SPECIFIC ROUTES FIRST, PARAMETERIZED ROUTES LAST

@router.get("/profile")
async def get_user_profile(current_user: str = Depends(get_current_user)):
    """Get the current user's profile with category-specific completeness info"""
    try:
        print(f"🔍 Getting profile for user: {current_user}")
        profile = load_user_profile(current_user)
        
        # Handle contaminated profile (only for serious issues)
        if isinstance(profile, dict) and profile.get("error") == "contaminated_profile":
            validation_info = profile.get("validation", {})
            
            if validation_info.get("reason") == "foreign_user_data_detected":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "contaminated_profile",
                        "message": "Profile contains data from other users",
                        "user_id": current_user,
                        "validation": validation_info,
                        "recommended_action": "clear_contaminated_profile_and_restart_interview"
                    }
                )
            elif validation_info.get("reason") == "extensive_data_without_any_sessions":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "suspicious_profile",
                        "message": "Profile has extensive data but no interview sessions",
                        "user_id": current_user,
                        "validation": validation_info,
                        "recommended_action": "start_interview_to_validate_or_clear_profile"
                    }
                )
        
        if not profile:
            # Check interview status
            db = get_firestore_client()
            sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
            sessions = list(sessions_ref.stream())
            
            if not sessions:
                raise HTTPException(
                    status_code=404,
                    detail="No profile found. Please start an interview to begin creating your profile."
                )
            
            # If there are sessions but no profile, suggest continuing
            in_progress_sessions = [s for s in sessions if s.to_dict().get("status") == "in_progress"]
            if in_progress_sessions:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "message": "Interview in progress but no profile generated yet. Continue the interview to build your profile.",
                        "sessions": [{"session_id": s.id, "phase": s.to_dict().get("current_phase"), "category": s.to_dict().get("selected_category")} for s in in_progress_sessions]
                    }
                )
        
        # Return profile with enhanced category information
        clean_profile = {k: v for k, v in profile.items() if not k.startswith('_')}
        validation_summary = profile.get("_validation", {})
        
        response = {
            "success": True,
            "profile": clean_profile,
            "user_id": current_user,
            "profile_type": "user_specific",
            "profile_found": True,
            "profile_completeness": validation_summary.get("profile_completeness", "unknown"),
            "category_completeness": validation_summary.get("category_completeness", {}),
            "validation_summary": {
                "valid": validation_summary.get("valid", True),
                "authenticity_score": validation_summary.get("authenticity_score", 1.0),
                "reason": validation_summary.get("reason"),
                "has_interview_activity": validation_summary.get("has_any_session", False),
                "questions_answered": validation_summary.get("total_questions_answered", 0),
                "total_responses": validation_summary.get("total_detailed_responses", 0),
                "authenticated_responses": validation_summary.get("total_authenticated_responses", 0),
                "completed_phases_by_category": validation_summary.get("completed_phases_by_category", {}),
                "in_progress_phases_by_category": validation_summary.get("in_progress_phases_by_category", {})
            },
            "profile_source": profile.get("_source", "unknown")
        }
        
        # Add enhanced guidance based on category completeness
        category_completeness = validation_summary.get("category_completeness", {})
        completed_categories = [cat for cat, data in category_completeness.items() if data.get("interview_completed")]
        in_progress_categories = [cat for cat, data in category_completeness.items() if data.get("interview_in_progress")]
        available_categories = ["Movies", "Food", "Travel", "Books", "Music", "Fitness"]
        not_started_categories = [cat for cat in available_categories if cat not in category_completeness]
        
        if len(completed_categories) == len(category_completeness) and len(completed_categories) > 0:
            response["message"] = f"Profile complete for {len(completed_categories)} categories: {', '.join(completed_categories)}. You can start interviews for other categories or update existing ones."
        elif len(completed_categories) > 0:
            response["message"] = f"Profile complete for: {', '.join(completed_categories)}. Continue in-progress categories or start new ones."
        elif len(in_progress_categories) > 0:
            response["message"] = f"Interviews in progress for: {', '.join(in_progress_categories)}. Continue these or start new category interviews."
        else:
            response["message"] = "Start category interviews to build your personalized profile."
        
        # Add actionable suggestions
        response["suggestions"] = {
            "completed_categories": completed_categories,
            "in_progress_categories": in_progress_categories,
            "available_to_start": not_started_categories,
            "can_update": completed_categories,
            "should_continue": in_progress_categories
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in get_user_profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load profile: {str(e)}"
        )

@router.get("/profile/category/{category}")
async def get_category_profile_status(
    category: str,
    current_user: str = Depends(get_current_user)
):
    """Get profile status for a specific category"""
    try:
        profile = load_user_profile(current_user)
        
        if not profile:
            return {
                "success": False,
                "user_id": current_user,
                "category": category,
                "has_data": False,
                "message": f"No profile found. Start a {category} interview to begin."
            }
        
        validation_summary = profile.get("_validation", {})
        category_completeness = validation_summary.get("category_completeness", {})
        
        if category in category_completeness:
            category_data = category_completeness[category]
            return {
                "success": True,
                "user_id": current_user,
                "category": category,
                "has_data": category_data.get("has_profile_data", False),
                "interview_completed": category_data.get("interview_completed", False),
                "interview_in_progress": category_data.get("interview_in_progress", False),
                "data_authenticity": category_data.get("data_authenticity", "unknown"),
                "detailed_responses": category_data.get("detailed_responses", 0),
                "authenticated_responses": category_data.get("authenticated_responses", 0),
                "status": "completed" if category_data.get("interview_completed") else "in_progress" if category_data.get("interview_in_progress") else "has_data",
                "message": f"{category} profile status: {category_data.get('data_authenticity', 'unknown')}"
            }
        else:
            return {
                "success": True,
                "user_id": current_user,
                "category": category,
                "has_data": False,
                "interview_completed": False,
                "interview_in_progress": False,
                "status": "not_started",
                "message": f"No {category} profile data found. Start a {category} interview to begin building this section."
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get category profile status: {str(e)}"
        )

@router.post("/restart/{category}")
async def restart_category_interview(
    category: str,
    current_user: str = Depends(get_current_user)
):
    """Restart interview for a specific category"""
    try:
        db = get_firestore_client()
        
        # Find existing sessions for this category
        sessions_query = db.collection("interview_sessions")\
            .where("user_id", "==", current_user)\
            .where("selected_category", "==", category)
        
        existing_sessions = list(sessions_query.stream())
        
        # Archive all existing sessions for this category
        for session in existing_sessions:
            session.reference.update({
                "status": "archived",
                "archived_at": datetime.utcnow(),
                "archived_reason": "category_restart"
            })
        
        # Create new session
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "user_id": current_user,
            "selected_category": category,
            "status": "in_progress",
            "current_tier": 1,
            "current_phase": "general",
            "questions_answered": 0,
            "total_tiers": 3,
            "is_complete": False,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "user_specific": True,
            "restart_count": len(existing_sessions)
        }
        
        # Save new session
        db.collection("interview_sessions").document(session_id).set(session_data)
        
        return {
            "success": True,
            "message": f"Restarted {category} interview",
            "session_id": session_id,
            "user_id": current_user,
            "category": category,
            "archived_sessions": len(existing_sessions),
            "status": "in_progress"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restart {category} interview: {str(e)}"
        )

@router.get("/categories")
async def get_recommendation_categories():
    """Get available recommendation categories"""
    categories = [
        {
            "id": "movies",
            "name": "Movies & TV",
            "description": "Movie and TV show recommendations",
            "questions_file": "moviesAndTV_tiered_questions.json"
        },
        {
            "id": "food",
            "name": "Food & Dining",
            "description": "Restaurant and food recommendations",
            "questions_file": "foodAndDining_tiered_questions.json"
        },
        {
            "id": "travel",
            "name": "Travel",
            "description": "Travel destination recommendations",
            "questions_file": "travel_tiered_questions.json"
        },
        {
            "id": "books",
            "name": "Books & Reading",
            "description": "Book recommendations",
            "questions_file": "books_tiered_questions.json"
        },
        {
            "id": "music",
            "name": "Music",
            "description": "Music and artist recommendations",
            "questions_file": "music_tiered_questions.json"
        },
        {
            "id": "fitness",
            "name": "Fitness & Wellness",
            "description": "Fitness and wellness recommendations",
            "questions_file": "fitness_tiered_questions.json"
        }
    ]
    
    return {
        "categories": categories,
        "default_category": "movies"
    }

@router.post("/generate", response_model=RecommendationResponse)
async def generate_user_recommendations(
    request: RecommendationRequest,
    current_user: str = Depends(get_current_user)
):
    """Generate recommendations using the same logic as Streamlit but enhanced for FastAPI"""
    try:
        start_time = datetime.utcnow()
        settings = get_settings()
        db = get_firestore_client()
        
        print(f"🚀 Generating recommendations for user: {current_user}")
        print(f"📝 Query: {request.query}")
        print(f"🏷️ Category: {request.category}")
        
        # Load profile (same as Streamlit)
        user_profile = load_user_profile(current_user)
        
        # Handle serious contamination only
        if isinstance(user_profile, dict) and user_profile.get("error") == "contaminated_profile":
            validation = user_profile.get("validation", {})
            if validation.get("reason") in ["foreign_user_data_detected", "extensive_data_without_any_sessions"]:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "contaminated_profile",
                        "message": "Cannot generate recommendations with contaminated profile data",
                        "recommended_action": "clear_profile_and_start_interview"
                    }
                )
        
        # If no profile, check if we should allow basic recommendations (same as Streamlit)
        if not user_profile:
            print("⚠️ No profile found - checking interview status")
            
            # Check if user has any interview activity
            sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
            sessions = list(sessions_ref.stream())
            
            if not sessions:
                # No interview started - create minimal profile for basic recommendations
                print("📝 No interview sessions - creating basic profile for general recommendations")
                user_profile = {
                    "user_id": current_user,
                    "generalprofile": {
                        "corePreferences": {
                            "note": f"Basic profile - complete interview for personalized {request.category or 'recommendations'}"
                        }
                    },
                    "profile_completeness": "empty"
                }
            else:
                # Has interview activity but no profile - this shouldn't happen
                raise HTTPException(
                    status_code=404,
                    detail="Interview sessions found but no profile generated. Please contact support."
                )
        
        # Clean profile for AI processing (remove metadata)
        clean_profile = {k: v for k, v in user_profile.items() if not k.startswith('_')}
        
        # Get profile completeness info
        validation_summary = user_profile.get("_validation", {})
        profile_completeness = validation_summary.get("profile_completeness", "unknown")
        questions_answered = validation_summary.get("total_questions_answered", 0)
        category_completeness = validation_summary.get("category_completeness", {})
        
        print(f"📊 Profile completeness: {profile_completeness}")
        print(f"📝 Questions answered: {questions_answered}")
        print(f"🏷️ Category completeness: {list(category_completeness.keys())}")
        
        # Check if the requested category has data
        category_has_data = False
        category_status = "not_started"
        if request.category and request.category in category_completeness:
            category_data = category_completeness[request.category]
            category_has_data = category_data.get("has_profile_data", False)
            if category_data.get("interview_completed"):
                category_status = "completed"
            elif category_data.get("interview_in_progress"):
                category_status = "in_progress"
            else:
                category_status = "has_data"
        
        print(f"🎯 Category {request.category} status: {category_status}, has_data: {category_has_data}")
        
        # Generate category-aware recommendations
        recs_json = generate_recommendations(
            clean_profile, 
            request.query, 
            settings.OPENAI_API_KEY,
            request.category  # Add category parameter
        )
        
        try:
            recs = json.loads(recs_json)
            
            # Normalize to list (same as Streamlit)
            if isinstance(recs, dict):
                if "recommendations" in recs and isinstance(recs["recommendations"], list):
                    recs = recs["recommendations"]
                else:
                    recs = [recs]
            
            if not isinstance(recs, list):
                raise HTTPException(
                    status_code=500,
                    detail="Unexpected response format – expected a list of recommendations."
                )
            
            # Validate category relevance for travel
            if request.category and request.category.lower() == "travel":
                travel_keywords = ["destination", "place", "visit", "travel", "city", "country", "attraction", "trip", "valley", "mountain", "beach", "street", "food", "culture", "heritage", "adventure", "pakistan", "hunza", "lahore", "skardu"]
                
                for i, rec in enumerate(recs):
                    title_and_desc = (rec.get('title', '') + ' ' + rec.get('description', '')).lower()
                    if not any(keyword in title_and_desc for keyword in travel_keywords):
                        print(f"⚠️ Recommendation {i+1} '{rec.get('title')}' may not be travel-related")
                        print(f"🔍 Content: {title_and_desc[:100]}...")
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Add profile completion guidance based on category status
            for rec in recs:
                if "reasons" not in rec:
                    rec["reasons"] = []
                
                if request.category and category_status == "not_started":
                    rec["reasons"].append(f"Start a {request.category} interview for more personalized recommendations")
                elif request.category and category_status == "in_progress":
                    rec["reasons"].append(f"Continue your {request.category} interview for better personalization")
                elif profile_completeness == "empty":
                    rec["reasons"].append("Start an interview to get more personalized recommendations")
                elif profile_completeness in ["partial_in_progress", "partial_data_exists"]:
                    rec["reasons"].append("Complete more interview questions for better personalization")
            
            # Generate session ID for conversation tracking
            session_id = str(uuid.uuid4())
            
            # Save conversation messages (like Streamlit chat)
            save_conversation_message(
                current_user, 
                session_id, 
                "user", 
                f"What would you like {request.category.lower() if request.category else ''} recommendations for? {request.query}", 
                "recommendation",
                f"{request.category or 'General'} Recommendation Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
            # Prepare recommendation data for database
            recommendation_data = {
                "user_id": current_user,
                "query": request.query,
                "category": request.category,
                "recommendations": recs,
                "processing_time_ms": int(processing_time),
                "search_context": search_web(f"{request.category} {request.query} recommendations 2024" if request.category else f"{request.query} recommendations 2024"),
                "session_id": session_id,
                "profile_version": clean_profile.get("version", "1.0"),
                "profile_completeness": profile_completeness,
                "category_status": category_status,
                "category_has_data": category_has_data,
                "questions_answered": questions_answered,
                "user_specific": True,
                "generation_method": "streamlit_compatible"
            }
            
            # Save to database
            recommendation_id = save_recommendation_to_db(recommendation_data, db)
            
            if not recommendation_id:
                print("⚠️ Warning: Failed to save recommendation to database")
                recommendation_id = str(uuid.uuid4())  # Fallback
            
            # Format recommendations for conversation history (like Streamlit display)
            recs_text = f"Here are your {request.category.lower() if request.category else ''} recommendations:\n\n"
            
            for i, rec in enumerate(recs, 1):
                title = rec.get("title", "<no title>")
                description = rec.get("description", rec.get("reason", "<no description>"))
                reasons = rec.get("reasons", [])
                
                recs_text += f"**{i}. {title}**\n"
                recs_text += f"{description}\n"
                if reasons:
                    for reason in reasons:
                        recs_text += f"• {reason}\n"
                recs_text += "\n"
            
            # Save recommendations to conversation history
            save_conversation_message(
                current_user, 
                session_id, 
                "assistant", 
                recs_text, 
                "recommendation"
            )
            
            # Convert to RecommendationItem objects
            recommendation_items = []
            for rec in recs:
                # Use confidence score from AI or default based on profile completeness
                base_confidence = 0.6 if profile_completeness == "empty" or category_status == "not_started" else 0.8
                confidence_score = rec.get('confidence_score', base_confidence)
                
                recommendation_items.append(RecommendationItem(
                    title=rec.get('title', 'Recommendation'),
                    description=rec.get('description', rec.get('reason', '')),
                    reasons=rec.get('reasons', []),
                    category=request.category,
                    confidence_score=confidence_score
                ))
            
            return RecommendationResponse(
                recommendation_id=recommendation_id,
                recommendations=recommendation_items,
                query=request.query,
                category=request.category,
                user_id=current_user,
                generated_at=datetime.utcnow(),
                processing_time_ms=int(processing_time)
            )
            
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse recommendations: {str(e)}"
            print(f"❌ JSON parsing error: {error_msg}")
            print(f"🔍 Raw AI response: {recs_json[:500]}...")
            
            # Save error to conversation history
            save_conversation_message(
                current_user, 
                str(uuid.uuid4()), 
                "assistant", 
                f"Sorry, I encountered an error generating {request.category or ''} recommendations: {error_msg}", 
                "recommendation"
            )
            
            raise HTTPException(
                status_code=500,
                detail=error_msg
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error generating recommendations for user {current_user}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate {request.category or ''} recommendations: {str(e)}"
        )

@router.get("/history")
async def get_recommendation_history(
    current_user: str = Depends(get_current_user),
    limit: int = Query(20, description="Number of recommendations to return"),
    offset: int = Query(0, description="Number of recommendations to skip"),
    category: Optional[str] = Query(None, description="Filter by category")
):
    """Get recommendation history for the user with enhanced filtering"""
    try:
        db = get_firestore_client()
        
        # Simplified query to avoid index issues
        query = db.collection("user_recommendations").document(current_user).collection("recommendations")
        query = query.where("is_active", "==", True)
        query = query.limit(limit).offset(offset)
        
        recommendations = list(query.stream())
        
        # Filter and sort in Python
        filtered_recs = []
        for rec in recommendations:
            rec_data = rec.to_dict()
            
            # Apply category filter
            if category and rec_data.get("category") != category:
                continue
            
            filtered_recs.append(rec_data)
        
        # Sort by generated_at descending
        filtered_recs.sort(key=lambda x: x.get("generated_at", datetime.min), reverse=True)
        
        # Format response
        history = []
        for rec_data in filtered_recs:
            history.append({
                "recommendation_id": rec_data["recommendation_id"],
                "query": rec_data["query"],
                "category": rec_data.get("category"),
                "recommendations_count": len(rec_data.get("recommendations", [])),
                "generated_at": rec_data["generated_at"],
                "view_count": rec_data.get("view_count", 0),
                "feedback_count": rec_data.get("feedback_count", 0),
                "session_id": rec_data.get("session_id"),
                "processing_time_ms": rec_data.get("processing_time_ms"),
                "profile_completeness": rec_data.get("profile_completeness", "unknown"),
                "category_status": rec_data.get("category_status", "unknown"),
                "generation_method": rec_data.get("generation_method", "unknown")
            })
        
        return {
            "success": True,
            "history": history,
            "total_count": len(history),
            "user_id": current_user,
            "filters": {
                "category": category,
                "limit": limit,
                "offset": offset
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recommendation history: {str(e)}"
        )

@router.post("/{recommendation_id}/feedback")
async def submit_recommendation_feedback(
    recommendation_id: str,
    feedback: RecommendationFeedback,
    current_user: str = Depends(get_current_user)
):
    """Submit feedback for a recommendation"""
    try:
        db = get_firestore_client()
        
        # Verify recommendation exists and belongs to user
        rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
        if not rec_doc.exists:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        # Save feedback
        feedback_data = {
            "feedback_type": feedback.feedback_type,
            "rating": feedback.rating,
            "comment": feedback.comment,
            "clicked_items": feedback.clicked_items
        }
        
        feedback_id = save_recommendation_feedback(recommendation_id, current_user, feedback_data, db)
        
        if not feedback_id:
            raise HTTPException(status_code=500, detail="Failed to save feedback")
        
        return {
            "success": True,
            "message": "Feedback submitted successfully",
            "feedback_id": feedback_id,
            "recommendation_id": recommendation_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit feedback: {str(e)}"
        )

# IMPORTANT: Put parameterized routes LAST to avoid route conflicts
@router.get("/{recommendation_id}")
async def get_recommendation_details(
    recommendation_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get detailed information about a specific recommendation"""
    try:
        db = get_firestore_client()
        
        # Get recommendation details
        rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
        if not rec_doc.exists:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        rec_data = rec_doc.to_dict()
        
        # Increment view count
        current_views = rec_data.get("view_count", 0)
        rec_doc.reference.update({
            "view_count": current_views + 1,
            "last_viewed": datetime.utcnow()
        })
        
        return {
            "success": True,
            "recommendation": {
                "recommendation_id": rec_data["recommendation_id"],
                "query": rec_data["query"],
                "category": rec_data.get("category"),
                "recommendations": rec_data["recommendations"],
                "generated_at": rec_data["generated_at"],
                "processing_time_ms": rec_data.get("processing_time_ms"),
                "view_count": current_views + 1,
                "search_context": rec_data.get("search_context", []),
                "profile_completeness": rec_data.get("profile_completeness", "unknown"),
                "category_status": rec_data.get("category_status", "unknown"),
                "questions_answered": rec_data.get("questions_answered", 0),
                "generation_method": rec_data.get("generation_method", "unknown")
            },
            "user_id": current_user
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recommendation details: {str(e)}"
        )# app/routers/recommendations.py - Complete Enhanced with Category Management

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
from openai import OpenAI
from duckduckgo_search import DDGS 
from duckduckgo_search.exceptions import DuckDuckGoSearchException
from itertools import islice
import time
import uuid
from datetime import datetime, timedelta

from app.core.security import get_current_user
from app.core.firebase import get_firestore_client
from app.core.config import get_settings
from app.routers.conversations import save_conversation_message

router = APIRouter()

# Enhanced Pydantic models
class RecommendationRequest(BaseModel):
    query: str
    category: Optional[str] = None
    user_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class RecommendationItem(BaseModel):
    title: str
    description: Optional[str] = None
    reasons: List[str] = []
    category: Optional[str] = None
    confidence_score: Optional[float] = None
    external_links: Optional[List[str]] = None

class RecommendationResponse(BaseModel):
    recommendation_id: str
    recommendations: List[RecommendationItem]
    query: str
    category: Optional[str] = None
    user_id: str
    generated_at: datetime
    processing_time_ms: Optional[int] = None

class RecommendationFeedback(BaseModel):
    recommendation_id: str
    feedback_type: str  # 'like', 'dislike', 'not_relevant', 'helpful'
    rating: Optional[int] = None  # 1-5 stars
    comment: Optional[str] = None
    clicked_items: List[str] = []

# Database helper functions
def save_recommendation_to_db(recommendation_data: Dict[str, Any], db) -> str:
    """Save recommendation to database and return recommendation_id"""
    try:
        recommendation_id = str(uuid.uuid4())
        
        # Prepare data for database
        db_data = {
            "recommendation_id": recommendation_id,
            "user_id": recommendation_data["user_id"],
            "query": recommendation_data["query"],
            "category": recommendation_data.get("category"),
            "recommendations": recommendation_data["recommendations"],
            "generated_at": datetime.utcnow(),
            "processing_time_ms": recommendation_data.get("processing_time_ms"),
            "search_context": recommendation_data.get("search_context", []),
            "profile_version": recommendation_data.get("profile_version"),
            "profile_completeness": recommendation_data.get("profile_completeness"),
            "questions_answered": recommendation_data.get("questions_answered", 0),
            "session_id": recommendation_data.get("session_id"),
            "generation_method": recommendation_data.get("generation_method"),
            "is_active": True,
            "view_count": 0,
            "feedback_count": 0
        }
        
        # Save to user-specific collection
        db.collection("user_recommendations").document(recommendation_data["user_id"]).collection("recommendations").document(recommendation_id).set(db_data)
        
        # Also save to recommendation history for analytics
        history_data = {
            "recommendation_id": recommendation_id,
            "user_id": recommendation_data["user_id"],
            "query": recommendation_data["query"],
            "category": recommendation_data.get("category"),
            "recommendations_count": len(recommendation_data["recommendations"]),
            "profile_completeness": recommendation_data.get("profile_completeness"),
            "created_at": datetime.utcnow(),
            "is_bookmarked": False,
            "tags": []
        }
        
        db.collection("recommendation_history").document(recommendation_id).set(history_data)
        
        return recommendation_id
        
    except Exception as e:
        print(f"Error saving recommendation: {e}")
        return None

def save_recommendation_feedback(recommendation_id: str, user_id: str, feedback_data: Dict[str, Any], db):
    """Save user feedback for a recommendation"""
    try:
        feedback_id = str(uuid.uuid4())
        
        feedback_doc = {
            "feedback_id": feedback_id,
            "recommendation_id": recommendation_id,
            "user_id": user_id,
            "feedback_type": feedback_data["feedback_type"],
            "rating": feedback_data.get("rating"),
            "comment": feedback_data.get("comment"),
            "clicked_items": feedback_data.get("clicked_items", []),
            "created_at": datetime.utcnow()
        }
        
        # Save feedback
        db.collection("recommendation_feedback").document(feedback_id).set(feedback_doc)
        
        # Update recommendation with feedback count
        rec_ref = db.collection("user_recommendations").document(user_id).collection("recommendations").document(recommendation_id)
        rec_doc = rec_ref.get()
        
        if rec_doc.exists:
            current_feedback_count = rec_doc.to_dict().get("feedback_count", 0)
            rec_ref.update({"feedback_count": current_feedback_count + 1})
        
        return feedback_id
        
    except Exception as e:
        print(f"Error saving feedback: {e}")
        return None

# ENHANCED Category-Aware Profile validation and loading functions
def validate_profile_authenticity(profile_data: Dict[str, Any], user_id: str, db) -> Dict[str, Any]:
    """Enhanced validation that's category-aware and allows partial profiles"""
    
    if not profile_data or not user_id:
        return {"valid": False, "reason": "empty_profile_or_user"}
    
    validation_result = {
        "valid": True,
        "warnings": [],
        "user_id": user_id,
        "profile_sections": {},
        "authenticity_score": 1.0,
        "template_indicators": [],
        "profile_completeness": "partial",
        "category_completeness": {}  # NEW: Track completeness per category
    }
    
    try:
        # Check interview sessions for this user (grouped by category)
        interview_sessions = db.collection("interview_sessions").where("user_id", "==", user_id).stream()
        
        completed_phases_by_category = {}
        in_progress_phases_by_category = {}
        session_data = {}
        total_questions_answered = 0
        has_any_session = False
        
        for session in interview_sessions:
            has_any_session = True
            session_dict = session.to_dict()
            session_data[session.id] = session_dict
            
            category = session_dict.get("selected_category", "unknown")
            phase = session_dict.get("current_phase", "general")
            
            if category not in completed_phases_by_category:
                completed_phases_by_category[category] = set()
            if category not in in_progress_phases_by_category:
                in_progress_phases_by_category[category] = set()
            
            if session_dict.get("status") == "completed":
                completed_phases_by_category[category].add(phase)
                total_questions_answered += session_dict.get("questions_answered", 0)
            elif session_dict.get("status") == "in_progress":
                in_progress_phases_by_category[category].add(phase)
                total_questions_answered += session_dict.get("questions_answered", 0)
        
        # Convert sets to lists for JSON serialization
        completed_phases_by_category = {k: list(v) for k, v in completed_phases_by_category.items()}
        in_progress_phases_by_category = {k: list(v) for k, v in in_progress_phases_by_category.items()}
        
        validation_result["completed_phases_by_category"] = completed_phases_by_category
        validation_result["in_progress_phases_by_category"] = in_progress_phases_by_category
        validation_result["total_questions_answered"] = total_questions_answered
        validation_result["has_any_session"] = has_any_session
        validation_result["session_data"] = session_data
        
        # Analyze profile sections with category awareness
        profile_sections = profile_data.get("recommendationProfiles", {})
        general_profile = profile_data.get("generalprofile", {})
        
        total_detailed_responses = 0
        total_authenticated_responses = 0
        total_foreign_responses = 0
        template_indicators = []
        
        # Map profile section names to categories
        section_to_category = {
            "moviesandtv": "Movies",
            "movies": "Movies", 
            "travel": "Travel",
            "food": "Food",
            "foodanddining": "Food",
            "books": "Books",
            "music": "Music",
            "fitness": "Fitness"
        }
        
        # Check each recommendation profile section
        for section_name, section_data in profile_sections.items():
            section_lower = section_name.lower()
            mapped_category = section_to_category.get(section_lower, section_name)
            
            section_validation = {
                "has_data": bool(section_data),
                "mapped_category": mapped_category,
                "has_session_for_category": mapped_category in completed_phases_by_category or mapped_category in in_progress_phases_by_category,
                "interview_completed_for_category": mapped_category in completed_phases_by_category and len(completed_phases_by_category[mapped_category]) > 0,
                "interview_in_progress_for_category": mapped_category in in_progress_phases_by_category and len(in_progress_phases_by_category[mapped_category]) > 0,
                "data_authenticity": "unknown",
                "detailed_response_count": 0,
                "authenticated_response_count": 0,
                "foreign_response_count": 0
            }
            
            if section_data and isinstance(section_data, dict):
                def analyze_responses(data, path=""):
                    nonlocal total_detailed_responses, total_authenticated_responses, total_foreign_responses
                    
                    if isinstance(data, dict):
                        for key, value in data.items():
                            current_path = f"{path}.{key}" if path else key
                            
                            if isinstance(value, dict) and "value" in value:
                                response_value = value.get("value", "")
                                if isinstance(response_value, str) and len(response_value.strip()) > 10:
                                    section_validation["detailed_response_count"] += 1
                                    total_detailed_responses += 1
                                    
                                    # Check authentication markers
                                    if "user_id" in value and "updated_at" in value:
                                        if value.get("user_id") == user_id:
                                            section_validation["authenticated_response_count"] += 1
                                            total_authenticated_responses += 1
                                        else:
                                            section_validation["foreign_response_count"] += 1
                                            total_foreign_responses += 1
                                            template_indicators.append(
                                                f"Foreign user data: {section_name}.{current_path} (from {value.get('user_id')})"
                                            )
                                
                                # Recursively check nested structures
                                if isinstance(value, dict):
                                    analyze_responses(value, current_path)
                
                analyze_responses(section_data)
                
                # Enhanced authenticity determination with category awareness
                if section_validation["foreign_response_count"] > 0:
                    section_validation["data_authenticity"] = "foreign_user_data"
                elif section_validation["detailed_response_count"] > 0:
                    if section_validation["interview_completed_for_category"]:
                        section_validation["data_authenticity"] = "authentic"
                    elif section_validation["interview_in_progress_for_category"]:
                        section_validation["data_authenticity"] = "in_progress_authentic"
                    elif section_validation["authenticated_response_count"] > 0:
                        section_validation["data_authenticity"] = "authenticated_but_no_session"
                    else:
                        # Check if user has ANY interview activity
                        if has_any_session:
                            section_validation["data_authenticity"] = "possibly_legitimate"
                        else:
                            section_validation["data_authenticity"] = "suspicious_no_sessions"
                            template_indicators.append(
                                f"Detailed data without any interview sessions: {section_name}"
                            )
                else:
                    section_validation["data_authenticity"] = "minimal_data"
            
            validation_result["profile_sections"][section_name] = section_validation
            
            # Track category completeness
            if mapped_category not in validation_result["category_completeness"]:
                validation_result["category_completeness"][mapped_category] = {
                    "has_profile_data": section_validation["has_data"],
                    "has_interview_sessions": section_validation["has_session_for_category"],
                    "interview_completed": section_validation["interview_completed_for_category"],
                    "interview_in_progress": section_validation["interview_in_progress_for_category"],
                    "data_authenticity": section_validation["data_authenticity"],
                    "detailed_responses": section_validation["detailed_response_count"],
                    "authenticated_responses": section_validation["authenticated_response_count"]
                }
        
        # Check general profile
        general_detailed_responses = 0
        general_authenticated_responses = 0
        
        def check_general_profile(data, path="generalprofile"):
            nonlocal general_detailed_responses, general_authenticated_responses
            
            if isinstance(data, dict):
                for key, value in data.items():
                    current_path = f"{path}.{key}"
                    
                    if isinstance(value, dict):
                        if "value" in value and isinstance(value["value"], str) and len(value["value"].strip()) > 10:
                            general_detailed_responses += 1
                            if "user_id" in value and value.get("user_id") == user_id:
                                general_authenticated_responses += 1
                        else:
                            check_general_profile(value, current_path)
        
        check_general_profile(general_profile)
        
        # Calculate totals
        total_responses_with_general = total_detailed_responses + general_detailed_responses
        total_auth_with_general = total_authenticated_responses + general_authenticated_responses
        
        # Calculate authenticity score (more lenient)
        if total_responses_with_general > 0:
            auth_ratio = total_auth_with_general / total_responses_with_general
            session_factor = 1.0 if has_any_session else 0.3
            foreign_penalty = min(total_foreign_responses / max(total_responses_with_general, 1), 0.8)
            
            validation_result["authenticity_score"] = max(0.0, (auth_ratio * 0.6 + session_factor * 0.4) - foreign_penalty)
        else:
            validation_result["authenticity_score"] = 1.0
        
        # Determine overall profile completeness
        completed_categories = len([cat for cat in validation_result["category_completeness"].values() if cat["interview_completed"]])
        total_categories_with_data = len(validation_result["category_completeness"])
        
        if completed_categories > 0:
            if completed_categories == total_categories_with_data:
                validation_result["profile_completeness"] = "complete"
            else:
                validation_result["profile_completeness"] = "partially_complete"
        elif has_any_session and total_questions_answered > 0:
            validation_result["profile_completeness"] = "partial_in_progress"
        elif total_responses_with_general > 0:
            validation_result["profile_completeness"] = "partial_data_exists"
        else:
            validation_result["profile_completeness"] = "empty"
        
        validation_result["template_indicators"] = template_indicators
        validation_result["total_detailed_responses"] = total_responses_with_general
        validation_result["total_authenticated_responses"] = total_auth_with_general
        validation_result["total_foreign_responses"] = total_foreign_responses
        
        # MODIFIED validation logic - more permissive but category-aware
        if total_foreign_responses > 0:
            validation_result["valid"] = False
            validation_result["reason"] = "foreign_user_data_detected"
        elif total_responses_with_general > 10 and not has_any_session:
            validation_result["valid"] = False
            validation_result["reason"] = "extensive_data_without_any_sessions"
        elif validation_result["authenticity_score"] < 0.2:
            validation_result["valid"] = False
            validation_result["reason"] = "very_low_authenticity_score"
        
        # Add enhanced diagnostics
        validation_result["diagnostics"] = {
            "has_interview_activity": has_any_session,
            "questions_answered": total_questions_answered,
            "categories_with_data": total_categories_with_data,
            "completed_categories": completed_categories,
            "authentication_percentage": (total_auth_with_general / max(total_responses_with_general, 1)) * 100,
            "foreign_data_percentage": (total_foreign_responses / max(total_responses_with_general, 1)) * 100,
            "profile_usability": "usable" if validation_result["valid"] else "needs_cleanup"
        }
        
        return validation_result
        
    except Exception as e:
        return {
            "valid": False, 
            "reason": "validation_error", 
            "error": str(e)
        }

def load_user_profile(user_id: str = None) -> Dict[str, Any]:
    """Load and validate USER-SPECIFIC profile from Firestore - matches Streamlit pattern with category awareness"""
    try:
        db = get_firestore_client()
        
        if not user_id:
            print("❌ No user_id provided for profile loading")
            return {}
        
        print(f"🔍 Looking for profile for user: {user_id}")
        
        # Try to find profile in multiple locations (same as Streamlit logic)
        profile_locations = [
            {
                "collection": "user_profiles",
                "document": f"{user_id}_profile_structure.json",
                "description": "Primary user_profiles collection"
            },
            {
                "collection": "user_collection", 
                "document": f"{user_id}_profile_structure.json",
                "description": "Fallback user_collection with user prefix"
            },
            {
                "collection": "user_collection",
                "document": "profile_strcuture.json",  # Matches Streamlit typo
                "description": "Streamlit default profile location"
            },
            {
                "collection": "interview_profiles",
                "document": f"{user_id}_profile.json", 
                "description": "Interview-generated profile"
            },
            {
                "collection": f"user_{user_id}",
                "document": "profile_structure.json",
                "description": "User-specific collection"
            }
        ]
        
        raw_profile = None
        profile_source = None
        
        for location in profile_locations:
            try:
                doc_ref = db.collection(location["collection"]).document(location["document"])
                doc = doc_ref.get()
                
                if doc.exists:
                    raw_profile = doc.to_dict()
                    profile_source = f"{location['collection']}/{location['document']}"
                    print(f"✅ Found profile at: {profile_source}")
                    break
                    
            except Exception as e:
                print(f"❌ Error checking {location['description']}: {e}")
                continue
        
        if not raw_profile:
            print(f"❌ No profile found for user: {user_id}")
            return {}
        
        # Validate profile authenticity with enhanced category-aware validation
        validation = validate_profile_authenticity(raw_profile, user_id, db)
        
        print(f"🔍 Profile validation result: {validation.get('valid')} - {validation.get('reason', 'OK')}")
        print(f"🔍 Profile completeness: {validation.get('profile_completeness', 'unknown')}")
        print(f"🔍 Questions answered: {validation.get('total_questions_answered', 0)}")
        print(f"🔍 Authenticity score: {validation.get('authenticity_score', 0.0):.2f}")
        print(f"🔍 Category completeness: {list(validation.get('category_completeness', {}).keys())}")
        
        if validation.get("warnings"):
            print(f"⚠️ Profile warnings: {validation['warnings']}")
        
        # Only reject for serious contamination
        if not validation.get("valid"):
            serious_issues = ["foreign_user_data_detected", "extensive_data_without_any_sessions"]
            if validation.get("reason") in serious_issues:
                print(f"🚨 SERIOUS PROFILE ISSUE for user {user_id}: {validation.get('reason')}")
                return {
                    "error": "contaminated_profile",
                    "user_id": user_id,
                    "validation": validation,
                    "message": f"Profile validation failed: {validation.get('reason')}",
                    "profile_source": profile_source
                }
            else:
                print(f"⚠️ Minor profile issue for user {user_id}: {validation.get('reason')} - allowing with warnings")
        
        # Return profile with validation info (even if partial)
        profile_with_metadata = raw_profile.copy()
        profile_with_metadata["_validation"] = validation
        profile_with_metadata["_source"] = profile_source
        
        return profile_with_metadata
        
    except Exception as e:
        print(f"❌ Error loading user profile for {user_id}: {e}")
        return {}

def search_web(query, max_results=3, max_retries=3, base_delay=1.0):
    """Query DuckDuckGo via DDGS.text(), returning up to max_results items."""
    for attempt in range(1, max_retries + 1):
        try:
            with DDGS() as ddgs:
                return list(islice(ddgs.text(query), max_results))
        except DuckDuckGoSearchException as e:
            msg = str(e)
            if "202" in msg:
                wait = base_delay * (2 ** (attempt - 1))
                print(f"[search_web] Rate‑limited (202). Retry {attempt}/{max_retries} in {wait:.1f}s…")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            print(f"[search_web] Unexpected error: {e}")
            break
    
    print(f"[search_web] Failed to fetch results after {max_retries} attempts.")
    return []

def generate_recommendations(user_profile, user_query, openai_key, category=None):
    """Generate 3 personalized recommendations using user profile and web search - STREAMLIT COMPATIBLE"""
    
    # Enhanced search with category context
    if category:
        search_query = f"{category} {user_query} recommendations 2024"
    else:
        search_query = f"{user_query} recommendations 2024"
    
    search_results = search_web(search_query)
    
    # Category-specific instructions
    category_instructions = ""
    if category:
        category_lower = category.lower()
        
        if category_lower in ["travel", "travel & destinations"]:
            category_instructions = """
            **CATEGORY FOCUS: TRAVEL & DESTINATIONS**
            - Recommend specific destinations, attractions, or travel experiences
            - Include practical travel advice (best time to visit, transportation, accommodations)
            - Consider cultural experiences, local cuisine, historical sites, natural attractions
            - Focus on places to visit, things to do, travel itineraries
            - DO NOT recommend economic plans, political content, or business strategies
            
            **EXAMPLE for Pakistan Travel Query**:
            - "Hunza Valley, Pakistan" - Mountain valley with stunning landscapes
            - "Lahore Food Street" - Culinary travel experience in historic city
            - "Skardu Adventures" - Trekking and mountaineering destination
            """
            
        elif category_lower in ["movies", "movies & tv", "entertainment"]:
            category_instructions = """
            **CATEGORY FOCUS: MOVIES & TV**
            - Recommend specific movies, TV shows, or streaming content
            - Consider genres, directors, actors, themes that match user preferences
            - Include where to watch (streaming platforms) if possible
            - Focus on entertainment content, not travel or other categories
            """
            
        elif category_lower in ["food", "food & dining", "restaurants"]:
            category_instructions = """
            **CATEGORY FOCUS: FOOD & DINING**
            - Recommend specific restaurants, cuisines, or food experiences
            - Include local specialties, popular dishes, dining venues
            - Consider user's location and dietary preferences
            - Focus on food and dining experiences, not travel destinations
            """
            
        else:
            category_instructions = f"""
            **CATEGORY FOCUS: {category.upper()}**
            - Focus recommendations specifically on {category} related content
            - Ensure all suggestions are relevant to the {category} category
            - Do not recommend content from other categories
            """
    
    prompt = f"""
    **Task**: Generate exactly 3 highly personalized {category + ' ' if category else ''}recommendations based on:
    
    {category_instructions}
    
    **User Profile**:
    {json.dumps(user_profile, indent=2)}
    
    **User Query**:
    "{user_query}"
    
    **Web Context** (for reference only):
    {search_results}
    
    **Requirements**:
    1. Each recommendation must directly reference profile details when available
    2. ALL recommendations MUST be relevant to the "{category}" category if specified
    3. Blend the user's core values and preferences from their profile
    4. Only suggest what is asked for - no extra advice
    5. For travel queries, recommend specific destinations, attractions, or experiences
    6. Format as JSON array with each recommendation having:
       - title: string (specific name of place/item/experience)
       - description: string (brief description of what it is)
       - reasons: array of strings (why it matches the user profile)
       - confidence_score: float (0.0-1.0)
    
    **CRITICAL for Travel Category**: 
    If this is a travel recommendation, suggest actual destinations, attractions, restaurants, or travel experiences.
    DO NOT suggest economic plans, political content, or business strategies.
    
    **Output Example for Travel**:
    [
      {{
         "title": "Hunza Valley, Pakistan",
         "description": "Breathtaking mountain valley known for stunning landscapes and rich cultural heritage",
         "reasons": ["Matches your love for natural beauty and cultural exploration", "Perfect for peaceful mountain retreats you prefer"],
         "confidence_score": 0.9
      }},
      {{
         "title": "Lahore Food Street, Pakistan", 
         "description": "Historic food destination offering authentic Pakistani cuisine and cultural immersion",
         "reasons": ["Aligns with your interest in trying traditional foods", "Offers the cultural experiences you enjoy"],
         "confidence_score": 0.85
      }},
      {{
         "title": "Skardu, Pakistan",
         "description": "Adventure destination for trekking and mountaineering with stunning natural scenery",
         "reasons": ["Perfect for your moderate adventure seeking preferences", "Offers the peaceful outdoor experiences you value"],
         "confidence_score": 0.8
      }}
    ]
    
    Generate your response in JSON format only.
    """
    
    # Setting up LLM - same as Streamlit pattern
    client = OpenAI(api_key=openai_key)

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": f"You're a recommendation engine that creates hyper-personalized {category.lower() if category else ''} suggestions. You MUST focus on {category.lower() if category else 'relevant'} content only. Output valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7  
    )
    
    return response.choices[0].message.content

# ROUTE DEFINITIONS - SPECIFIC ROUTES FIRST, PARAMETERIZED ROUTES LAST

@router.get("/profile")
async def get_user_profile(current_user: str = Depends(get_current_user)):
    """Get the current user's profile with category-specific completeness info"""
    try:
        print(f"🔍 Getting profile for user: {current_user}")
        profile = load_user_profile(current_user)
        
        # Handle contaminated profile (only for serious issues)
        if isinstance(profile, dict) and profile.get("error") == "contaminated_profile":
            validation_info = profile.get("validation", {})
            
            if validation_info.get("reason") == "foreign_user_data_detected":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "contaminated_profile",
                        "message": "Profile contains data from other users",
                        "user_id": current_user,
                        "validation": validation_info,
                        "recommended_action": "clear_contaminated_profile_and_restart_interview"
                    }
                )
            elif validation_info.get("reason") == "extensive_data_without_any_sessions":
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "suspicious_profile",
                        "message": "Profile has extensive data but no interview sessions",
                        "user_id": current_user,
                        "validation": validation_info,
                        "recommended_action": "start_interview_to_validate_or_clear_profile"
                    }
                )
        
        if not profile:
            # Check interview status
            db = get_firestore_client()
            sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
            sessions = list(sessions_ref.stream())
            
            if not sessions:
                raise HTTPException(
                    status_code=404,
                    detail="No profile found. Please start an interview to begin creating your profile."
                )
            
            # If there are sessions but no profile, suggest continuing
            in_progress_sessions = [s for s in sessions if s.to_dict().get("status") == "in_progress"]
            if in_progress_sessions:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "message": "Interview in progress but no profile generated yet. Continue the interview to build your profile.",
                        "sessions": [{"session_id": s.id, "phase": s.to_dict().get("current_phase"), "category": s.to_dict().get("selected_category")} for s in in_progress_sessions]
                    }
                )
        
        # Return profile with enhanced category information
        clean_profile = {k: v for k, v in profile.items() if not k.startswith('_')}
        validation_summary = profile.get("_validation", {})
        
        response = {
            "success": True,
            "profile": clean_profile,
            "user_id": current_user,
            "profile_type": "user_specific",
            "profile_found": True,
            "profile_completeness": validation_summary.get("profile_completeness", "unknown"),
            "category_completeness": validation_summary.get("category_completeness", {}),
            "validation_summary": {
                "valid": validation_summary.get("valid", True),
                "authenticity_score": validation_summary.get("authenticity_score", 1.0),
                "reason": validation_summary.get("reason"),
                "has_interview_activity": validation_summary.get("has_any_session", False),
                "questions_answered": validation_summary.get("total_questions_answered", 0),
                "total_responses": validation_summary.get("total_detailed_responses", 0),
                "authenticated_responses": validation_summary.get("total_authenticated_responses", 0),
                "completed_phases_by_category": validation_summary.get("completed_phases_by_category", {}),
                "in_progress_phases_by_category": validation_summary.get("in_progress_phases_by_category", {})
            },
            "profile_source": profile.get("_source", "unknown")
        }
        
        # Add enhanced guidance based on category completeness
        category_completeness = validation_summary.get("category_completeness", {})
        completed_categories = [cat for cat, data in category_completeness.items() if data.get("interview_completed")]
        in_progress_categories = [cat for cat, data in category_completeness.items() if data.get("interview_in_progress")]
        available_categories = ["Movies", "Food", "Travel", "Books", "Music", "Fitness"]
        not_started_categories = [cat for cat in available_categories if cat not in category_completeness]
        
        if len(completed_categories) == len(category_completeness) and len(completed_categories) > 0:
            response["message"] = f"Profile complete for {len(completed_categories)} categories: {', '.join(completed_categories)}. You can start interviews for other categories or update existing ones."
        elif len(completed_categories) > 0:
            response["message"] = f"Profile complete for: {', '.join(completed_categories)}. Continue in-progress categories or start new ones."
        elif len(in_progress_categories) > 0:
            response["message"] = f"Interviews in progress for: {', '.join(in_progress_categories)}. Continue these or start new category interviews."
        else:
            response["message"] = "Start category interviews to build your personalized profile."
        
        # Add actionable suggestions
        response["suggestions"] = {
            "completed_categories": completed_categories,
            "in_progress_categories": in_progress_categories,
            "available_to_start": not_started_categories,
            "can_update": completed_categories,
            "should_continue": in_progress_categories
        }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in get_user_profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load profile: {str(e)}"
        )

@router.get("/profile/category/{category}")
async def get_category_profile_status(
    category: str,
    current_user: str = Depends(get_current_user)
):
    """Get profile status for a specific category"""
    try:
        profile = load_user_profile(current_user)
        
        if not profile:
            return {
                "success": False,
                "user_id": current_user,
                "category": category,
                "has_data": False,
                "message": f"No profile found. Start a {category} interview to begin."
            }
        
        validation_summary = profile.get("_validation", {})
        category_completeness = validation_summary.get("category_completeness", {})
        
        if category in category_completeness:
            category_data = category_completeness[category]
            return {
                "success": True,
                "user_id": current_user,
                "category": category,
                "has_data": category_data.get("has_profile_data", False),
                "interview_completed": category_data.get("interview_completed", False),
                "interview_in_progress": category_data.get("interview_in_progress", False),
                "data_authenticity": category_data.get("data_authenticity", "unknown"),
                "detailed_responses": category_data.get("detailed_responses", 0),
                "authenticated_responses": category_data.get("authenticated_responses", 0),
                "status": "completed" if category_data.get("interview_completed") else "in_progress" if category_data.get("interview_in_progress") else "has_data",
                "message": f"{category} profile status: {category_data.get('data_authenticity', 'unknown')}"
            }
        else:
            return {
                "success": True,
                "user_id": current_user,
                "category": category,
                "has_data": False,
                "interview_completed": False,
                "interview_in_progress": False,
                "status": "not_started",
                "message": f"No {category} profile data found. Start a {category} interview to begin building this section."
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get category profile status: {str(e)}"
        )

@router.post("/restart/{category}")
async def restart_category_interview(
    category: str,
    current_user: str = Depends(get_current_user)
):
    """Restart interview for a specific category"""
    try:
        db = get_firestore_client()
        
        # Find existing sessions for this category
        sessions_query = db.collection("interview_sessions")\
            .where("user_id", "==", current_user)\
            .where("selected_category", "==", category)
        
        existing_sessions = list(sessions_query.stream())
        
        # Archive all existing sessions for this category
        for session in existing_sessions:
            session.reference.update({
                "status": "archived",
                "archived_at": datetime.utcnow(),
                "archived_reason": "category_restart"
            })
        
        # Create new session
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "user_id": current_user,
            "selected_category": category,
            "status": "in_progress",
            "current_tier": 1,
            "current_phase": "general",
            "questions_answered": 0,
            "total_tiers": 3,
            "is_complete": False,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "user_specific": True,
            "restart_count": len(existing_sessions)
        }
        
        # Save new session
        db.collection("interview_sessions").document(session_id).set(session_data)
        
        return {
            "success": True,
            "message": f"Restarted {category} interview",
            "session_id": session_id,
            "user_id": current_user,
            "category": category,
            "archived_sessions": len(existing_sessions),
            "status": "in_progress"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restart {category} interview: {str(e)}"
        )

@router.get("/categories")
async def get_recommendation_categories():
    """Get available recommendation categories"""
    categories = [
        {
            "id": "movies",
            "name": "Movies & TV",
            "description": "Movie and TV show recommendations",
            "questions_file": "moviesAndTV_tiered_questions.json"
        },
        {
            "id": "food",
            "name": "Food & Dining",
            "description": "Restaurant and food recommendations",
            "questions_file": "foodAndDining_tiered_questions.json"
        },
        {
            "id": "travel",
            "name": "Travel",
            "description": "Travel destination recommendations",
            "questions_file": "travel_tiered_questions.json"
        },
        {
            "id": "books",
            "name": "Books & Reading",
            "description": "Book recommendations",
            "questions_file": "books_tiered_questions.json"
        },
        {
            "id": "music",
            "name": "Music",
            "description": "Music and artist recommendations",
            "questions_file": "music_tiered_questions.json"
        },
        {
            "id": "fitness",
            "name": "Fitness & Wellness",
            "description": "Fitness and wellness recommendations",
            "questions_file": "fitness_tiered_questions.json"
        }
    ]
    
    return {
        "categories": categories,
        "default_category": "movies"
    }

@router.post("/generate", response_model=RecommendationResponse)
async def generate_user_recommendations(
    request: RecommendationRequest,
    current_user: str = Depends(get_current_user)
):
    """Generate recommendations using the same logic as Streamlit but enhanced for FastAPI"""
    try:
        start_time = datetime.utcnow()
        settings = get_settings()
        db = get_firestore_client()
        
        print(f"🚀 Generating recommendations for user: {current_user}")
        print(f"📝 Query: {request.query}")
        print(f"🏷️ Category: {request.category}")
        
        # Load profile (same as Streamlit)
        user_profile = load_user_profile(current_user)
        
        # Handle serious contamination only
        if isinstance(user_profile, dict) and user_profile.get("error") == "contaminated_profile":
            validation = user_profile.get("validation", {})
            if validation.get("reason") in ["foreign_user_data_detected", "extensive_data_without_any_sessions"]:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "error": "contaminated_profile",
                        "message": "Cannot generate recommendations with contaminated profile data",
                        "recommended_action": "clear_profile_and_start_interview"
                    }
                )
        
        # If no profile, check if we should allow basic recommendations (same as Streamlit)
        if not user_profile:
            print("⚠️ No profile found - checking interview status")
            
            # Check if user has any interview activity
            sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
            sessions = list(sessions_ref.stream())
            
            if not sessions:
                # No interview started - create minimal profile for basic recommendations
                print("📝 No interview sessions - creating basic profile for general recommendations")
                user_profile = {
                    "user_id": current_user,
                    "generalprofile": {
                        "corePreferences": {
                            "note": f"Basic profile - complete interview for personalized {request.category or 'recommendations'}"
                        }
                    },
                    "profile_completeness": "empty"
                }
            else:
                # Has interview activity but no profile - this shouldn't happen
                raise HTTPException(
                    status_code=404,
                    detail="Interview sessions found but no profile generated. Please contact support."
                )
        
        # Clean profile for AI processing (remove metadata)
        clean_profile = {k: v for k, v in user_profile.items() if not k.startswith('_')}
        
        # Get profile completeness info
        validation_summary = user_profile.get("_validation", {})
        profile_completeness = validation_summary.get("profile_completeness", "unknown")
        questions_answered = validation_summary.get("total_questions_answered", 0)
        category_completeness = validation_summary.get("category_completeness", {})
        
        print(f"📊 Profile completeness: {profile_completeness}")
        print(f"📝 Questions answered: {questions_answered}")
        print(f"🏷️ Category completeness: {list(category_completeness.keys())}")
        
        # Check if the requested category has data
        category_has_data = False
        category_status = "not_started"
        if request.category and request.category in category_completeness:
            category_data = category_completeness[request.category]
            category_has_data = category_data.get("has_profile_data", False)
            if category_data.get("interview_completed"):
                category_status = "completed"
            elif category_data.get("interview_in_progress"):
                category_status = "in_progress"
            else:
                category_status = "has_data"
        
        print(f"🎯 Category {request.category} status: {category_status}, has_data: {category_has_data}")
        
        # Generate category-aware recommendations
        recs_json = generate_recommendations(
            clean_profile, 
            request.query, 
            settings.OPENAI_API_KEY,
            request.category  # Add category parameter
        )
        
        try:
            recs = json.loads(recs_json)
            
            # Normalize to list (same as Streamlit)
            if isinstance(recs, dict):
                if "recommendations" in recs and isinstance(recs["recommendations"], list):
                    recs = recs["recommendations"]
                else:
                    recs = [recs]
            
            if not isinstance(recs, list):
                raise HTTPException(
                    status_code=500,
                    detail="Unexpected response format – expected a list of recommendations."
                )
            
            # Validate category relevance for travel
            if request.category and request.category.lower() == "travel":
                travel_keywords = ["destination", "place", "visit", "travel", "city", "country", "attraction", "trip", "valley", "mountain", "beach", "street", "food", "culture", "heritage", "adventure", "pakistan", "hunza", "lahore", "skardu"]
                
                for i, rec in enumerate(recs):
                    title_and_desc = (rec.get('title', '') + ' ' + rec.get('description', '')).lower()
                    if not any(keyword in title_and_desc for keyword in travel_keywords):
                        print(f"⚠️ Recommendation {i+1} '{rec.get('title')}' may not be travel-related")
                        print(f"🔍 Content: {title_and_desc[:100]}...")
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Add profile completion guidance based on category status
            for rec in recs:
                if "reasons" not in rec:
                    rec["reasons"] = []
                
                if request.category and category_status == "not_started":
                    rec["reasons"].append(f"Start a {request.category} interview for more personalized recommendations")
                elif request.category and category_status == "in_progress":
                    rec["reasons"].append(f"Continue your {request.category} interview for better personalization")
                elif profile_completeness == "empty":
                    rec["reasons"].append("Start an interview to get more personalized recommendations")
                elif profile_completeness in ["partial_in_progress", "partial_data_exists"]:
                    rec["reasons"].append("Complete more interview questions for better personalization")
            
            # Generate session ID for conversation tracking
            session_id = str(uuid.uuid4())
            
            # Save conversation messages (like Streamlit chat)
            save_conversation_message(
                current_user, 
                session_id, 
                "user", 
                f"What would you like {request.category.lower() if request.category else ''} recommendations for? {request.query}", 
                "recommendation",
                f"{request.category or 'General'} Recommendation Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
            # Prepare recommendation data for database
            recommendation_data = {
                "user_id": current_user,
                "query": request.query,
                "category": request.category,
                "recommendations": recs,
                "processing_time_ms": int(processing_time),
                "search_context": search_web(f"{request.category} {request.query} recommendations 2024" if request.category else f"{request.query} recommendations 2024"),
                "session_id": session_id,
                "profile_version": clean_profile.get("version", "1.0"),
                "profile_completeness": profile_completeness,
                "category_status": category_status,
                "category_has_data": category_has_data,
                "questions_answered": questions_answered,
                "user_specific": True,
                "generation_method": "streamlit_compatible"
            }
            
            # Save to database
            recommendation_id = save_recommendation_to_db(recommendation_data, db)
            
            if not recommendation_id:
                print("⚠️ Warning: Failed to save recommendation to database")
                recommendation_id = str(uuid.uuid4())  # Fallback
            
            # Format recommendations for conversation history (like Streamlit display)
            recs_text = f"Here are your {request.category.lower() if request.category else ''} recommendations:\n\n"
            
            for i, rec in enumerate(recs, 1):
                title = rec.get("title", "<no title>")
                description = rec.get("description", rec.get("reason", "<no description>"))
                reasons = rec.get("reasons", [])
                
                recs_text += f"**{i}. {title}**\n"
                recs_text += f"{description}\n"
                if reasons:
                    for reason in reasons:
                        recs_text += f"• {reason}\n"
                recs_text += "\n"
            
            # Save recommendations to conversation history
            save_conversation_message(
                current_user, 
                session_id, 
                "assistant", 
                recs_text, 
                "recommendation"
            )
            
            # Convert to RecommendationItem objects
            recommendation_items = []
            for rec in recs:
                # Use confidence score from AI or default based on profile completeness
                base_confidence = 0.6 if profile_completeness == "empty" or category_status == "not_started" else 0.8
                confidence_score = rec.get('confidence_score', base_confidence)
                
                recommendation_items.append(RecommendationItem(
                    title=rec.get('title', 'Recommendation'),
                    description=rec.get('description', rec.get('reason', '')),
                    reasons=rec.get('reasons', []),
                    category=request.category,
                    confidence_score=confidence_score
                ))
            
            return RecommendationResponse(
                recommendation_id=recommendation_id,
                recommendations=recommendation_items,
                query=request.query,
                category=request.category,
                user_id=current_user,
                generated_at=datetime.utcnow(),
                processing_time_ms=int(processing_time)
            )
            
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse recommendations: {str(e)}"
            print(f"❌ JSON parsing error: {error_msg}")
            print(f"🔍 Raw AI response: {recs_json[:500]}...")
            
            # Save error to conversation history
            save_conversation_message(
                current_user, 
                str(uuid.uuid4()), 
                "assistant", 
                f"Sorry, I encountered an error generating {request.category or ''} recommendations: {error_msg}", 
                "recommendation"
            )
            
            raise HTTPException(
                status_code=500,
                detail=error_msg
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error generating recommendations for user {current_user}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate {request.category or ''} recommendations: {str(e)}"
        )

@router.get("/history")
async def get_recommendation_history(
    current_user: str = Depends(get_current_user),
    limit: int = Query(20, description="Number of recommendations to return"),
    offset: int = Query(0, description="Number of recommendations to skip"),
    category: Optional[str] = Query(None, description="Filter by category")
):
    """Get recommendation history for the user with enhanced filtering"""
    try:
        db = get_firestore_client()
        
        # Simplified query to avoid index issues
        query = db.collection("user_recommendations").document(current_user).collection("recommendations")
        query = query.where("is_active", "==", True)
        query = query.limit(limit).offset(offset)
        
        recommendations = list(query.stream())
        
        # Filter and sort in Python
        filtered_recs = []
        for rec in recommendations:
            rec_data = rec.to_dict()
            
            # Apply category filter
            if category and rec_data.get("category") != category:
                continue
            
            filtered_recs.append(rec_data)
        
        # Sort by generated_at descending
        filtered_recs.sort(key=lambda x: x.get("generated_at", datetime.min), reverse=True)
        
        # Format response
        history = []
        for rec_data in filtered_recs:
            history.append({
                "recommendation_id": rec_data["recommendation_id"],
                "query": rec_data["query"],
                "category": rec_data.get("category"),
                "recommendations_count": len(rec_data.get("recommendations", [])),
                "generated_at": rec_data["generated_at"],
                "view_count": rec_data.get("view_count", 0),
                "feedback_count": rec_data.get("feedback_count", 0),
                "session_id": rec_data.get("session_id"),
                "processing_time_ms": rec_data.get("processing_time_ms"),
                "profile_completeness": rec_data.get("profile_completeness", "unknown"),
                "category_status": rec_data.get("category_status", "unknown"),
                "generation_method": rec_data.get("generation_method", "unknown")
            })
        
        return {
            "success": True,
            "history": history,
            "total_count": len(history),
            "user_id": current_user,
            "filters": {
                "category": category,
                "limit": limit,
                "offset": offset
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recommendation history: {str(e)}"
        )

@router.post("/{recommendation_id}/feedback")
async def submit_recommendation_feedback(
    recommendation_id: str,
    feedback: RecommendationFeedback,
    current_user: str = Depends(get_current_user)
):
    """Submit feedback for a recommendation"""
    try:
        db = get_firestore_client()
        
        # Verify recommendation exists and belongs to user
        rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
        if not rec_doc.exists:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        # Save feedback
        feedback_data = {
            "feedback_type": feedback.feedback_type,
            "rating": feedback.rating,
            "comment": feedback.comment,
            "clicked_items": feedback.clicked_items
        }
        
        feedback_id = save_recommendation_feedback(recommendation_id, current_user, feedback_data, db)
        
        if not feedback_id:
            raise HTTPException(status_code=500, detail="Failed to save feedback")
        
        return {
            "success": True,
            "message": "Feedback submitted successfully",
            "feedback_id": feedback_id,
            "recommendation_id": recommendation_id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit feedback: {str(e)}"
        )

# IMPORTANT: Put parameterized routes LAST to avoid route conflicts
@router.get("/{recommendation_id}")
async def get_recommendation_details(
    recommendation_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get detailed information about a specific recommendation"""
    try:
        db = get_firestore_client()
        
        # Get recommendation details
        rec_doc = db.collection("user_recommendations").document(current_user).collection("recommendations").document(recommendation_id).get()
        
        if not rec_doc.exists:
            raise HTTPException(status_code=404, detail="Recommendation not found")
        
        rec_data = rec_doc.to_dict()
        
        # Increment view count
        current_views = rec_data.get("view_count", 0)
        rec_doc.reference.update({
            "view_count": current_views + 1,
            "last_viewed": datetime.utcnow()
        })
        
        return {
            "success": True,
            "recommendation": {
                "recommendation_id": rec_data["recommendation_id"],
                "query": rec_data["query"],
                "category": rec_data.get("category"),
                "recommendations": rec_data["recommendations"],
                "generated_at": rec_data["generated_at"],
                "processing_time_ms": rec_data.get("processing_time_ms"),
                "view_count": current_views + 1,
                "search_context": rec_data.get("search_context", []),
                "profile_completeness": rec_data.get("profile_completeness", "unknown"),
                "category_status": rec_data.get("category_status", "unknown"),
                "questions_answered": rec_data.get("questions_answered", 0),
                "generation_method": rec_data.get("generation_method", "unknown")
            },
            "user_id": current_user
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recommendation details: {str(e)}"
        )