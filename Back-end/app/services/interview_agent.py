from openai import OpenAI
from app.core.config import get_settings
from typing import List, Dict, Any, Optional
import uuid

class InterviewAgent:
    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.phases = self._load_question_structure()
        
    def _load_question_structure(self):
        """Load the complete interview structure"""
        return [
            {
                "name": "Foundational Understanding",
                "instructions": ("Please answer the following questions as openly and descriptively as possible. "
                                "Think about specific examples, feelings, and the 'why' behind your answers."),
                "questions": [
                    "Tell me about your life story in brief. What key moments shaped who you are today?",
                    "What 3-5 core values or principles guide your decisions in life?",
                    "How would you describe your personality? What aspects are you most proud of?",
                    "What activities or experiences truly bring you joy and fulfillment?",
                    "How do you typically approach challenges or stress in your life?",
                ]
            },
            {
                "name": "Preferences & Tastes",
                "instructions": "Let's explore your preferences and tastes across different categories.",
                "questions": [
                    "What types of entertainment (movies, TV, books, music) do you most enjoy and why?",
                    "Describe your ideal travel experience. What aspects do you value most?",
                    "What's your approach to food and dining? Any particular preferences or cuisines you love?",
                    "What role does physical activity or wellness play in your life?",
                    "How do you like to discover new things to try or experience?",
                ]
            }
        ]
    
    def get_current_question(self, phase_index: int, question_index: int) -> Dict[str, Any]:
        """Get current question based on phase and question index"""
        if phase_index < len(self.phases) and question_index < len(self.phases[phase_index]["questions"]):
            return {
                "phase": self.phases[phase_index]["name"],
                "question": self.phases[phase_index]["questions"][question_index],
                "is_complete": False
            }
        elif phase_index < len(self.phases):
            # Move to next phase
            return {
                "phase": self.phases[phase_index + 1]["name"] if phase_index + 1 < len(self.phases) else "Complete",
                "question": self.phases[phase_index + 1]["questions"][0] if phase_index + 1 < len(self.phases) else "",
                "is_complete": phase_index + 1 >= len(self.phases)
            }
        else:
            # Interview complete
            return {
                "phase": "Complete",
                "question": "",
                "is_complete": True
            }
    
    def generate_follow_up(self, question: str, answer: str) -> str:
        """Generate follow-up question based on user's answer"""
        prompt = f"""Generate ONE follow-up question based on:
        Original Q: {question}
        Response: {answer[:300]}
        Keep it relevant and probing for more depth or specific examples."""
        
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an interview agent that creates insightful follow-up questions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=100
        )
        
        return response.choices[0].message.content.strip()
    
    def evaluate_answer_quality(self, answer: str) -> bool:
        """Determine if answer needs follow-up based on depth and specificity"""
        if len(answer.split()) < 20:  # Too short
            return True
            
        # Use LLM to assess quality
        prompt = f"""Assess if this response needs a follow-up question (YES/NO answer only):
        Response: {answer[:300]}
        
        Consider:
        - Does it include specific examples?
        - Does it have emotional depth or personal reflection?
        - Does it provide sufficient detail?
        """
        
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You evaluate interview answer quality and respond only with YES or NO."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=10
        )
        
        # If the answer is "YES", then follow-up is needed
        return "YES" in response.choices[0].message.content.upper()
    
    def create_session(self, user_id: str) -> Dict[str, Any]:
        """Create a new interview session"""
        session_id = str(uuid.uuid4())
        
        return {
            "session_id": session_id,
            "user_id": user_id,
            "current_phase": 0,
            "current_question": 0,
            "follow_up_count": 0,
            "conversation": []
        }