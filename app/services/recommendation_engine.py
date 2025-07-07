from openai import OpenAI
from app.core.config import get_settings
from typing import Dict, Any, List
import json
from duckduckgo_search import DDGS
from duckduckgo_search.exceptions import DuckDuckGoSearchException
from itertools import islice
import time
from firebase_admin import firestore

class RecommendationEngine:
    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.db = firestore.client()
    
    def load_user_profile(self, user_id: str = None) -> Dict[str, Any]:
        """Load user profile from Firestore"""
        try:
            doc_ref = self.db.collection("user_collection").document("profile_strcuture.json")
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            else:
                return {}
        except Exception as e:
            print(f"Error loading user profile: {e}")
            return {}
    
    def search_web(self, query: str, max_results: int = 3, max_retries: int = 3, base_delay: float = 1.0) -> List[Dict[str, Any]]:
        """Search the web with retry logic for rate limiting"""
        for attempt in range(1, max_retries + 1):
            try:
                with DDGS() as ddgs:
                    results = list(islice(ddgs.text(query), max_results))
                    return results
            except DuckDuckGoSearchException as e:
                msg = str(e)
                if "202" in msg:
                    wait = base_delay * (2 ** (attempt - 1))
                    print(f"[search_web] Rate-limited (202). Retry {attempt}/{max_retries} in {wait:.1f}s...")
                    time.sleep(wait)
                else:
                    raise
            except Exception as e:
                print(f"Search error: {e}")
                return []
        
        print(f"[search_web] Failed to fetch results after {max_retries} attempts.")
        return []
    
    def generate_recommendations(self, user_query: str, user_profile: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Generate personalized recommendations based on user profile and search results"""
        
        # Load user profile if not provided
        if user_profile is None:
            user_profile = self.load_user_profile()
        
        # Get current web context
        search_results = self.search_web(f"{user_query} recommendations 2024")
        
        prompt = f"""
        **Task**: Generate exactly 3 highly personalized recommendations based on:
        
        **User Profile**:
        {json.dumps(user_profile, indent=2)}
        
        **User Query**:
        "{user_query}"
        
        **Web Context** (for reference only):
        {json.dumps(search_results, indent=2)}
        
        **Requirements**:
        1. Each recommendation must directly reference profile details
        2. Blend the user's core values and preferences
        3. Only suggest what is asked for suggest no extra advices.
        4. Format as JSON array with each recommendation having:
           - title: string
           - reason: string (why it matches the user profile)
        
        **Output Example**:
        [
          {{
             "title": "Creative Project Tool",
             "reason": "Matches your love for storytelling and freelance work. Try Notion's creative templates for content planning."
          }},
          {{
             "title": "Historical Drama Series",
             "reason": "Resonates with your interest in personal struggles and leadership as shown in historical figures."
          }},
          {{
             "title": "Motivational Biopic",
             "reason": "Highlights overcoming personal difficulties aligning with your experiences of resilience."
          }}
        ]
        
        Generate your response in JSON format only.
        """

        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You're a recommendation engine that creates hyper-personalized suggestions. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        try:
            result = response.choices[0].message.content
            
            # Try to parse as JSON directly
            try:
                recommendations = json.loads(result)
                return recommendations if isinstance(recommendations, list) else [recommendations]
            except json.JSONDecodeError:
                # Try to extract JSON array from the response
                start = result.find('[')
                end = result.rfind(']') + 1
                if start >= 0 and end > start:
                    json_str = result[start:end]
                    recommendations = json.loads(json_str)
                    return recommendations if isinstance(recommendations, list) else [recommendations]
                else:
                    # Try to extract JSON object and wrap in array
                    start = result.find('{')
                    end = result.rfind('}') + 1
                    if start >= 0 and end > start:
                        json_str = result[start:end]
                        recommendation = json.loads(json_str)
                        return [recommendation]
                    
                raise ValueError("Could not parse JSON from response")
                
        except Exception as e:
            print(f"Error parsing recommendations: {e}")
            # Return a fallback response
            return [
                {
                    "title": "Personalized Suggestion",
                    "reason": "Based on your profile and preferences, this recommendation aligns with your interests."
                }
            ]
    
    def generate_category_recommendations(self, category: str, user_query: str, user_profile: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Generate recommendations for a specific category"""
        
        # Load user profile if not provided
        if user_profile is None:
            user_profile = self.load_user_profile()
        
        # Get current web context
        search_results = self.search_web(f"{category} {user_query} recommendations 2024")
        
        prompt = f"""
        **Task**: Generate exactly 3 highly personalized {category} recommendations based on:
        
        **User Profile**:
        {json.dumps(user_profile, indent=2)}
        
        **User Query**:
        "{user_query}"
        
        **Category**: {category}
        
        **Web Context** (for reference only):
        {json.dumps(search_results, indent=2)}
        
        **Requirements**:
        1. Each recommendation must directly reference profile details
        2. Blend the user's core values and preferences
        3. Only suggest items in the "{category}" category
        4. Provide specific, actionable recommendations
        5. Format as JSON array with each recommendation having:
           - title: string
           - description: string (brief description)
           - reasons: array of strings (specific reasons why it matches the user)
        
        **Output Format**:
        [
          {{
            "title": "Specific Recommendation Title",
            "description": "Brief description of the recommendation",
            "reasons": [
              "Reason 1 connecting to user profile",
              "Reason 2 connecting to user preferences"
            ]
          }},
          ...
        ]
        
        Generate your response in JSON format only.
        """

        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": f"You're a specialized {category} recommendation engine. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        try:
            result = response.choices[0].message.content
            
            # Try to parse as JSON directly
            try:
                recommendations = json.loads(result)
                return recommendations if isinstance(recommendations, list) else [recommendations]
            except json.JSONDecodeError:
                # Try to extract JSON array from the response
                start = result.find('[')
                end = result.rfind(']') + 1
                if start >= 0 and end > start:
                    json_str = result[start:end]
                    recommendations = json.loads(json_str)
                    return recommendations if isinstance(recommendations, list) else [recommendations]
                else:
                    raise ValueError("Could not parse JSON from response")
                    
        except Exception as e:
            print(f"Error parsing category recommendations: {e}")
            # Return a fallback response
            return [
                {
                    "title": f"Personalized {category} Suggestion",
                    "description": f"A {category} recommendation tailored to your preferences",
                    "reasons": ["Based on your profile and preferences", "Aligns with your interests and values"]
                }
            ]