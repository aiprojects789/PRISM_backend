from openai import OpenAI
from app.core.config import get_settings
from typing import Dict, Any, List
import json
from duckduckgo_search import DDGS
from itertools import islice

class RecommendationEngine:
    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def search_web(self, query: str, max_results: int = 3) -> List[Dict[str, Any]]:
        """Search the web for relevant information"""
        try:
            with DDGS() as ddgs:
                results = list(islice(ddgs.text(query), max_results))
                return results
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def generate_recommendations(self, user_profile: Dict[str, Any], category: str, query: str) -> List[Dict[str, Any]]:
        """Generate personalized recommendations based on user profile and search results"""
        # Get current web context
        search_results = self.search_web(f"{category} {query} recommendations")
        
        prompt = f"""
        **Task**: Generate exactly 3 highly personalized {category} recommendations based on:
        
        **User Profile**:
        {json.dumps(user_profile, indent=2)}
        
        **User Query**:
        "{query}"
        
        **Web Context** (for reference only):
        {json.dumps(search_results, indent=2)}
        
        **Requirements**:
        1. Each recommendation must directly reference profile details
        2. Blend the user's core values and preferences
        3. Only suggest what is asked for in the category "{category}"
        4. For each recommendation, provide:
           - Title
           - Brief description
           - Specific reasons why it matches the user profile (at least 2)
        
        **Output Format**:
        Return a JSON array with 3 recommendation objects, each with:
        - title (string)
        - description (string)
        - reasons (array of strings)
        """

        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You're a recommendation engine that creates hyper-personalized suggestions. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        try:
            result = json.loads(response.choices[0].message.content)
            if "recommendations" in result:
                return result["recommendations"]
            return result  # Assume the entire response is the recommendations array
        except json.JSONDecodeError:
            # Try to extract just the JSON part
            content = response.choices[0].message.content
            start = content.find('[')
            end = content.rfind(']') + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
            raise ValueError("Could not parse JSON from response")