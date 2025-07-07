from openai import OpenAI
from app.core.config import get_settings
from typing import Dict, Any, List
import json
import re
from collections import defaultdict
from firebase_admin import firestore

class ProfileGenerator:
    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.db = firestore.client()
    
    def extract_json_array(self, s: str) -> str:
        """Extract JSON array from LLM output"""
        pattern = r'\[\s*(?:\{.*?\}\s*,?\s*)+\]'
        match = re.search(pattern, s, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON array found in LLM response")
        return match.group(0)
    
    def get_concept_paths(self, data: dict, parent_key: str = '', sep: str = '.') -> List[str]:
        """Get all concept paths from nested dictionary"""
        paths: List[str] = []
        for key, value in data.items():
            new_key = f"{parent_key}{sep}{key}" if parent_key else key
            if isinstance(value, dict):
                if 'description' in value or 'values' in value or 'value' in value:
                    paths.append(new_key)
                else:
                    for child_key, child_val in value.items():
                        if isinstance(child_val, dict):
                            paths.extend(self.get_concept_paths({child_key: child_val}, new_key, sep))
        return paths
    
    def get_description_for_path(self, root: dict, dotted_path: str) -> str:
        """Get description for a specific path in nested dictionary"""
        parts = dotted_path.split('.') if dotted_path else []
        node = root
        for key in parts:
            node = node.get(key, {}) if isinstance(node, dict) else {}
        return node.get('description', '') if isinstance(node, dict) else ''
    
    def generate_single_question(self, field_path: str, intent_desc: str) -> str:
        """Generate a conversational question for a specific field"""
        prompt = f"""You are a friendly AI assistant helping users build their personalized digital twin for better recommendations. Your tone should be warm, encouraging, and respectful.

Generate a conversational, open-ended question that:
- Feels like part of a friendly dialogue
- Offers light guidance or an example to help the user answer
- Is inclusive and privacy-aware (especially if the topic is sensitive)
- Does NOT include multiple-choice options or lists
- Sounds like something a thoughtful assistant would naturally ask

Use the field name and description to craft the question.

Field Name: {field_path}  
Description: {intent_desc}

Generate a conversational question:"""
        
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a friendly AI assistant creating conversational interview questions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=150
        )
        
        return response.choices[0].message.content.strip()
    
    def rank_and_tier_with_gpt4o(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank and tier questions using GPT-4"""
        prompt = f"""Here is a JSON array of questions. 
        
        Respond with ONLY a JSON array of the same objects, each with added:
        - impactScore: integer 0–100 (based on how much this question impacts personalization)
        - tier: "Tier 1", "Tier 2", or "Tier 3" (Tier 1 = highest impact, most essential)
        
        Sort by descending impactScore and distribute evenly across tiers.
        
        ```json
        {json.dumps(questions, indent=2)}
        ```"""
        
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert in personalization and recommendation logic. Score each question 0–100 on impact, rank, and bucket into three equal tiers."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        try:
            json_text = self.extract_json_array(response.choices[0].message.content)
            return json.loads(json_text)
        except Exception as e:
            print(f"Error parsing ranked questions: {e}")
            # Return original questions with default scoring
            for i, q in enumerate(questions):
                q['impactScore'] = 100 - (i * 10)  # Simple descending score
                q['tier'] = f"Tier {(i // (len(questions) // 3)) + 1}"
            return questions
    
    def enrich_questions(self, flat_questions: List[Dict[str, Any]], schema: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Enrich questions with metadata"""
        enriched: List[Dict[str, Any]] = []
        for q in flat_questions:
            full = q["field"]  
            section, *rest = full.split('.', 1)
            subsection = rest[0] if rest else ''
            description = self.get_description_for_path(
                schema.get(section, {}),
                subsection
            )
            enriched.append({
                "section": section,
                "subsection": subsection,
                "field": full,
                "description": description,
                "question": q["question"],
                "impactScore": q["impactScore"],
                "tier": q["tier"],
                "qest": "pending"
            })
        return enriched
    
    def wrap_questions_by_tier(self, flat_questions: List[Dict[str, Any]], status: str = "in_process") -> Dict[str, Dict[str, Any]]:
        """Wrap questions into tier structure"""
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for q in flat_questions:
            grouped[q["tier"]].append(q)

        return {
            "tier1": {"status": status, "questions": grouped.get("Tier 1", [])},
            "tier2": {"status": status, "questions": grouped.get("Tier 2", [])},
            "tier3": {"status": status, "questions": grouped.get("Tier 3", [])},
        }
    
    def generate_questions(self, data: dict, section: str, category: str = None) -> List[Dict[str, Any]]:
        """Generate questions for a specific section"""
        results: List[Dict[str, Any]] = []
        
        if section == 'generalprofile':
            base = data.get('generalprofile', {})
            for p in self.get_concept_paths(base):
                abs_path = f"generalprofile.{p}"
                desc = self.get_description_for_path(base, p)
                q = self.generate_single_question(abs_path, desc)
                results.append({'field': abs_path, 'question': q})

        elif section == 'recommendationProfiles' and category:
            base = data.get('recommendationProfiles', {}).get(category, {})
            for p in self.get_concept_paths(base):
                abs_path = f"recommendationProfiles.{category}.{p}"
                desc = self.get_description_for_path(base, p)
                q = self.generate_single_question(abs_path, desc)
                results.append({'field': abs_path, 'question': q})

        elif section == 'simulationPreferences':
            base = data.get('simulationPreferences', {})
            for p in self.get_concept_paths(base):
                abs_path = f"simulationPreferences.{p}"
                desc = self.get_description_for_path(base, p)
                q = self.generate_single_question(abs_path, desc)
                results.append({'field': abs_path, 'question': q})

        return results
    
    def generate_and_save_questions(self, schema_data: dict, section: str, category: str = None) -> Dict[str, Any]:
        """Generate, rank, and save questions to Firestore"""
        try:
            # Generate questions
            flat_questions = self.generate_questions(schema_data, section, category)
            
            # Rank and tier questions
            ranked_questions = self.rank_and_tier_with_gpt4o(flat_questions)
            
            # Enrich questions with metadata
            enriched_questions = self.enrich_questions(ranked_questions, schema_data)
            
            # Wrap into tier structure
            tiered_questions = self.wrap_questions_by_tier(enriched_questions)
            
            # Save to Firestore
            collection_name = "question_collection"
            if category:
                doc_name = f"{category}_tiered_questions.json"
            else:
                doc_name = f"{section}_tiered_questions.json"
            
            doc_ref = self.db.collection(collection_name).document(doc_name)
            doc_ref.set(tiered_questions)
            
            return tiered_questions
            
        except Exception as e:
            print(f"Error generating and saving questions: {e}")
            raise
    
    def generate_phase_summary(self, phase: str, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a summary for a specific interview phase"""
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
        """Generate a full user profile from interview data"""
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