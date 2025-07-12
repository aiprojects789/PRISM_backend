
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