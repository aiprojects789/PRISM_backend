# from openai import OpenAI
# from app.core.config import get_settings
# from app.core.firebase import get_firestore_client  # Add this import
# from typing import List, Dict, Any, Optional
# import uuid
# import json

# class InterviewAgent:
#     def __init__(self):
#         settings = get_settings()
#         self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
#         self.db = get_firestore_client()  # ✅ Now uses the proper function
        
#         # Firestore collections
#         self.master_collection = "user_collection"
#         self.master_doc_id = "profile_strcuture.json"
#         self.tiers_collection = "question_collection"
#         self.tiers_doc_id = "general_tiered_questions.json"
        
#         # Load master profile and tier questions from Firestore
#         self.master_profile = self._load_master_profile()
#         self.tier_questions = self._load_tier_questions()
    
#     def _load_master_profile(self) -> Dict[str, Any]:
#         """Load master profile structure from Firestore"""
#         try:
#             doc_ref = self.db.collection(self.master_collection).document(self.master_doc_id)
#             doc = doc_ref.get()
#             if doc.exists:
#                 return doc.to_dict()
#             else:
#                 return {}
#         except Exception as e:
#             print(f"Error loading master profile: {e}")
#             return {}
    
#     def _load_tier_questions(self) -> Dict[str, Any]:
#         """Load tier questions from Firestore"""
#         try:
#             doc_ref = self.db.collection(self.tiers_collection).document(self.tiers_doc_id)
#             doc = doc_ref.get()
#             if doc.exists:
#                 return doc.to_dict()
#             else:
#                 return {}
#         except Exception as e:
#             print(f"Error loading tier questions: {e}")
#             return {}
    
#     def get_pending_questions_by_field(self, tier_name: str = "tier1") -> List[Dict[str, Any]]:
#         """Get all pending questions from a specific tier"""
#         tier_data = self.tier_questions.get(tier_name, {})
#         questions = tier_data.get("questions", [])
        
#         # Filter only pending questions
#         pending_questions = [q for q in questions if q.get("qest") == "pending"]
#         return pending_questions
    
#     def set_nested(self, data: Dict[str, Any], dotted_path: str, value: Any) -> None:
#         """Set nested dictionary value using dot notation"""
#         keys = dotted_path.split('.')
#         d = data
#         for key in keys[:-1]:
#             if key not in d or not isinstance(d[key], dict):
#                 d[key] = {}
#             d = d[key]
#         d[keys[-1]] = value
    
#     def apply_responses_to_profile(self, responses: Dict[str, Any], tier_name: str = "tier1") -> None:
#         """Apply user responses to both master profile and tier questions"""
#         questions = self.tier_questions.get(tier_name, {}).get("questions", [])
        
#         for q in questions:
#             field = q.get("field")
#             if q.get("qest") == "pending" and field in responses:
#                 # Update nested master profile
#                 if "generalprofile" in field:
#                     # Remove the generalprofile prefix for nested setting
#                     nested_path = field.replace("generalprofile.", "")
#                     self.set_nested(
#                         self.master_profile.get("generalprofile", {}),
#                         nested_path,
#                         responses[field]
#                     )
#                 else:
#                     # Handle other profile sections
#                     self.set_nested(self.master_profile, field, responses[field])
                
#                 # Mark question as answered
#                 q["qest"] = "answered"
        
#         # Save both profiles back to Firestore
#         self._save_profiles()
    
#     def _save_profiles(self) -> None:
#         """Save both master profile and tier questions to Firestore"""
#         try:
#             # Save master profile
#             self.db.collection(self.master_collection).document(self.master_doc_id).set(self.master_profile)
            
#             # Save tier questions
#             self.db.collection(self.tiers_collection).document(self.tiers_doc_id).set(self.tier_questions)
            
#         except Exception as e:
#             print(f"Error saving profiles: {e}")
    
#     def create_session(self, user_id: str, questions_list: List[Dict[str, Any]]) -> Dict[str, Any]:
#         """Create a new interview session with dynamic questions"""
#         session_id = str(uuid.uuid4())
        
