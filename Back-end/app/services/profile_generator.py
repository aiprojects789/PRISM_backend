from openai import OpenAI
from app.core.config import get_settings
from typing import Dict, Any, List
import json
from collections import defaultdict

class ProfileGenerator:
    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def generate_phase_summary(self, phase: str, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate a summary for a specific interview phase
        """
        prompt = f"""
        Create a structured JSON summary for the following interview phase: "{phase}".
        Summarize the key ideas, values, stories, and personal characteristics discussed.
        Use clear groupings like background, personality traits, preferences, life lessons, etc.
        Return only valid JSON without any extra commentary.

        Interview Data:
        {json.dumps(data, indent=2)}
        """

        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo-16k",
            messages=[
                {"role": "system", "content": "You are a professional profile summarizer. Output valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        result = response.choices[0].message.content
        
        # Handle potential non-JSON responses
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            # Try to extract just the JSON part
            start = result.find('{')
            end = result.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(result[start:end])
            raise ValueError("Could not parse JSON from response")
    
    def generate_full_profile(self, interview_data: List[Dict[str, Any]], chunk_size: int = 4) -> Dict[str, Any]:
        """
        Generate a full user profile from interview data
        """
        # Group entries by phase
        phase_data = defaultdict(list)
        for item in interview_data:
            phase = item.get("phase", "Miscellaneous")
            phase_data[phase].append(item)
        
        # Process each phase
        full_profile = {}
        for phase, entries in phase_data.items():
            # Chunk large phases
            chunked_summaries = []
            for i in range(0, len(entries), chunk_size):
                chunk = entries[i:i + chunk_size]
                summary_json = self.generate_phase_summary(phase, chunk)
                chunked_summaries.append(summary_json)
            
            # Combine chunks for this phase
            if len(chunked_summaries) == 1:
                full_profile[phase] = chunked_summaries[0]
            else:
                full_profile[phase] = {
                    f"part_{idx+1}": chunk for idx, chunk in enumerate(chunked_summaries)
                }
        
        return full_profile