#         # Create phases with dynamic questions
#         phases = [
#             {
#                 "name": "Dynamic Questions",
#                 "instructions": (
#                     "Please answer the following questions in order. "
#                     "There are no right or wrong answers."
#                 ),
#                 "questions": questions_list,
#                 "tier_name": "tier1"
#             }
#         ]
        
#         return {
#             "session_id": session_id,
#             "user_id": user_id,
#             "current_phase": 0,
#             "current_question": 0,
#             "follow_up_depth": 0,
#             "conversation": [],
#             "phases": phases
#         }
    
#     def get_current_question(self, session_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
#         """Get current question from session"""
#         current_phase = session_data.get("current_phase", 0)
#         current_question = session_data.get("current_question", 0)
#         phases = session_data.get("phases", [])
        
#         if current_phase >= len(phases):
#             return None
        
#         phase = phases[current_phase]
#         questions = phase.get("questions", [])
        
#         if current_question >= len(questions):
#             return None
        
#         question_data = questions[current_question]
#         return {
#             "question": question_data.get("question"),
#             "field": question_data.get("field"),
#             "phase": phase.get("name"),
#             "tier_name": phase.get("tier_name", "tier1")
#         }
    
#     def submit_answer(self, session_data: Dict[str, Any], answer: str) -> Dict[str, Any]:
#         """Submit an answer and advance to next question"""
#         current_question_data = self.get_current_question(session_data)
        
#         if not current_question_data:
#             return {"success": False, "message": "No current question found"}
        
#         # Save the answer
#         field = current_question_data.get("field")
#         tier_name = current_question_data.get("tier_name", "tier1")
        
#         # Apply response to profile
#         self.apply_responses_to_profile({field: answer}, tier_name)
        
#         # Add to conversation history
#         session_data["conversation"].append({
#             "question": current_question_data.get("question"),
#             "answer": answer,
#             "field": field,
#             "phase": current_question_data.get("phase")
#         })
        
#         # Advance to next question
#         session_data["current_question"] += 1
        
#         # Check if phase is complete
#         current_phase = session_data.get("current_phase", 0)
#         phases = session_data.get("phases", [])
        
#         if current_phase < len(phases):
#             phase = phases[current_phase]
#             questions = phase.get("questions", [])
            
#             if session_data["current_question"] >= len(questions):
#                 # Move to next phase
#                 session_data["current_phase"] += 1
#                 session_data["current_question"] = 0
        
#         return {
#             "success": True,
#             "session_data": session_data,
#             "is_complete": self.is_complete(session_data)
#         }
    
#     def is_complete(self, session_data: Dict[str, Any]) -> bool:
#         """Check if interview is complete"""
#         current_phase = session_data.get("current_phase", 0)
#         phases = session_data.get("phases", [])
        
#         if current_phase >= len(phases):
#             return True
        
#         if current_phase == len(phases) - 1:
#             # Last phase - check if all questions answered
#             current_question = session_data.get("current_question", 0)
#             last_phase = phases[-1]
#             questions = last_phase.get("questions", [])
#             return current_question >= len(questions)
        
#         return False
    
#     def generate_follow_up(self, question: str, answer: str) -> str:
#         """Generate follow-up question based on user's answer"""
#         prompt = f"""Generate ONE follow-up question based on:
#         Original Q: {question}
#         Response: {answer[:300]}
#         Keep it relevant and probing for more depth or specific examples."""
        
#         response = self.client.chat.completions.create(
#             model="gpt-4",
#             messages=[
#                 {"role": "system", "content": "You are an interview agent that creates insightful follow-up questions."},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0.5,
#             max_tokens=100
#         )
        
#         return response.choices[0].message.content.strip()
    
#     def evaluate_answer_quality(self, answer: str) -> bool:
#         """Determine if answer needs follow-up based on depth and specificity"""
#         if len(answer.split()) < 20:  # Too short
#             return True
            
#         # Use LLM to assess quality
#         prompt = f"""Assess if this response needs a follow-up question (YES/NO answer only):
#         Response: {answer[:300]}
        
#         Consider:
#         - Does it include specific examples?
#         - Does it have emotional depth or personal reflection?
#         - Does it provide sufficient detail?
#         """
        
#         response = self.client.chat.completions.create(
#             model="gpt-4",
#             messages=[
#                 {"role": "system", "content": "You evaluate interview answer quality and respond only with YES or NO."},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0.3,
#             max_tokens=10
#         )
        
#         return "YES" in response.choices[0].message.content.upper()
    
#     def _complete_tier_if_done(self) -> None:
#         """Mark tier as completed if all questions are answered"""
#         for tier_name, tier in self.tier_questions.items():
#             questions = tier.get("questions", [])
#             if tier.get("status") == "in_process" and all(
#                 q.get("qest") == "answered" for q in questions
#             ):
#                 tier["status"] = "completed"
#                 self._save_profiles()
#                 break



from openai import OpenAI
from app.core.config import get_settings
from app.core.firebase import get_firestore_client
from typing import List, Dict, Any, Optional
import uuid
import json
from datetime import datetime

class InterviewAgent:
    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.db = get_firestore_client()
        
        # Firestore collections
        self.master_collection = "user_collection"
        self.master_doc_id = "profile_strcuture.json"
        self.tiers_collection = "question_collection"
        self.tiers_doc_id = "general_tiered_questions.json"
        
        # Load master profile and tier questions from Firestore
        self.master_profile = self._load_master_profile()
        self.tier_questions = self._load_tier_questions()
    
    def _load_master_profile(self) -> Dict[str, Any]:
        """Load master profile structure from Firestore"""
        try:
            doc_ref = self.db.collection(self.master_collection).document(self.master_doc_id)
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict()
            else:
                return {}
        except Exception as e:
            print(f"Error loading master profile: {e}")
            return {}
    
    def _load_tier_questions(self) -> Dict[str, Any]:
        """Load tier questions from Firestore"""
        try:
            doc_ref = self.db.collection(self.tiers_collection).document(self.tiers_doc_id)
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict()
            else:
                return {}
        except Exception as e:
            print(f"Error loading tier questions: {e}")
            return {}
    
    def get_pending_questions_by_field(self, tier_name: str = "tier1") -> List[Dict[str, Any]]:
        """Get all pending questions from a specific tier with enhanced details"""
        tier_data = self.tier_questions.get(tier_name, {})
        questions = tier_data.get("questions", [])
        
        # Filter only pending questions and enhance with additional metadata
        pending_questions = []
        for i, q in enumerate(questions):
            if q.get("qest") == "pending":
                enhanced_question = {
                    **q,
                    "question_index": i,
                    "tier_name": tier_name,
                    "created_at": q.get("created_at", datetime.utcnow().isoformat()),
                    "updated_at": q.get("updated_at", datetime.utcnow().isoformat()),
                    "metadata": {
                        "estimated_time": q.get("estimated_time", 2),  # minutes
                        "difficulty_level": q.get("difficulty_level", "medium"),
                        "tags": q.get("tags", []),
                        "follow_up_enabled": q.get("follow_up_enabled", True)
                    }
                }
                pending_questions.append(enhanced_question)
        
        return pending_questions
    
    def get_tier_details(self, tier_name: str) -> Dict[str, Any]:
        """Get comprehensive details about a specific tier"""
        tier_data = self.tier_questions.get(tier_name, {})
        
        if not tier_data:
            return {}
        
        questions = tier_data.get("questions", [])
        total_questions = len(questions)
        answered_questions = len([q for q in questions if q.get("qest") == "answered"])
        pending_questions = len([q for q in questions if q.get("qest") == "pending"])
        
        return {
            "tier_name": tier_name,
            "metadata": {
                "description": tier_data.get("description", ""),
                "category": tier_data.get("category", "general"),
                "priority": tier_data.get("priority", 1),
                "status": tier_data.get("status", "pending"),
                "created_at": tier_data.get("created_at", ""),
                "updated_at": tier_data.get("updated_at", "")
            },
            "statistics": {
                "total_questions": total_questions,
                "answered_questions": answered_questions,
                "pending_questions": pending_questions,
                "completion_percentage": round((answered_questions / total_questions) * 100, 2) if total_questions > 0 else 0
            },
            "questions_by_status": {
                "pending": [q for q in questions if q.get("qest") == "pending"],
                "answered": [q for q in questions if q.get("qest") == "answered"],
                "skipped": [q for q in questions if q.get("qest") == "skipped"]
            },
            "fields_covered": list(set([q.get("field") for q in questions if q.get("field")])),
            "categories": list(set([q.get("category", "general") for q in questions]))
        }
    
    def get_all_tiers_summary(self) -> Dict[str, Any]:
        """Get summary of all available tiers"""
        summary = {
            "total_tiers": len(self.tier_questions),
            "tiers": {},
            "overall_stats": {
                "total_questions": 0,
                "total_answered": 0,
                "total_pending": 0,
                "completion_percentage": 0
            }
        }
        
        total_questions = 0
        total_answered = 0
        total_pending = 0
        
        for tier_name, tier_data in self.tier_questions.items():
            questions = tier_data.get("questions", [])
            tier_total = len(questions)
            tier_answered = len([q for q in questions if q.get("qest") == "answered"])
            tier_pending = len([q for q in questions if q.get("qest") == "pending"])
            
            summary["tiers"][tier_name] = {
                "name": tier_name,
                "status": tier_data.get("status", "pending"),
                "total_questions": tier_total,
                "answered_questions": tier_answered,
                "pending_questions": tier_pending,
                "completion_percentage": round((tier_answered / tier_total) * 100, 2) if tier_total > 0 else 0,
                "priority": tier_data.get("priority", 1),
                "category": tier_data.get("category", "general")
            }
            
            total_questions += tier_total
            total_answered += tier_answered
            total_pending += tier_pending
        
        summary["overall_stats"] = {
            "total_questions": total_questions,
            "total_answered": total_answered,
            "total_pending": total_pending,
            "completion_percentage": round((total_answered / total_questions) * 100, 2) if total_questions > 0 else 0
        }
    
    def set_nested(self, data: Dict[str, Any], dotted_path: str, value: Any) -> None:
        """Set nested dictionary value using dot notation"""
        keys = dotted_path.split('.')
        d = data
        for key in keys[:-1]:
            if key not in d or not isinstance(d[key], dict):
                d[key] = {}
            d = d[key]
        d[keys[-1]] = value
    
    def apply_responses_to_profile(self, responses: Dict[str, Any], tier_name: str = "tier1") -> Dict[str, Any]:
        """Apply user responses to both master profile and tier questions with detailed tracking"""
        questions = self.tier_questions.get(tier_name, {}).get("questions", [])
        applied_responses = {}
        
        for q in questions:
            field = q.get("field")
            if q.get("qest") == "pending" and field in responses:
                # Update nested master profile
                if "generalprofile" in field:
                    # Remove the generalprofile prefix for nested setting
                    nested_path = field.replace("generalprofile.", "")
                    self.set_nested(
                        self.master_profile.get("generalprofile", {}),
                        nested_path,
                        responses[field]
                    )
                else:
                    # Handle other profile sections
                    self.set_nested(self.master_profile, field, responses[field])
                
                # Mark question as answered with timestamp
                q["qest"] = "answered"
                q["answered_at"] = datetime.utcnow().isoformat()
                q["answer_value"] = responses[field]
                
                applied_responses[field] = {
                    "value": responses[field],
                    "question": q.get("question"),
                    "tier": tier_name,
                    "answered_at": q["answered_at"]
                }
        
        # Update tier status if all questions are answered
        self._update_tier_status(tier_name)
        
        # Save both profiles back to Firestore
        self._save_profiles()
        
        return applied_responses
    
    def _update_tier_status(self, tier_name: str) -> None:
        """Update tier status based on question completion"""
        tier_data = self.tier_questions.get(tier_name, {})
        questions = tier_data.get("questions", [])
        
        if not questions:
            return
        
        total_questions = len(questions)
        answered_questions = len([q for q in questions if q.get("qest") == "answered"])
        
        if answered_questions == 0:
            tier_data["status"] = "pending"
        elif answered_questions == total_questions:
            tier_data["status"] = "completed"
            tier_data["completed_at"] = datetime.utcnow().isoformat()
        else:
            tier_data["status"] = "in_progress"
        
        tier_data["updated_at"] = datetime.utcnow().isoformat()
        tier_data["progress"] = {
            "answered": answered_questions,
            "total": total_questions,
            "percentage": round((answered_questions / total_questions) * 100, 2)
        }
    
    def _save_profiles(self) -> None:
        """Save both master profile and tier questions to Firestore"""
        try:
            # Save master profile
            self.db.collection(self.master_collection).document(self.master_doc_id).set(self.master_profile)
            
            # Save tier questions
            self.db.collection(self.tiers_collection).document(self.tiers_doc_id).set(self.tier_questions)
            
        except Exception as e:
            print(f"Error saving profiles: {e}")
    
    # In your InterviewAgent class
def create_session(self, user_id, questions):
    """
    Create session with proper validation
    """
    try:
        session_id = str(uuid.uuid4())
        
        # Validate questions
        if not questions:
            raise ValueError("No questions provided for session creation")
        
        # Create phases from questions
        phases = [{
            "name": "Interview Phase 1",
            "tier_name": "tier1",
            "questions": questions,
            "instructions": "Please answer the following questions thoughtfully."
        }]
        
        session_data = {
            "session_id": session_id,
            "user_id": user_id,
            "current_phase": 0,
            "current_question": 0,
            "follow_up_depth": 0,
            "conversation": [],
            "phases": phases,
            "created_at": datetime.utcnow().isoformat(),
            "status": "active"
        }
        
        # DEBUG: Log session creation
        print(f"DEBUG - Created session:")
        print(f"  Session ID: {session_id}")
        print(f"  Total phases: {len(phases)}")
        print(f"  Questions in phase 0: {len(phases[0]['questions'])}")
        print(f"  First question: {phases[0]['questions'][0].get('question', 'None')}")
        
        return session_data
        
    except Exception as e:
        print(f"DEBUG - Exception in create_session: {str(e)}")
        raise
    
    def _calculate_phase_difficulty(self, questions_list: List[Dict[str, Any]]) -> str:
        """Calculate overall difficulty level for a phase"""
        difficulty_scores = {"easy": 1, "medium": 2, "hard": 3}
        difficulties = [q.get("metadata", {}).get("difficulty_level", "medium") for q in questions_list]
        
        if not difficulties:
            return "medium"
        
        avg_score = sum(difficulty_scores.get(d, 2) for d in difficulties) / len(difficulties)
        
        if avg_score <= 1.5:
            return "easy"
        elif avg_score <= 2.5:
            return "medium"
        else:
            return "hard"
    
    # In your InterviewAgent class
def get_current_question(self, session_data):
    """
    Get the current question with proper bounds checking
    """
    try:
        current_phase = session_data.get('current_phase', 0)
        current_question = session_data.get('current_question', 0)
        phases = session_data.get('phases', [])
        
        # Check if we have valid phases
        if not phases:
            print("DEBUG - No phases in session data")
            return None
        
        # Check if current phase is valid
        if current_phase >= len(phases):
            print(f"DEBUG - Current phase {current_phase} >= phases length {len(phases)}")
            return None
        
        current_phase_data = phases[current_phase]
        questions = current_phase_data.get('questions', [])
        
        # Check if we have questions in current phase
        if not questions:
            print(f"DEBUG - No questions in phase {current_phase}")
            return None
        
        # Check if current question index is valid
        if current_question >= len(questions):
            print(f"DEBUG - Current question {current_question} >= questions length {len(questions)}")
            return None
        
        question_data = questions[current_question]
        
        # Ensure question_data has required fields
        if not question_data.get('question'):
            print(f"DEBUG - Question data missing 'question' field: {question_data}")
            return None
        
        # Return complete question data
        return {
            'question': question_data['question'],
            'field': question_data.get('field', 'unknown'),
            'phase': current_phase,
            'tier_name': current_phase_data.get('tier_name', 'tier1'),
            'question_index': current_question,
            'question_id': question_data.get('id', ''),
            'type': question_data.get('type', 'text'),
            'category': question_data.get('category', 'general')
        }
        
    except Exception as e:
        print(f"DEBUG - Exception in get_current_question: {str(e)}")
        return None
    
    def submit_answer(self, session_data: Dict[str, Any], answer: str) -> Dict[str, Any]:
        """Submit an answer and advance to next question with enhanced tracking"""
        current_question_data = self.get_current_question(session_data)
        
        if not current_question_data:
            return {"success": False, "message": "No current question found"}
        
        # Save the answer with enhanced metadata
        field = current_question_data.get("field")
        tier_name = current_question_data.get("tier_name", "tier1")
        
        # Apply response to profile
        applied_responses = self.apply_responses_to_profile({field: answer}, tier_name)
        
        # Add to conversation history with enhanced data
        conversation_entry = {
            "question": current_question_data.get("question"),
            "answer": answer,
            "field": field,
            "phase": current_question_data.get("phase"),
            "tier": tier_name,
            "timestamp": datetime.utcnow().isoformat(),
            "question_metadata": current_question_data.get("question_metadata", {}),
            "answer_metadata": {
                "word_count": len(answer.split()),
                "character_count": len(answer),
                "answer_quality": self._assess_answer_quality(answer),
                "processing_time": None,  # Could be calculated if needed
                "follow_up_depth": session_data.get("follow_up_depth", 0)
            },
            "applied_to_profile": field in applied_responses
        }
        
        session_data["conversation"].append(conversation_entry)
        
        # Advance to next question
        session_data["current_question"] += 1
        session_data["follow_up_depth"] = 0  # Reset follow-up depth
        
        # Check if phase is complete
        current_phase = session_data.get("current_phase", 0)
        phases = session_data.get("phases", [])
        
        if current_phase < len(phases):
            phase = phases[current_phase]
            questions = phase.get("questions", [])
            
            if session_data["current_question"] >= len(questions):
                # Move to next phase
                session_data["current_phase"] += 1
                session_data["current_question"] = 0
        
        return {
            "success": True,
            "session_data": session_data,
            "is_complete": self.is_complete(session_data),
            "applied_responses": applied_responses,
            "answer_metadata": conversation_entry["answer_metadata"]
        }
    
    def _assess_answer_quality(self, answer: str) -> str:
        """Assess the quality of an answer based on length and content"""
        word_count = len(answer.split())
        
        if word_count < 5:
            return "very_short"
        elif word_count < 15:
            return "short"
        elif word_count < 50:
            return "medium"
        elif word_count < 100:
            return "detailed"
        else:
            return "very_detailed"
    
    def is_complete(self, session_data: Dict[str, Any]) -> bool:
        """Check if interview is complete"""
        current_phase = session_data.get("current_phase", 0)
        phases = session_data.get("phases", [])
        
        if current_phase >= len(phases):
            return True
        
        if current_phase == len(phases) - 1:
            # Last phase - check if all questions answered
            current_question = session_data.get("current_question", 0)
            last_phase = phases[-1]
            questions = last_phase.get("questions", [])
            return current_question >= len(questions)
        
        return False
    
    def generate_follow_up(self, question: str, answer: str, context: Dict[str, Any] = None) -> str:
        """Generate follow-up question based on user's answer with enhanced context"""
        context_info = ""
        if context:
            tier = context.get("tier", "")
            field = context.get("field", "")
            context_info = f"Tier: {tier}, Field: {field}. "
        
        prompt = f"""Generate ONE insightful follow-up question based on:
        {context_info}
        Original Question: {question}
        User's Response: {answer[:300]}
        
        The follow-up should:
        - Probe deeper into their response
        - Ask for specific examples or details
        - Explore emotional aspects or motivations
        - Be conversational and engaging
        - Stay relevant to the original question's intent
        
        Keep it under 25 words."""
        
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an empathetic interview agent that creates insightful follow-up questions to understand users better."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=100
        )
        
        return response.choices[0].message.content.strip()
    
    def evaluate_answer_quality(self, answer: str, question_context: Dict[str, Any] = None) -> bool:
        """Determine if answer needs follow-up based on depth and specificity"""
        word_count = len(answer.split())
        
        # Basic length check
        if word_count < 10:
            return True
        
        # Check for specific indicators that suggest need for follow-up
        shallow_indicators = [
            "yes", "no", "maybe", "i don't know", "not sure", "ok", "fine", "good", "bad"
        ]
        
        answer_lower = answer.lower()
        if any(indicator in answer_lower for indicator in shallow_indicators) and word_count < 20:
            return True
        
        # Use LLM to assess quality for more nuanced evaluation
        prompt = f"""Assess if this interview response needs a follow-up question (respond with only YES or NO):
        
        Response: {answer[:300]}
        
        Consider:
        - Does it include specific examples or details?
        - Does it show personal reflection or depth?
        - Does it fully address what was asked?
        - Would a follow-up help uncover more valuable insights?
        
        Response length: {word_count} words
        """
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You evaluate interview responses and determine if follow-up questions would be valuable. Respond only with YES or NO."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=10
            )
            
            return "YES" in response.choices[0].message.content.upper()
        except Exception as e:
            print(f"Error evaluating answer quality: {e}")
            # Fallback to simple heuristic
            return word_count < 30
    
    def get_session_analytics(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive analytics for a session"""
        conversation = session_data.get("conversation", [])
        
        if not conversation:
            return {}
        
        # Calculate various metrics
        total_answers = len(conversation)
        word_counts = [entry.get("answer_metadata", {}).get("word_count", 0) for entry in conversation]
        
        analytics = {
            "response_analytics": {
                "total_responses": total_answers,
                "average_word_count": sum(word_counts) / len(word_counts) if word_counts else 0,
                "total_words": sum(word_counts),
                "longest_response": max(word_counts) if word_counts else 0,
                "shortest_response": min(word_counts) if word_counts else 0
            },
            "quality_distribution": {},
            "tier_distribution": {},
            "category_distribution": {},
            "follow_up_stats": {
                "total_follow_ups": len([entry for entry in conversation if entry.get("answer_metadata", {}).get("follow_up_depth", 0) > 0]),
                "follow_up_rate": 0
            },
            "completion_stats": {
                "fields_completed": len(set([entry.get("field") for entry in conversation if entry.get("field")])),
                "phases_completed": len(set([entry.get("phase") for entry in conversation if entry.get("phase")])),
                "tiers_involved": len(set([entry.get("tier") for entry in conversation if entry.get("tier")]))
            }
        }
        
        # Calculate quality distribution
        quality_counts = {}
        for entry in conversation:
            quality = entry.get("answer_metadata", {}).get("answer_quality", "unknown")
            quality_counts[quality] = quality_counts.get(quality, 0) + 1
        analytics["quality_distribution"] = quality_counts
        
        # Calculate tier distribution
        tier_counts = {}
        for entry in conversation:
            tier = entry.get("tier", "unknown")
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        analytics["tier_distribution"] = tier_counts
        
        # Calculate category distribution
        category_counts = {}
        for entry in conversation:
            category = entry.get("question_metadata", {}).get("category", "unknown")
            category_counts[category] = category_counts.get(category, 0) + 1
        analytics["category_distribution"] = category_counts
        
        # Calculate follow-up rate
        if total_answers > 0:
            analytics["follow_up_stats"]["follow_up_rate"] = round(
                (analytics["follow_up_stats"]["total_follow_ups"] / total_answers) * 100, 2
            )
        
        return analytics
    
    def _complete_tier_if_done(self, tier_name: str = None) -> Dict[str, Any]:
        """Mark tier as completed if all questions are answered and return completion status"""
        completion_status = {}
        
        tiers_to_check = [tier_name] if tier_name else list(self.tier_questions.keys())
        
        for tier in tiers_to_check:
            if tier not in self.tier_questions:
                continue
                
            tier_data = self.tier_questions[tier]
            questions = tier_data.get("questions", [])
            
            if not questions:
                continue
            
            total_questions = len(questions)
            answered_questions = len([q for q in questions if q.get("qest") == "answered"])
            
            if answered_questions == total_questions and tier_data.get("status") != "completed":
                tier_data["status"] = "completed"
                tier_data["completed_at"] = datetime.utcnow().isoformat()
                completion_status[tier] = {
                    "newly_completed": True,
                    "completion_time": tier_data["completed_at"],
                    "total_questions": total_questions
                }
            elif answered_questions > 0 and tier_data.get("status") == "pending":
                tier_data["status"] = "in_progress"
                completion_status[tier] = {
                    "newly_completed": False,
                    "status": "in_progress",
                    "progress": f"{answered_questions}/{total_questions}"
                }
        
        if completion_status:
            self._save_profiles()
        
        return completion_status