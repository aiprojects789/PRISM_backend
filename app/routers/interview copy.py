# # app/routers/interview.py - Complete User-Specific Profile Management

# from fastapi import APIRouter, Depends, HTTPException, status
# from fastapi.security import HTTPAuthorizationCredentials
# from pydantic import BaseModel
# from typing import Dict, Any, List, Optional
# import uuid
# import copy
# from datetime import datetime
# from openai import OpenAI
# from langchain_community.chat_models import ChatOpenAI
# from langchain.schema import SystemMessage, HumanMessage

# from app.core.security import get_current_user, security
# from app.core.firebase import get_firestore_client
# from app.core.config import get_settings
# from app.routers.conversations import save_conversation_message

# router = APIRouter()

# # Pydantic models for the interview
# class InterviewStartRequest(BaseModel):
#     user_id: str
#     selected_category: str = "Movies"  # Movies, Food, Travel

# class InterviewAnswerRequest(BaseModel):
#     session_id: str
#     answer: str

# class InterviewStatusResponse(BaseModel):
#     session_id: str
#     is_complete: bool
#     current_tier_idx: int
#     current_phase: str
#     current_question: Optional[Dict[str, Any]]
#     progress: Dict[str, Any]

# class TieredInterviewAgent:
#     def __init__(self, db, openai_key, selected_category="Movies", user_id=None):
#         if not user_id:
#             raise ValueError("user_id is required for TieredInterviewAgent")
            
#         self.db = db
#         self.openai_key = openai_key
#         self.user_id = user_id  # 🔥 CRITICAL: Always require user_id
#         self.selected_category = selected_category
#         self.current_tier_idx = 0
#         self.current_phase = 'general'
#         self.current_q_idx = 0
#         self.tier_keys = []
#         self.general_questions = {}
#         self.category_questions = {}
#         self.profile_structure = {}
#         self.conversation = []
#         self.follow_up_count = 0
#         self.started_at = datetime.utcnow()
#         self.completed_at = None

#         # Category mapping
#         selected = selected_category.lower()
#         cat_map = {
#             'movies': 'moviesAndTV_tiered_questions.json',
#             'food': 'foodAndDining_tiered_questions.json',
#             'travel': 'travel_tiered_questions.json'
#         }
#         self.cat_doc_id = cat_map.get(selected, 'moviesAndTV_tiered_questions.json')
        
#         self.load_data()

#     def load_data(self):
#         """Load questions and USER-SPECIFIC profile data from Firestore"""
#         try:
#             print(f"📚 Loading data for user: {self.user_id}")
            
#             # Load general questions (create user-specific copy)
#             gen_doc = self.db.collection("question_collection").document("general_tiered_questions.json").get()
#             if gen_doc.exists:
#                 self.general_questions = self._create_user_specific_questions(gen_doc.to_dict(), "general")
#             else:
#                 self.general_questions = {}
            
#             # Load category questions (create user-specific copy)
#             cat_doc = self.db.collection("question_collection").document(self.cat_doc_id).get()
#             if cat_doc.exists:
#                 self.category_questions = self._create_user_specific_questions(cat_doc.to_dict(), "category")
#             else:
#                 self.category_questions = {}
            
#             # Load USER-SPECIFIC profile structure
#             self.profile_structure = self._load_user_profile_structure()
            
#             # Extract tier keys
#             if self.general_questions:
#                 self.tier_keys = sorted(
#                     [k for k in self.general_questions.keys() if k.startswith('tier')],
#                     key=lambda x: int(x.replace('tier', ''))
#                 )
#             else:
#                 self.tier_keys = ["tier1", "tier2", "tier3"]

#             print(f"✅ Data loaded for user {self.user_id}: {len(self.tier_keys)} tiers")

#         except Exception as e:
#             print(f"❌ Failed to load data for user {self.user_id}: {e}")
#             self.general_questions = {}
#             self.category_questions = {}
#             self.profile_structure = {}
#             self.tier_keys = ["tier1", "tier2", "tier3"]

#         self.pick_up_where_left_off()

#     def _create_user_specific_questions(self, template_questions: dict, question_type: str) -> dict:
#         """Create user-specific copy of questions from template"""
#         try:
#             # Check if user already has their own copy
#             user_doc_id = f"{self.user_id}_{question_type}_questions.json"
#             user_doc = self.db.collection("user_questions").document(user_doc_id).get()
            
#             if user_doc.exists:
#                 # User already has their own copy, load it
#                 print(f"✅ Loading existing {question_type} questions for user {self.user_id}")
#                 return user_doc.to_dict()
#             else:
#                 # Create new user-specific copy from template
#                 print(f"🆕 Creating new {question_type} questions for user {self.user_id}")
#                 user_questions = self._deep_copy_questions(template_questions)
                
#                 # Add user metadata
#                 user_questions["user_id"] = self.user_id
#                 user_questions["created_at"] = datetime.utcnow().isoformat()
#                 user_questions["updated_at"] = datetime.utcnow().isoformat()
#                 user_questions["question_type"] = question_type
#                 user_questions["category"] = self.selected_category if question_type == "category" else "general"
                
#                 # Save user-specific copy
#                 self.db.collection("user_questions").document(user_doc_id).set(user_questions)
                
#                 return user_questions
                
#         except Exception as e:
#             print(f"❌ Error creating user-specific questions: {e}")
#             return template_questions  # Fallback to template

#     def _deep_copy_questions(self, questions: dict) -> dict:
#         """Create a deep copy of questions and reset all statuses to pending"""
#         user_questions = copy.deepcopy(questions)
        
#         # Reset all question statuses to pending for new user
#         for tier_key, tier_data in user_questions.items():
#             if isinstance(tier_data, dict) and 'questions' in tier_data:
#                 # Reset tier status
#                 tier_data['status'] = 'pending'
#                 if 'completed_at' in tier_data:
#                     del tier_data['completed_at']
                
#                 # Reset all questions to pending
#                 for question in tier_data.get('questions', []):
#                     if isinstance(question, dict):
#                         question['qest'] = 'pending'
#                         # Remove any previous answers
#                         for key in ['answer', 'answered_at']:
#                             if key in question:
#                                 del question[key]
        
#         return user_questions

#     def _load_user_profile_structure(self) -> dict:
#         """Load USER-SPECIFIC profile structure"""
#         try:
#             # User-specific profile document
#             profile_doc_id = f"{self.user_id}_profile_structure.json"
#             profile_doc = self.db.collection("user_profiles").document(profile_doc_id).get()
            
#             if profile_doc.exists:
#                 print(f"✅ Loading existing profile structure for user {self.user_id}")
#                 return profile_doc.to_dict()
#             else:
#                 # Create new user profile from template
#                 print(f"🆕 Creating new profile structure for user {self.user_id}")
                
#                 # Load the profile template
#                 template_doc = self.db.collection("user_collection").document("profile_strcuture.json").get()
                
#                 if template_doc.exists:
#                     template_profile = template_doc.to_dict()
#                 else:
#                     # Create basic profile structure if template doesn't exist
#                     template_profile = {
#                         "generalprofile": {},
#                         "recommendationProfiles": {
#                             self.selected_category.lower(): {}
#                         },
#                         "simulationPreferences": {}
#                     }
                
#                 # Add user metadata
#                 user_profile = {
#                     **template_profile,
#                     "user_id": self.user_id,
#                     "created_at": datetime.utcnow().isoformat(),
#                     "updated_at": datetime.utcnow().isoformat(),
#                     "selected_category": self.selected_category,
#                     "version": "1.0"
#                 }
                
#                 # Save user-specific profile
#                 self.db.collection("user_profiles").document(profile_doc_id).set(user_profile)
                
#                 return user_profile
                
#         except Exception as e:
#             print(f"❌ Error loading user profile structure: {e}")
#             return {}

#     def pick_up_where_left_off(self):
#         """Find the first tier that is not completed and set it to in_process"""
#         for idx, tier_key in enumerate(self.tier_keys):
#             status = self.general_questions.get(tier_key, {}).get('status', '')
#             if status == 'completed':
#                 continue

#             self.current_tier_idx = idx
#             if status != 'in_process':
#                 self.general_questions[tier_key]['status'] = 'in_process'
#             return

#         # If no tier left, mark interview complete
#         self.current_tier_idx = len(self.tier_keys)

#     def get_current_tier_key(self):
#         """Get current tier key"""
#         if self.current_tier_idx < len(self.tier_keys):
#             return self.tier_keys[self.current_tier_idx]
#         return None

#     def get_pending_questions(self, dataset, tier_key):
#         """Get pending questions for a specific tier and dataset"""
#         if not dataset or not tier_key or tier_key not in dataset:
#             return []
            
#         tier = dataset.get(tier_key, {})
        
#         # For general questions, respect the tier status
#         if dataset == self.general_questions:
#             tier_status = tier.get('status', '')
#             if tier_status != 'in_process' and tier_status != '':
#                 return []
        
#         questions = tier.get('questions', [])
#         if not isinstance(questions, list):
#             return []
            
#         return [q for q in questions if isinstance(q, dict) and q.get('qest') == 'pending']
    
#     def get_current_question(self):
#         """Get the current question to be asked"""
#         tier_key = self.get_current_tier_key()
#         if not tier_key:
#             return None
            
#         if self.current_phase == 'general':
#             pending = self.get_pending_questions(self.general_questions, tier_key)
#             if pending and 0 <= self.current_q_idx < len(pending):
#                 question_data = pending[self.current_q_idx]
#                 return {
#                     'question': question_data.get('question', ''),
#                     'field': question_data.get('field', ''),
#                     'phase': 'general',
#                     'tier': tier_key,
#                     'question_id': question_data.get('id', ''),
#                     'category': question_data.get('category', 'general'),
#                     'user_id': self.user_id
#                 }
#         elif self.current_phase == 'category':
#             pending = self.get_pending_questions(self.category_questions, tier_key)
#             if pending and 0 <= self.current_q_idx < len(pending):
#                 question_data = pending[self.current_q_idx]
#                 return {
#                     'question': question_data.get('question', ''),
#                     'field': question_data.get('field', ''),
#                     'phase': 'category',
#                     'tier': tier_key,
#                     'question_id': question_data.get('id', ''),
#                     'category': question_data.get('category', self.selected_category.lower()),
#                     'user_id': self.user_id
#                 }
        
#         return None

#     def regenerate_question_with_motivation(self, next_question: str, user_response: str = None) -> str:
#         """Generate a conversational follow-up by acknowledging the user's response"""
#         try:
#             client = OpenAI(api_key=self.openai_key)

#             prompt = f"Next question: {next_question}\n"
#             if user_response:
#                 prompt += f"User's previous response: {user_response}\n"
#             prompt += (
#                 "Please write a natural, conversational transition that acknowledges the user's response "
#                 "and leads into the next question. Keep it warm, curious, and supportive."
#             )

#             response = client.chat.completions.create(
#                 model="gpt-4o-mini",
#                 messages=[
#                     {"role": "system", "content": "You are a friendly, engaging interviewer having a casual, supportive conversation. When provided with a user's previous response and a next question, create a natural, conversational transition. Acknowledge or positively reflect on the user's response, and then smoothly ask the next question. Keep the tone friendly, curious, and encouraging, and avoid robotic phrasing. Do not rigidly repeat the question; weave it naturally into your words."},
#                     {"role": "user", "content": prompt}
#                 ],
#                 temperature=0.7,
#                 max_tokens=150
#             )
            
#             return response.choices[0].message.content.strip()
#         except Exception as e:
#             print(f"Error generating motivated question: {e}")
#             return next_question  # Fallback to original question

#     def submit_answer(self, answer):
#         """Submit answer and update profile structure"""
#         tier_key = self.get_current_tier_key()
#         if not tier_key:
#             return False
            
#         current_q = self.get_current_question()
#         if not current_q:
#             return False
        
#         # Update the question status in the appropriate dataset
#         if self.current_phase == 'general':
#             dataset = self.general_questions
#         else:
#             dataset = self.category_questions
            
#         pending = self.get_pending_questions(dataset, tier_key)
#         if pending and 0 <= self.current_q_idx < len(pending):
#             # Find the question in the original dataset and mark as answered
#             question_to_update = pending[self.current_q_idx]
#             question_text = question_to_update.get('question', '')
            
#             tier_questions = dataset.get(tier_key, {}).get('questions', [])
#             for q in tier_questions:
#                 if q.get('question') == question_text:
#                     q['qest'] = 'answered'
#                     q['answered_at'] = datetime.utcnow().isoformat()
#                     q['answer'] = answer
#                     q['user_id'] = self.user_id  # Track which user answered
#                     break
            
#             # Update profile structure with the answer
#             field_path = current_q.get('field', '')
#             if field_path:
#                 self.update_profile_structure(field_path, answer)
            
#             # Add to conversation history with enhanced metadata
#             conversation_entry = {
#                 "question": current_q.get('question'),
#                 "answer": answer,
#                 "field": field_path,
#                 "phase": self.current_phase,
#                 "tier": tier_key,
#                 "timestamp": datetime.utcnow().isoformat(),
#                 "question_id": current_q.get('question_id', ''),
#                 "category": current_q.get('category', 'general'),
#                 "user_id": self.user_id,
#                 "answer_metadata": {
#                     "word_count": len(answer.split()),
#                     "character_count": len(answer),
#                     "answer_quality": self._assess_answer_quality(answer)
#                 }
#             }
            
#             self.conversation.append(conversation_entry)
            
#             # Move to next question or phase
#             self.advance_to_next()
            
#             return True
        
#         return False

#     def _assess_answer_quality(self, answer: str) -> str:
#         """Assess the quality of an answer based on length and content"""
#         word_count = len(answer.split())
        
#         if word_count < 5:
#             return "very_short"
#         elif word_count < 15:
#             return "short"
#         elif word_count < 50:
#             return "medium"
#         elif word_count < 100:
#             return "detailed"
#         else:
#             return "very_detailed"

#     def update_profile_structure(self, field_path, answer):
#         """Update profile structure with the answer"""
#         if not field_path or not isinstance(field_path, str):
#             return
            
#         keys = field_path.split('.')
#         current = self.profile_structure
        
#         try:
#             for key in keys[:-1]:
#                 if key not in current:
#                     current[key] = {}
#                 current = current[key]
            
#             final_key = keys[-1]
#             if final_key in current and isinstance(current[final_key], dict):
#                 current[final_key]['value'] = answer
#                 current[final_key]['updated_at'] = datetime.utcnow().isoformat()
#                 current[final_key]['user_id'] = self.user_id
#             else:
#                 if final_key not in current:
#                     current[final_key] = {}
#                 if isinstance(current[final_key], dict):
#                     current[final_key]['value'] = answer
#                     current[final_key]['updated_at'] = datetime.utcnow().isoformat()
#                     current[final_key]['user_id'] = self.user_id
#                 else:
#                     current[final_key] = {
#                         'value': answer,
#                         'updated_at': datetime.utcnow().isoformat(),
#                         'user_id': self.user_id
#                     }
#         except (KeyError, TypeError, AttributeError) as e:
#             print(f"Error updating profile structure for field '{field_path}': {e}")
#             return

#     def advance_to_next(self):
#         """Advance to next question, phase, or tier"""
#         tier_key = self.get_current_tier_key()
#         if not tier_key:
#             return
        
#         if self.current_phase == 'general':
#             pending = self.get_pending_questions(self.general_questions, tier_key)
#             if pending and self.current_q_idx + 1 < len(pending):
#                 self.current_q_idx += 1
#             else:
#                 # Move to category phase
#                 self.current_phase = 'category'
#                 self.current_q_idx = 0
                
#                 cat_pending = self.get_pending_questions(self.category_questions, tier_key)
#                 if not cat_pending:
#                     self.complete_current_tier()
#                     self.advance_to_next_tier()
        
#         elif self.current_phase == 'category':
#             pending = self.get_pending_questions(self.category_questions, tier_key)
#             if pending and self.current_q_idx + 1 < len(pending):
#                 self.current_q_idx += 1
#             else:
#                 self.complete_current_tier()
#                 self.advance_to_next_tier()

#     def complete_current_tier(self):
#         """Mark current tier as completed"""
#         tier_key = self.get_current_tier_key()
#         if tier_key:
#             if tier_key in self.general_questions:
#                 self.general_questions[tier_key]['status'] = 'completed'
#                 self.general_questions[tier_key]['completed_at'] = datetime.utcnow().isoformat()
#                 self.general_questions[tier_key]['completed_by'] = self.user_id
            
#             if tier_key in self.category_questions:
#                 self.category_questions[tier_key]['status'] = 'completed'
#                 self.category_questions[tier_key]['completed_at'] = datetime.utcnow().isoformat()
#                 self.category_questions[tier_key]['completed_by'] = self.user_id

#     def advance_to_next_tier(self):
#         """Move to the next tier"""
#         if self.current_tier_idx + 1 < len(self.tier_keys):
#             self.current_tier_idx += 1
#             self.current_phase = 'general'
#             self.current_q_idx = 0
            
#             next_tier_key = self.get_current_tier_key()
#             if next_tier_key and next_tier_key in self.general_questions:
#                 self.general_questions[next_tier_key]['status'] = 'in_process'
#         else:
#             self.current_tier_idx = len(self.tier_keys)
#             self.completed_at = datetime.utcnow()

#     def is_complete(self):
#         """Check if interview is complete"""
#         return self.current_tier_idx >= len(self.tier_keys)

#     def save_to_firestore(self):
#         """Save USER-SPECIFIC data back to Firestore"""
#         try:
#             # Save user-specific profile structure
#             profile_doc_id = f"{self.user_id}_profile_structure.json"
#             self.profile_structure["updated_at"] = datetime.utcnow().isoformat()
#             self.profile_structure["user_id"] = self.user_id
#             self.db.collection("user_profiles").document(profile_doc_id).set(self.profile_structure)
            
#             # Save user-specific question collections
#             general_doc_id = f"{self.user_id}_general_questions.json"
#             self.general_questions["updated_at"] = datetime.utcnow().isoformat()
#             self.general_questions["user_id"] = self.user_id
#             self.db.collection("user_questions").document(general_doc_id).set(self.general_questions)
            
#             category_doc_id = f"{self.user_id}_category_questions.json"
#             self.category_questions["updated_at"] = datetime.utcnow().isoformat()
#             self.category_questions["user_id"] = self.user_id
#             self.db.collection("user_questions").document(category_doc_id).set(self.category_questions)
            
#             print(f"✅ Saved user-specific data for user {self.user_id}")
#             return True
#         except Exception as e:
#             print(f"❌ Failed to save user-specific data for user {self.user_id}: {e}")
#             return False

#     def to_dict(self):
#         """Convert agent state to dictionary for database storage"""
#         return {
#             "user_id": self.user_id,
#             "selected_category": self.selected_category,
#             "current_tier_idx": self.current_tier_idx,
#             "current_phase": self.current_phase,
#             "current_q_idx": self.current_q_idx,
#             "tier_keys": self.tier_keys,
#             "cat_doc_id": self.cat_doc_id,
#             "conversation": self.conversation,
#             "follow_up_count": self.follow_up_count,
#             "started_at": self.started_at.isoformat() if hasattr(self.started_at, 'isoformat') else str(self.started_at),
#             "completed_at": self.completed_at.isoformat() if self.completed_at and hasattr(self.completed_at, 'isoformat') else None,
#             "created_at": datetime.utcnow().isoformat(),
#             "updated_at": datetime.utcnow().isoformat()
#         }

#     @classmethod
#     def from_dict(cls, db, openai_key, data, selected_category="Movies"):
#         """Create agent from database data"""
#         user_id = data.get("user_id")
#         if not user_id:
#             raise ValueError("user_id is required to restore agent from database")
            
#         agent = cls(db, openai_key, selected_category, user_id)
        
#         # Restore state from database
#         agent.current_tier_idx = data.get("current_tier_idx", 0)
#         agent.current_phase = data.get("current_phase", 'general')
#         agent.current_q_idx = data.get("current_q_idx", 0)
#         agent.conversation = data.get("conversation", [])
#         agent.follow_up_count = data.get("follow_up_count", 0)
        
#         # Restore timestamps
#         started_at_str = data.get("started_at")
#         if started_at_str:
#             try:
#                 agent.started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
#             except:
#                 agent.started_at = datetime.utcnow()
        
#         completed_at_str = data.get("completed_at")
#         if completed_at_str:
#             try:
#                 agent.completed_at = datetime.fromisoformat(completed_at_str.replace('Z', '+00:00'))
#             except:
#                 agent.completed_at = None
        
#         return agent

# # 🔥 CRITICAL: Database helper functions for USER-SPECIFIC session management
# def save_interview_session(user_id: str, session_id: str, agent: TieredInterviewAgent, db):
#     """Save USER-SPECIFIC interview session to database"""
#     try:
#         session_data = {
#             "session_id": session_id,
#             "user_id": user_id,  # 🔥 CRITICAL: Always include user_id
#             "agent_state": agent.to_dict(),
#             "created_at": datetime.utcnow(),
#             "updated_at": datetime.utcnow(),
#             "is_active": True,
#             "status": "in_progress",
#             "metadata": {
#                 "selected_category": agent.selected_category,
#                 "current_tier": agent.current_tier_idx,
#                 "current_phase": agent.current_phase,
#                 "total_questions_answered": len(agent.conversation),
#                 "user_specific": True  # Flag to indicate this is user-specific
#             }
#         }
        
#         # Save to user-specific collection
#         db.collection("interview_sessions").document(session_id).set(session_data)
        
#         # Also maintain a user index for easy querying
#         user_session_ref = {
#             "session_id": session_id,
#             "created_at": datetime.utcnow(),
#             "status": "in_progress",
#             "category": agent.selected_category
#         }
#         db.collection("user_interview_index").document(user_id).collection("sessions").document(session_id).set(user_session_ref)
        
#         print(f"✅ User-specific session {session_id} saved for user {user_id}")
#         return True
#     except Exception as e:
#         print(f"❌ Error saving user-specific session for user {user_id}: {e}")
#         return False

# def load_interview_session(session_id: str, db) -> Optional[TieredInterviewAgent]:
#     """Load USER-SPECIFIC interview session from database"""
#     try:
#         doc = db.collection("interview_sessions").document(session_id).get()
#         if not doc.exists:
#             print(f"❌ Session {session_id} not found in database")
#             return None
        
#         session_data = doc.to_dict()
#         agent_state = session_data.get("agent_state", {})
#         user_id = session_data.get("user_id")
        
#         if not user_id:
#             print(f"❌ No user_id found in session {session_id}")
#             return None
        
#         # Recreate agent from saved state
#         settings = get_settings()
#         agent = TieredInterviewAgent.from_dict(
#             db, 
#             settings.OPENAI_API_KEY, 
#             agent_state,
#             agent_state.get("selected_category", "Movies")
#         )
        
#         print(f"✅ User-specific session {session_id} loaded for user {user_id}")
#         return agent
#     except Exception as e:
#         print(f"❌ Error loading interview session: {e}")
#         return None

# def update_interview_session(session_id: str, agent: TieredInterviewAgent, db):
#     """Update USER-SPECIFIC interview session in database"""
#     try:
#         update_data = {
#             "agent_state": agent.to_dict(),
#             "updated_at": datetime.utcnow(),
#             "status": "completed" if agent.is_complete() else "in_progress",
#             "metadata": {
#                 "current_tier": agent.current_tier_idx,
#                 "current_phase": agent.current_phase,
#                 "total_questions_answered": len(agent.conversation),
#                 "last_updated": datetime.utcnow().isoformat(),
#                 "user_specific": True
#             }
#         }
        
#         if agent.is_complete():
#             update_data["completed_at"] = datetime.utcnow()
        
#         db.collection("interview_sessions").document(session_id).update(update_data)
        
#         # Update user index
#         db.collection("user_interview_index").document(agent.user_id).collection("sessions").document(session_id).update({
#             "status": update_data["status"],
#             "updated_at": datetime.utcnow()
#         })
        
#         print(f"✅ User-specific session {session_id} updated for user {agent.user_id}")
#         return True
#     except Exception as e:
#         print(f"❌ Error updating interview session: {e}")
#         return False

# # FastAPI endpoints with USER-SPECIFIC database session management
# @router.post("/start")
# async def start_interview(
#     request: InterviewStartRequest,
#     current_user: str = Depends(get_current_user)
# ):
#     """Start a new USER-SPECIFIC tiered interview session"""
#     try:
#         settings = get_settings()
#         db = get_firestore_client()
        
#         print(f"🚀 Starting USER-SPECIFIC interview for user: {current_user}")
#         print(f"📝 Selected category: {request.selected_category}")
        
#         # 🔥 CRITICAL: Always pass current_user as user_id for user-specific data
#         agent = TieredInterviewAgent(db, settings.OPENAI_API_KEY, request.selected_category, current_user)
        
#         if agent.is_complete():
#             return {
#                 "success": False,
#                 "message": "Interview already complete for this user",
#                 "is_complete": True,
#                 "user_id": current_user
#             }
        
#         # Generate session ID
#         session_id = str(uuid.uuid4())
#         print(f"📝 Generated session ID: {session_id} for user: {current_user}")
        
#         # 🔥 CRITICAL: Save USER-SPECIFIC session to database
#         if not save_interview_session(current_user, session_id, agent, db):
#             raise HTTPException(status_code=500, detail="Failed to save user-specific interview session")
        
#         # Get first question
#         current_q = agent.get_current_question()
        
#         if current_q:
#             welcome_message = f"Welcome to your personalized Prism Interview! Let's build your unique profile for {request.selected_category}."
#             question_message = f"**Tier {agent.current_tier_idx + 1} - {current_q['phase'].title()} Phase**\n\n{current_q['question']}"
            
#             # Save conversation messages
#             save_conversation_message(
#                 current_user, session_id, "assistant", welcome_message, 
#                 "interview", f"Interview Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
#             )
#             save_conversation_message(
#                 current_user, session_id, "assistant", question_message, "interview"
#             )
            
#             return {
#                 "success": True,
#                 "session_id": session_id,
#                 "user_id": current_user,
#                 "current_question": current_q,
#                 "progress": {
#                     "tier": f"{agent.current_tier_idx + 1}/{len(agent.tier_keys)}",
#                     "phase": agent.current_phase.title(),
#                     "category": request.selected_category
#                 },
#                 "user_specific": True,
#                 "database_saved": True,
#                 "source": "user_specific_database",
#                 "messages": [
#                     {"role": "assistant", "content": welcome_message},
#                     {"role": "assistant", "content": question_message}
#                 ]
#             }
#         else:
#             return {
#                 "success": False,
#                 "message": "No questions found for this user and category",
#                 "is_complete": True,
#                 "user_id": current_user
#             }
            
#     except Exception as e:
#         print(f"❌ Error in start_interview for user {current_user}: {e}")
#         raise HTTPException(status_code=500, detail=f"Failed to start user-specific interview: {str(e)}")

# @router.post("/answer")
# async def submit_answer(
#     request: InterviewAnswerRequest,
#     current_user: str = Depends(get_current_user)
# ):
#     """Submit an answer to the current interview question - USER-SPECIFIC"""
#     try:
#         db = get_firestore_client()
        
#         print(f"📝 Submitting answer for session: {request.session_id} (user: {current_user})")
        
#         # 🔥 Load USER-SPECIFIC session from database
#         agent = load_interview_session(request.session_id, db)
        
#         if not agent:
#             raise HTTPException(status_code=404, detail="Interview session not found in database")
        
#         # Verify user owns this session
#         session_doc = db.collection("interview_sessions").document(request.session_id).get()
#         if not session_doc.exists or session_doc.to_dict().get("user_id") != current_user:
#             raise HTTPException(status_code=403, detail="Not authorized to access this session")
        
#         # Verify agent belongs to current user
#         if agent.user_id != current_user:
#             raise HTTPException(status_code=403, detail="Session does not belong to current user")
        
#         # Get current question for context
#         current_q = agent.get_current_question()
#         if not current_q:
#             return {
#                 "success": False,
#                 "message": "No current question available",
#                 "is_complete": agent.is_complete(),
#                 "user_id": current_user
#             }
        
#         # Save user message to conversation history
#         save_conversation_message(
#             current_user, request.session_id, "user", request.answer, "interview"
#         )
        
#         # Submit answer to USER-SPECIFIC agent
#         success = agent.submit_answer(request.answer)
        
#         if success:
#             # Save updates to USER-SPECIFIC Firestore collections
#             if agent.save_to_firestore():
#                 # 🔥 CRITICAL: Update USER-SPECIFIC session in database
#                 update_interview_session(request.session_id, agent, db)
                
#                 # Check if interview is complete
#                 if agent.is_complete():
#                     completion_message = f"🎉 **Congratulations {current_user}!** You have completed your personalized tiered interview. Your unique profile has been saved successfully!"
                    
#                     # Save completion message
#                     save_conversation_message(
#                         current_user, request.session_id, "assistant", completion_message, "interview"
#                     )
                    
#                     # Mark session as completed in database
#                     db.collection("interview_sessions").document(request.session_id).update({
#                         "status": "completed",
#                         "completed_at": datetime.utcnow()
#                     })
                    
#                     return {
#                         "success": True,
#                         "is_complete": True,
#                         "message": completion_message,
#                         "database_updated": True,
#                         "source": "user_specific_database",
#                         "user_id": current_user
#                     }
#                 else:
#                     # Get next question
#                     next_q = agent.get_current_question()
#                     if next_q:
#                         phase_info = f"**Tier {agent.current_tier_idx + 1} - {next_q['phase'].title()} Phase**"
                        
#                         # Regenerate question with motivation
#                         motivated_question = agent.regenerate_question_with_motivation(
#                             next_q['question'], 
#                             request.answer
#                         )
                        
#                         next_message = f"{phase_info}\n\n{motivated_question}"
                        
#                         # Save assistant message
#                         save_conversation_message(
#                             current_user, request.session_id, "assistant", next_message, "interview"
#                         )
                        
#                         return {
#                             "success": True,
#                             "is_complete": False,
#                             "current_question": next_q,
#                             "progress": {
#                                 "tier": f"{agent.current_tier_idx + 1}/{len(agent.tier_keys)}",
#                                 "phase": agent.current_phase.title(),
#                                 "category": agent.selected_category
#                             },
#                             "database_updated": True,
#                             "source": "user_specific_database",
#                             "user_id": current_user,
#                             "messages": [{"role": "assistant", "content": next_message}]
#                         }
#                     else:
#                         return {
#                             "success": False,
#                             "message": "⚠️ No more questions available.",
#                             "is_complete": True,
#                             "user_id": current_user
#                         }
#             else:
#                 return {
#                     "success": False,
#                     "message": "❌ Failed to save your response. Please try again.",
#                     "user_id": current_user
#                 }
#         else:
#             return {
#                 "success": False,
#                 "message": "❌ Failed to process your answer. Please try again.",
#                 "user_id": current_user
#             }
            
#     except Exception as e:
#         print(f"❌ Error in submit_answer for user {current_user}: {e}")
#         raise HTTPException(status_code=500, detail=f"Failed to submit answer: {str(e)}")

# @router.get("/status/{session_id}")
# async def get_interview_status(
#     session_id: str,
#     current_user: str = Depends(get_current_user)
# ) -> InterviewStatusResponse:
#     """Get current interview status - USER-SPECIFIC"""
#     try:
#         db = get_firestore_client()
        
#         print(f"🔍 Getting status for session: {session_id} (user: {current_user})")
        
#         # 🔥 Load USER-SPECIFIC session from database
#         agent = load_interview_session(session_id, db)
        
#         if not agent:
#             raise HTTPException(status_code=404, detail=f"Interview session {session_id} not found in database")
        
#         # Verify user owns this session
#         session_doc = db.collection("interview_sessions").document(session_id).get()
#         if not session_doc.exists or session_doc.to_dict().get("user_id") != current_user:
#             raise HTTPException(status_code=403, detail="Not authorized to access this session")
        
#         # Verify agent belongs to current user
#         if agent.user_id != current_user:
#             raise HTTPException(status_code=403, detail="Session does not belong to current user")
        
#         current_q = agent.get_current_question()
        
#         return InterviewStatusResponse(
#             session_id=session_id,
#             is_complete=agent.is_complete(),
#             current_tier_idx=agent.current_tier_idx,
#             current_phase=agent.current_phase,
#             current_question=current_q,
#             progress={
#                 "tier": f"{agent.current_tier_idx + 1}/{len(agent.tier_keys)}",
#                 "phase": agent.current_phase.title(),
#                 "tier_name": agent.get_current_tier_key(),
#                 "source": "user_specific_database",
#                 "user_id": current_user,
#                 "category": agent.selected_category
#             }
#         )
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         print(f"❌ Error in get_interview_status for user {current_user}: {e}")
#         raise HTTPException(status_code=500, detail=f"Failed to get interview status: {str(e)}")

# @router.get("/sessions")
# async def list_user_sessions(current_user: str = Depends(get_current_user)):
#     """List all USER-SPECIFIC interview sessions for the current user"""
#     try:
#         db = get_firestore_client()
        
#         print(f"📋 Listing USER-SPECIFIC sessions for user: {current_user}")
        
#         # 🔥 Get USER-SPECIFIC sessions from database
#         sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#         sessions = sessions_ref.order_by("created_at", direction="DESCENDING").stream()
        
#         user_sessions = []
#         for session_doc in sessions:
#             session_data = session_doc.to_dict()
#             agent_state = session_data.get("agent_state", {})
            
#             user_sessions.append({
#                 "session_id": session_data["session_id"],
#                 "user_id": session_data["user_id"],
#                 "created_at": session_data["created_at"].isoformat() if hasattr(session_data["created_at"], 'isoformat') else str(session_data["created_at"]),
#                 "updated_at": session_data["updated_at"].isoformat() if hasattr(session_data["updated_at"], 'isoformat') else str(session_data["updated_at"]),
#                 "status": session_data.get("status", "unknown"),
#                 "is_complete": session_data.get("status") == "completed",
#                 "current_tier": agent_state.get("current_tier_idx", 0) + 1,
#                 "total_tiers": len(agent_state.get("tier_keys", [])),
#                 "current_phase": agent_state.get("current_phase", "unknown"),
#                 "is_active": session_data.get("is_active", False),
#                 "selected_category": agent_state.get("selected_category", "Movies"),
#                 "questions_answered": len(agent_state.get("conversation", [])),
#                 "user_specific": True
#             })
        
#         print(f"✅ Found {len(user_sessions)} USER-SPECIFIC sessions for user {current_user}")
        
#         return {
#             "sessions": user_sessions,
#             "total_sessions": len(user_sessions),
#             "source": "user_specific_database",
#             "storage_type": "firestore_user_specific",
#             "user_id": current_user
#         }
        
#     except Exception as e:
#         print(f"❌ Error listing sessions for user {current_user}: {e}")
#         raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")

# @router.get("/profile")
# async def get_user_profile(current_user: str = Depends(get_current_user)):
#     """Get USER-SPECIFIC profile"""
#     try:
#         db = get_firestore_client()
        
#         # Load user-specific profile
#         profile_doc_id = f"{current_user}_profile_structure.json"
#         profile_doc = db.collection("user_profiles").document(profile_doc_id).get()
        
#         if not profile_doc.exists:
#             return {
#                 "success": False,
#                 "message": "No profile found for this user. Please complete an interview first.",
#                 "user_id": current_user
#             }
        
#         profile_data = profile_doc.to_dict()
        
#         return {
#             "success": True,
#             "profile": profile_data,
#             "user_id": current_user,
#             "profile_type": "user_specific"
#         }
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to load user profile: {str(e)}")

# @router.get("/profile/progress")
# async def get_user_profile_progress(current_user: str = Depends(get_current_user)):
#     """Get USER-SPECIFIC profile completion progress"""
#     try:
#         db = get_firestore_client()
        
#         # Check user's question progress
#         general_doc = db.collection("user_questions").document(f"{current_user}_general_questions.json").get()
#         category_doc = db.collection("user_questions").document(f"{current_user}_category_questions.json").get()
        
#         progress = {
#             "user_id": current_user,
#             "general_questions": {"completed": 0, "total": 0},
#             "category_questions": {"completed": 0, "total": 0},
#             "overall_completion": 0,
#             "tiers_completed": 0,
#             "total_tiers": 0
#         }
        
#         # Calculate general questions progress
#         if general_doc.exists:
#             general_data = general_doc.to_dict()
#             for tier_key, tier_data in general_data.items():
#                 if tier_key.startswith('tier') and isinstance(tier_data, dict):
#                     progress["total_tiers"] += 1
#                     if tier_data.get('status') == 'completed':
#                         progress["tiers_completed"] += 1
                    
#                     questions = tier_data.get('questions', [])
#                     progress["general_questions"]["total"] += len(questions)
#                     progress["general_questions"]["completed"] += len([q for q in questions if q.get('qest') == 'answered'])
        
#         # Calculate category questions progress
#         if category_doc.exists:
#             category_data = category_doc.to_dict()
#             for tier_key, tier_data in category_data.items():
#                 if tier_key.startswith('tier') and isinstance(tier_data, dict):
#                     questions = tier_data.get('questions', [])
#                     progress["category_questions"]["total"] += len(questions)
#                     progress["category_questions"]["completed"] += len([q for q in questions if q.get('qest') == 'answered'])
        
#         # Calculate overall completion
#         total_questions = progress["general_questions"]["total"] + progress["category_questions"]["total"]
#         total_completed = progress["general_questions"]["completed"] + progress["category_questions"]["completed"]
        
#         if total_questions > 0:
#             progress["overall_completion"] = round((total_completed / total_questions) * 100, 2)
        
#         return {
#             "success": True,
#             "progress": progress,
#             "user_specific": True
#         }
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to get user progress: {str(e)}")

# @router.delete("/profile/reset")
# async def reset_user_profile(current_user: str = Depends(get_current_user)):
#     """Reset USER-SPECIFIC profile and questions"""
#     try:
#         db = get_firestore_client()
        
#         # Delete user-specific documents
#         documents_to_delete = [
#             ("user_profiles", f"{current_user}_profile_structure.json"),
#             ("user_questions", f"{current_user}_general_questions.json"),
#             ("user_questions", f"{current_user}_category_questions.json")
#         ]
        
#         deleted_count = 0
#         for collection, doc_id in documents_to_delete:
#             try:
#                 doc_ref = db.collection(collection).document(doc_id)
#                 if doc_ref.get().exists:
#                     doc_ref.delete()
#                     deleted_count += 1
#                     print(f"✅ Deleted {collection}/{doc_id}")
#             except Exception as e:
#                 print(f"❌ Error deleting {collection}/{doc_id}: {e}")
        
#         # Also mark user's interview sessions as reset
#         sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#         reset_sessions = 0
#         for session in sessions_ref.stream():
#             session.reference.update({
#                 "is_active": False,
#                 "status": "reset",
#                 "reset_at": datetime.utcnow()
#             })
#             reset_sessions += 1
        
#         # Delete user index
#         try:
#             user_index_ref = db.collection("user_interview_index").document(current_user)
#             if user_index_ref.get().exists:
#                 user_index_ref.delete()
#                 print(f"✅ Deleted user index for {current_user}")
#         except Exception as e:
#             print(f"❌ Error deleting user index: {e}")
        
#         return {
#             "success": True,
#             "message": f"User profile reset successfully. Deleted {deleted_count} documents and reset {reset_sessions} sessions.",
#             "user_id": current_user,
#             "deleted_documents": deleted_count,
#             "reset_sessions": reset_sessions
#         }
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to reset user profile: {str(e)}")

# @router.delete("/sessions/{session_id}")
# async def delete_interview_session(
#     session_id: str,
#     current_user: str = Depends(get_current_user)
# ):
#     """Delete a USER-SPECIFIC interview session from database"""
#     try:
#         db = get_firestore_client()
        
#         # Verify user owns this session
#         session_doc = db.collection("interview_sessions").document(session_id).get()
#         if not session_doc.exists:
#             raise HTTPException(status_code=404, detail="Interview session not found")
        
#         session_data = session_doc.to_dict()
#         if session_data.get("user_id") != current_user:
#             raise HTTPException(status_code=403, detail="Not authorized to delete this session")
        
#         # Soft delete
#         db.collection("interview_sessions").document(session_id).update({
#             "is_active": False,
#             "deleted_at": datetime.utcnow(),
#             "status": "deleted"
#         })
        
#         # Update user index
#         try:
#             db.collection("user_interview_index").document(current_user).collection("sessions").document(session_id).update({
#                 "status": "deleted",
#                 "deleted_at": datetime.utcnow()
#             })
#         except Exception as e:
#             print(f"❌ Error updating user index: {e}")
        
#         return {
#             "success": True,
#             "message": f"Interview session {session_id} deleted successfully",
#             "source": "user_specific_database",
#             "user_id": current_user
#         }
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")

# # Debug endpoints to verify database operations
# @router.get("/debug/database")
# async def debug_database_connection(current_user: str = Depends(get_current_user)):
#     """Debug endpoint to test USER-SPECIFIC database connectivity"""
#     try:
#         db = get_firestore_client()
        
#         # Test database write
#         test_doc_ref = db.collection("debug_test").document(f"test_{current_user}")
#         test_data = {
#             "user_id": current_user,
#             "timestamp": datetime.utcnow(),
#             "test": "user_specific_database_connectivity"
#         }
#         test_doc_ref.set(test_data)
        
#         # Test database read
#         test_doc = test_doc_ref.get()
        
#         if test_doc.exists:
#             # Clean up test document
#             test_doc_ref.delete()
            
#             return {
#                 "success": True,
#                 "message": "User-specific database connection successful",
#                 "firestore_connected": True,
#                 "can_write": True,
#                 "can_read": True,
#                 "storage_type": "user_specific_database",
#                 "user_id": current_user
#             }
#         else:
#             return {
#                 "success": False,
#                 "message": "Database read failed",
#                 "firestore_connected": True,
#                 "can_write": True,
#                 "can_read": False,
#                 "user_id": current_user
#             }
        
#     except Exception as e:
#         return {
#             "success": False,
#             "message": f"Database connection failed: {str(e)}",
#             "firestore_connected": False,
#             "error": str(e),
#             "user_id": current_user
#         }

# @router.get("/debug/user-data")
# async def debug_user_data(current_user: str = Depends(get_current_user)):
#     """Debug endpoint to check USER-SPECIFIC data in database"""
#     try:
#         db = get_firestore_client()
        
#         data_check = {
#             "user_id": current_user,
#             "profile_exists": False,
#             "general_questions_exist": False,
#             "category_questions_exist": False,
#             "sessions_count": 0,
#             "user_index_exists": False
#         }
        
#         # Check user profile
#         profile_doc = db.collection("user_profiles").document(f"{current_user}_profile_structure.json").get()
#         data_check["profile_exists"] = profile_doc.exists
        
#         # Check user questions
#         general_doc = db.collection("user_questions").document(f"{current_user}_general_questions.json").get()
#         data_check["general_questions_exist"] = general_doc.exists
        
#         category_doc = db.collection("user_questions").document(f"{current_user}_category_questions.json").get()
#         data_check["category_questions_exist"] = category_doc.exists
        
#         # Check sessions
#         sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#         sessions_count = len(list(sessions_ref.stream()))
#         data_check["sessions_count"] = sessions_count
        
#         # Check user index
#         user_index_doc = db.collection("user_interview_index").document(current_user).get()
#         data_check["user_index_exists"] = user_index_doc.exists
        
#         return {
#             "success": True,
#             "data_check": data_check
#         }
        
#     except Exception as e:
#         return {
#             "success": False,
#             "error": str(e),
#             "user_id": current_user
#         }

# # 🔥 DEBUG ENDPOINTS FOR AUTHENTICATION TESTING
# @router.get("/debug/auth")
# async def debug_authentication(
#     credentials: HTTPAuthorizationCredentials = Depends(security)
# ):
#     """Debug endpoint to test authentication"""
#     try:
#         from app.core.security import debug_token_verification
        
#         print(f"🔍 DEBUG AUTH ENDPOINT:")
#         print(f"  Credentials: {credentials}")
#         print(f"  Scheme: {credentials.scheme}")
#         print(f"  Token: {credentials.credentials[:50]}..." if credentials.credentials else "None")
        
#         # Manual token verification
#         result = debug_token_verification(credentials.credentials)
        
#         return {
#             "success": True,
#             "debug_info": {
#                 "scheme": credentials.scheme,
#                 "token_prefix": credentials.credentials[:50] if credentials.credentials else None,
#                 "token_length": len(credentials.credentials) if credentials.credentials else 0,
#                 "verification_result": result
#             }
#         }
        
#     except Exception as e:
#         return {
#             "success": False,
#             "error": str(e),
#             "debug_info": {
#                 "credentials_received": bool(credentials),
#                 "scheme": getattr(credentials, 'scheme', None),
#                 "has_token": bool(getattr(credentials, 'credentials', None))
#             }
#         }

# @router.get("/debug/auth-simple")
# async def debug_auth_simple():
#     """Simple debug endpoint without authentication"""
#     try:
#         from app.core.config import get_settings
#         settings = get_settings()
        
#         return {
#             "success": True,
#             "config_info": {
#                 "secret_key_exists": bool(settings.SECRET_KEY),
#                 "secret_key_length": len(settings.SECRET_KEY) if settings.SECRET_KEY else 0,
#                 "access_token_expire_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES
#             }
#         }
#     except Exception as e:
#         return {
#             "success": False,
#             "error": str(e)
#         }

# @router.post("/debug/test-token")
# async def test_token_manually(token_data: dict):
#     """Test a token manually by passing it in the request body"""
#     try:
#         from app.core.security import debug_token_verification
        
#         token = token_data.get("token")
#         if not token:
#             return {"success": False, "error": "No token provided"}
        
#         result = debug_token_verification(token)
        
#         return {
#             "success": True,
#             "token_test_result": result
#         }
        
#     except Exception as e:
#         return {
#             "success": False,
#             "error": str(e)
#         }
# # Replace the list_user_sessions function in interview.py with this version:

# @router.get("/sessions")
# async def list_user_sessions(current_user: str = Depends(get_current_user)):
#     """List all USER-SPECIFIC interview sessions for the current user - Fixed Version"""
#     try:
#         db = get_firestore_client()
        
#         print(f"📋 Listing USER-SPECIFIC sessions for user: {current_user}")
        
#         # 🔥 TEMPORARY FIX: Get sessions without ordering first
#         sessions_ref = db.collection("interview_sessions").where("user_id", "==", current_user)
#         sessions_docs = list(sessions_ref.stream())
        
#         # Sort in Python instead of Firestore
#         sessions_list = []
#         for session_doc in sessions_docs:
#             session_data = session_doc.to_dict()
#             sessions_list.append(session_data)
        
#         # Sort by created_at in descending order (most recent first)
#         sessions_list.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
        
#         user_sessions = []
#         for session_data in sessions_list:
#             agent_state = session_data.get("agent_state", {})
            
#             user_sessions.append({
#                 "session_id": session_data["session_id"],
#                 "user_id": session_data["user_id"],
#                 "created_at": session_data["created_at"].isoformat() if hasattr(session_data["created_at"], 'isoformat') else str(session_data["created_at"]),
#                 "updated_at": session_data["updated_at"].isoformat() if hasattr(session_data["updated_at"], 'isoformat') else str(session_data["updated_at"]),
#                 "status": session_data.get("status", "unknown"),
#                 "is_complete": session_data.get("status") == "completed",
#                 "current_tier": agent_state.get("current_tier_idx", 0) + 1,
#                 "total_tiers": len(agent_state.get("tier_keys", [])),
#                 "current_phase": agent_state.get("current_phase", "unknown"),
#                 "is_active": session_data.get("is_active", False),
#                 "selected_category": agent_state.get("selected_category", "Movies"),
#                 "questions_answered": len(agent_state.get("conversation", [])),
#                 "user_specific": True
#             })
        
#         print(f"✅ Found {len(user_sessions)} USER-SPECIFIC sessions for user {current_user}")
        
#         return {
#             "sessions": user_sessions,
#             "total_sessions": len(user_sessions),
#             "source": "user_specific_database",
#             "storage_type": "firestore_user_specific",
#             "user_id": current_user,
#             "index_status": "sorting_in_python"
#         }
        
#     except Exception as e:
#         print(f"❌ Error listing sessions for user {current_user}: {e}")
#         raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")

# # Alternative: Use user index collection instead
# @router.get("/sessions-alt")
# async def list_user_sessions_alternative(current_user: str = Depends(get_current_user)):
#     """Alternative: Use user index collection for faster queries"""
#     try:
#         db = get_firestore_client()
        
#         print(f"📋 Listing sessions using user index for: {current_user}")
        
#         # Use the user index collection instead
#         user_index_ref = db.collection("user_interview_index").document(current_user).collection("sessions")
#         session_refs = list(user_index_ref.stream())
        
#         user_sessions = []
#         for session_ref in session_refs:
#             session_index_data = session_ref.to_dict()
#             session_id = session_index_data.get("session_id")
            
#             if session_id:
#                 # Get full session data
#                 session_doc = db.collection("interview_sessions").document(session_id).get()
#                 if session_doc.exists:
#                     session_data = session_doc.to_dict()
#                     agent_state = session_data.get("agent_state", {})
                    
#                     user_sessions.append({
#                         "session_id": session_data["session_id"],
#                         "user_id": session_data["user_id"],
#                         "created_at": session_data["created_at"].isoformat() if hasattr(session_data["created_at"], 'isoformat') else str(session_data["created_at"]),
#                         "updated_at": session_data["updated_at"].isoformat() if hasattr(session_data["updated_at"], 'isoformat') else str(session_data["updated_at"]),
#                         "status": session_data.get("status", "unknown"),
#                         "is_complete": session_data.get("status") == "completed",
#                         "current_tier": agent_state.get("current_tier_idx", 0) + 1,
#                         "total_tiers": len(agent_state.get("tier_keys", [])),
#                         "current_phase": agent_state.get("current_phase", "unknown"),
#                         "is_active": session_data.get("is_active", False),
#                         "selected_category": agent_state.get("selected_category", "Movies"),
#                         "questions_answered": len(agent_state.get("conversation", [])),
#                         "user_specific": True
#                     })
        
#         # Sort by created_at
#         user_sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
#         return {
#             "sessions": user_sessions,
#             "total_sessions": len(user_sessions),
#             "source": "user_index_collection",
#             "storage_type": "firestore_user_index",
#             "user_id": current_user
#         }
        
#     except Exception as e:
#         print(f"❌ Error listing sessions for user {current_user}: {e}")
#         raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")  

# app/routers/interview.py - Complete Enhanced Interview Router

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime

from app.core.security import get_current_user
from app.core.firebase import get_firestore_client

router = APIRouter()

# Enhanced Pydantic models
class InterviewStartRequest(BaseModel):
    user_id: Optional[str] = None
    selected_category: str
    force_restart: Optional[bool] = False

class InterviewAnswerRequest(BaseModel):
    session_id: str
    answer: str
    question_id: Optional[str] = None

class InterviewStatusResponse(BaseModel):
    session_id: str
    is_complete: bool
    current_tier_idx: int
    current_phase: str
    current_question: Optional[Dict[str, Any]] = None
    progress: Dict[str, Any]

# Helper functions
def get_first_question_for_category(category: str, db) -> Dict[str, Any]:
    """Get the first question for a given category"""
    try:
        # Load general questions to get the first question
        gen_doc = db.collection("question_collection").document("general_tiered_questions.json").get()
        if gen_doc.exists:
            general_questions = gen_doc.to_dict()
            tier_keys = sorted([k for k in general_questions.keys() if k.startswith('tier')], 
                             key=lambda x: int(x.replace('tier', '')))
            
            if tier_keys:
                first_tier = tier_keys[0]
                questions = general_questions.get(first_tier, {}).get('questions', [])
                if questions:
                    first_question = questions[0]
                    return {
                        "question": first_question.get('question', f"Let's start building your {category} preferences."),
                        "field": first_question.get('field', f"generalprofile.corePreferences.{category.lower()}Motivation"),
                        "phase": "general",
                        "tier": first_tier,
                        "question_id": first_question.get('question_id', f"{category.lower()}_intro_1"),
                        "category": category,
                        "user_id": ""  # Will be filled by caller
                    }
        
        # Fallback question
        return {
            "question": f"What draws you to {category.lower()}? Tell me about your interests and what you're looking for.",
            "field": f"generalprofile.corePreferences.{category.lower()}Motivation",
            "phase": "general",
            "tier": "tier1",
            "question_id": f"{category.lower()}_intro_1",
            "category": category,
            "user_id": ""
        }
    except Exception as e:
        print(f"Error getting first question: {e}")
        return {
            "question": f"Welcome to your {category} interview! Let's begin building your personalized profile.",
            "field": "general.intro",
            "phase": "general",
            "tier": "tier1",
            "question_id": "intro_1",
            "category": category,
            "user_id": ""
        }

def get_current_question_for_session(session_id: str, db) -> Dict[str, Any]:
    """Get current question for an existing session"""
    try:
        session_doc = db.collection("interview_sessions").document(session_id).get()
        if session_doc.exists:
            session_data = session_doc.to_dict()
            category = session_data.get("selected_category", "Movies")
            tier = session_data.get("current_tier", 1)
            phase = session_data.get("current_phase", "general")
            user_id = session_data.get("user_id", "")
            
            # Try to get actual question from question collection
            # This is a simplified version - you'd integrate with your question loading logic
            return {
                "question": f"Continuing your {category} interview. What are your preferences for {phase} aspects?",
                "field": f"generalprofile.tier{tier}.{phase}",
                "phase": phase,
                "tier": f"tier{tier}",
                "question_id": f"{category.lower()}_{phase}_{tier}",
                "category": category,
                "user_id": user_id
            }
    except Exception as e:
        print(f"Error getting current question: {e}")
    
    return {
        "question": "Let's continue your interview...",
        "field": "general.continue",
        "phase": "general",
        "tier": "tier1",
        "question_id": "continue_1",
        "category": "general",
        "user_id": ""
    }

# MAIN ENDPOINTS

@router.post("/start")
async def start_interview(
    request: InterviewStartRequest,
    current_user: str = Depends(get_current_user)
):
    """Start or continue interview for a specific category - ENHANCED VERSION"""
    try:
        db = get_firestore_client()
        
        # Validate category
        valid_categories = ["Movies", "Food", "Travel", "Books", "Music", "Fitness"]
        if request.selected_category not in valid_categories:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {valid_categories}"
            )
        
        # Check existing sessions for this user and category
        sessions_query = db.collection("interview_sessions")\
            .where("user_id", "==", current_user)\
            .where("selected_category", "==", request.selected_category)
        
        existing_sessions = list(sessions_query.stream())
        
        # Check if there's an active session for this category
        active_session = None
        completed_session = None
        
        for session in existing_sessions:
            session_data = session.to_dict()
            if session_data.get("status") == "in_progress":
                active_session = session
            elif session_data.get("status") == "completed":
                completed_session = session
        
        # If there's an active session, resume it
        if active_session:
            session_data = active_session.to_dict()
            current_question = get_current_question_for_session(active_session.id, db)
            current_question["user_id"] = current_user
            
            return {
                "success": True,
                "message": f"Resuming existing {request.selected_category} interview",
                "session_id": active_session.id,
                "user_id": current_user,
                "current_question": current_question,
                "progress": {
                    "tier": f"{session_data.get('current_tier', 1)}/3",
                    "phase": session_data.get('current_phase', 'general').title(),
                    "tier_name": f"tier{session_data.get('current_tier', 1)}",
                    "source": "existing_session_resumed",
                    "user_id": current_user,
                    "category": request.selected_category
                },
                "is_resume": True,
                "user_specific": True,
                "database_saved": True,
                "source": "existing_session_resumed"
            }
        
        # If there's a completed session, offer to restart or update
        if completed_session:
            # Check if user explicitly wants to restart
            if request.force_restart:
                print(f"🔄 Force restarting {request.selected_category} interview for user {current_user}")
                
                # Archive the old session
                completed_session.reference.update({
                    "status": "archived",
                    "archived_at": datetime.utcnow(),
                    "archived_reason": "user_restart"
                })
                
                # Create new session
                new_session_id = str(uuid.uuid4())
                new_session_data = {
                    "session_id": new_session_id,
                    "user_id": current_user,
                    "selected_category": request.selected_category,
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
                    "restart_count": completed_session.to_dict().get("restart_count", 0) + 1
                }
                
                # Save new session
                db.collection("interview_sessions").document(new_session_id).set(new_session_data)
                
                # Get first question
                current_question = get_first_question_for_category(request.selected_category, db)
                current_question["user_id"] = current_user
                
                return {
                    "success": True,
                    "message": f"Restarted {request.selected_category} interview",
                    "session_id": new_session_id,
                    "user_id": current_user,
                    "current_question": current_question,
                    "progress": {
                        "tier": "1/3",
                        "phase": "General",
                        "tier_name": "tier1",
                        "source": "new_session_after_restart",
                        "user_id": current_user,
                        "category": request.selected_category
                    },
                    "is_restart": True,
                    "user_specific": True,
                    "database_saved": True,
                    "source": "new_session_after_restart",
                    "messages": [
                        {"role": "assistant", "content": f"Welcome back! Let's update your {request.selected_category} profile."},
                        {"role": "assistant", "content": f"**Tier 1 - General Phase**\n\n{current_question.get('question', '')}"}
                    ]
                }
            else:
                # Offer options to user
                completed_data = completed_session.to_dict()
                return {
                    "success": False,
                    "message": f"{request.selected_category} interview already completed",
                    "is_complete": True,
                    "user_id": current_user,
                    "completed_at": completed_data.get("updated_at"),
                    "session_id": completed_session.id,
                    "options": {
                        "restart": f"Add 'force_restart': true to restart the {request.selected_category} interview",
                        "update": f"Use the update endpoints to modify specific {request.selected_category} preferences",
                        "switch_category": "Try a different category like Food, Books, Music, or Fitness"
                    },
                    "available_actions": [
                        "restart_interview",
                        "update_preferences", 
                        "switch_category"
                    ]
                }
        
        # No existing sessions - create new one
        session_id = str(uuid.uuid4())
        session_data = {
            "session_id": session_id,
            "user_id": current_user,
            "selected_category": request.selected_category,
            "status": "in_progress",
            "current_tier": 1,
            "current_phase": "general",
            "questions_answered": 0,
            "total_tiers": 3,
            "is_complete": False,
            "is_active": True,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "user_specific": True
        }
        
        # Save session to database
        db.collection("interview_sessions").document(session_id).set(session_data)
        
        # Get first question
        current_question = get_first_question_for_category(request.selected_category, db)
        current_question["user_id"] = current_user
        
        return {
            "success": True,
            "message": f"Started new {request.selected_category} interview",
            "session_id": session_id,
            "user_id": current_user,
            "current_question": current_question,
            "progress": {
                "tier": "1/3",
                "phase": "General",
                "tier_name": "tier1",
                "source": "new_session_created",
                "user_id": current_user,
                "category": request.selected_category
            },
            "user_specific": True,
            "database_saved": True,
            "source": "new_session_created",
            "messages": [
                {"role": "assistant", "content": f"Welcome to your personalized Prism Interview! Let's build your unique profile for {request.selected_category}."},
                {"role": "assistant", "content": f"**Tier 1 - General Phase**\n\n{current_question.get('question', '')}"}
            ]
        }
        
    except Exception as e:
        print(f"❌ Error starting interview: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start interview: {str(e)}"
        )

@router.get("/status/{session_id}")
async def get_interview_status(
    session_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get status of a specific interview session"""
    try:
        db = get_firestore_client()
        
        # Get session data
        session_doc = db.collection("interview_sessions").document(session_id).get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail="Interview session not found")
        
        session_data = session_doc.to_dict()
        
        # Verify ownership
        if session_data.get("user_id") != current_user:
            raise HTTPException(status_code=403, detail="Access denied to this interview session")
        
        # Get current question if not complete
        current_question = None
        if session_data.get("status") == "in_progress":
            current_question = get_current_question_for_session(session_id, db)
            current_question["user_id"] = current_user
        
        return {
            "session_id": session_id,
            "is_complete": session_data.get("status") == "completed",
            "current_tier_idx": session_data.get("current_tier", 1) - 1,  # 0-based for frontend
            "current_phase": session_data.get("current_phase", "general"),
            "current_question": current_question,
            "progress": {
                "tier": f"{session_data.get('current_tier', 1)}/3",
                "phase": session_data.get('current_phase', 'general').title(),
                "tier_name": f"tier{session_data.get('current_tier', 1)}",
                "source": "user_specific_database",
                "user_id": current_user,
                "category": session_data.get("selected_category", "Unknown")
            },
            "status": session_data.get("status"),
            "questions_answered": session_data.get("questions_answered", 0),
            "category": session_data.get("selected_category"),
            "created_at": session_data.get("created_at"),
            "updated_at": session_data.get("updated_at")
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get interview status: {str(e)}"
        )

@router.get("/status/category/{category}")
async def get_category_interview_status(
    category: str,
    current_user: str = Depends(get_current_user)
):
    """Get interview status for a specific category"""
    try:
        db = get_firestore_client()
        
        # Get sessions for this user and category
        sessions_query = db.collection("interview_sessions")\
            .where("user_id", "==", current_user)\
            .where("selected_category", "==", category)
        
        sessions = list(sessions_query.stream())
        
        if not sessions:
            return {
                "user_id": current_user,
                "category": category,
                "status": "not_started",
                "has_data": False,
                "message": f"No {category} interview found. Start one to build your {category} profile."
            }
        
        # Find the most recent session
        latest_session = max(sessions, key=lambda s: s.to_dict().get("updated_at", datetime.min))
        session_data = latest_session.to_dict()
        
        # Check profile completeness for this category
        from app.routers.recommendations import load_user_profile
        profile = load_user_profile(current_user)
        category_lower = category.lower()
        has_category_data = False
        
        if profile and "recommendationProfiles" in profile:
            # Check various possible category names
            category_keys = [category_lower, f"{category_lower}AndTV", f"{category_lower}_dining"]
            for key in category_keys:
                if key in profile["recommendationProfiles"]:
                    has_category_data = True
                    break
        
        response = {
            "user_id": current_user,
            "category": category,
            "session_id": latest_session.id,
            "status": session_data.get("status"),
            "current_tier": session_data.get("current_tier"),
            "current_phase": session_data.get("current_phase"),
            "questions_answered": session_data.get("questions_answered", 0),
            "created_at": session_data.get("created_at"),
            "updated_at": session_data.get("updated_at"),
            "has_category_data": has_category_data,
            "is_complete": session_data.get("status") == "completed"
        }
        
        if session_data.get("status") == "completed":
            response["message"] = f"{category} interview completed. You can restart it or try other categories."
            response["available_actions"] = ["restart", "update_preferences", "try_other_categories"]
        elif session_data.get("status") == "in_progress":
            response["message"] = f"{category} interview in progress. Continue where you left off."
            response["available_actions"] = ["continue", "restart"]
        else:
            response["message"] = f"{category} interview {session_data.get('status')}."
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get category status: {str(e)}"
        )

@router.get("/categories/progress")
async def get_all_categories_progress(current_user: str = Depends(get_current_user)):
    """Get interview progress for all categories"""
    try:
        db = get_firestore_client()
        
        categories = ["Movies", "Food", "Travel", "Books", "Music", "Fitness"]
        progress = {}
        
        # Get all sessions for this user
        all_sessions_query = db.collection("interview_sessions").where("user_id", "==", current_user)
        all_sessions = list(all_sessions_query.stream())
        
        # Group sessions by category
        sessions_by_category = {}
        for session in all_sessions:
            session_data = session.to_dict()
            category = session_data.get("selected_category")
            if category not in sessions_by_category:
                sessions_by_category[category] = []
            sessions_by_category[category].append((session, session_data))
        
        # Get profile data
        from app.routers.recommendations import load_user_profile
        profile = load_user_profile(current_user)
        profile_sections = profile.get("recommendationProfiles", {}) if profile else {}
        
        for category in categories:
            category_lower = category.lower()
            
            # Check for sessions
            if category in sessions_by_category:
                # Get latest session
                latest_session, latest_data = max(
                    sessions_by_category[category], 
                    key=lambda x: x[1].get("updated_at", datetime.min)
                )
                
                progress[category] = {
                    "status": latest_data.get("status", "unknown"),
                    "questions_answered": latest_data.get("questions_answered", 0),
                    "current_tier": latest_data.get("current_tier", 1),
                    "current_phase": latest_data.get("current_phase", "general"),
                    "last_updated": latest_data.get("updated_at"),
                    "session_id": latest_session.id,
                    "has_profile_data": False,
                    "can_start": latest_data.get("status") != "in_progress",
                    "can_continue": latest_data.get("status") == "in_progress",
                    "can_restart": latest_data.get("status") == "completed"
                }
            else:
                progress[category] = {
                    "status": "not_started",
                    "questions_answered": 0,
                    "current_tier": 1,
                    "current_phase": "general",
                    "last_updated": None,
                    "session_id": None,
                    "has_profile_data": False,
                    "can_start": True,
                    "can_continue": False,
                    "can_restart": False
                }
            
            # Check for profile data
            category_keys = [category_lower, f"{category_lower}AndTV", f"{category_lower}_dining"]
            for key in category_keys:
                if key in profile_sections:
                    progress[category]["has_profile_data"] = True
                    break
        
        return {
            "success": True,
            "user_id": current_user,
            "categories": progress,
            "summary": {
                "completed": len([c for c in progress.values() if c["status"] == "completed"]),
                "in_progress": len([c for c in progress.values() if c["status"] == "in_progress"]),
                "not_started": len([c for c in progress.values() if c["status"] == "not_started"]),
                "total_categories": len(categories)
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get categories progress: {str(e)}"
        )

@router.get("/sessions-alt")
async def get_user_sessions_alternative(current_user: str = Depends(get_current_user)):
    """Get all interview sessions for the current user"""
    try:
        db = get_firestore_client()
        
        # Get all sessions for this user
        sessions_query = db.collection("interview_sessions").where("user_id", "==", current_user)
        sessions = list(sessions_query.stream())
        
        session_list = []
        for session in sessions:
            session_data = session.to_dict()
            session_list.append({
                "session_id": session.id,
                "user_id": session_data.get("user_id"),
                "created_at": session_data.get("created_at"),
                "updated_at": session_data.get("updated_at"),
                "status": session_data.get("status"),
                "is_complete": session_data.get("status") == "completed",
                "current_tier": session_data.get("current_tier", 1),
                "total_tiers": session_data.get("total_tiers", 3),
                "current_phase": session_data.get("current_phase", "general"),
                "is_active": session_data.get("is_active", True),
                "selected_category": session_data.get("selected_category"),
                "questions_answered": session_data.get("questions_answered", 0),
                "user_specific": session_data.get("user_specific", True)
            })
        
        return {
            "sessions": session_list,
            "total_sessions": len(session_list),
            "source": "user_index_collection",
            "storage_type": "firestore_user_index",
            "user_id": current_user
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get user sessions: {str(e)}"
        )

@router.post("/answer")
async def submit_interview_answer(
    request: InterviewAnswerRequest,
    current_user: str = Depends(get_current_user)
):
    """Submit an answer to an interview question"""
    try:
        db = get_firestore_client()
        
        # Get session data
        session_doc = db.collection("interview_sessions").document(request.session_id).get()
        
        if not session_doc.exists:
            raise HTTPException(status_code=404, detail="Interview session not found")
        
        session_data = session_doc.to_dict()
        
        # Verify ownership
        if session_data.get("user_id") != current_user:
            raise HTTPException(status_code=403, detail="Access denied to this interview session")
        
        # Verify session is active
        if session_data.get("status") != "in_progress":
            raise HTTPException(status_code=400, detail="Interview session is not active")
        
        # TODO: Implement answer processing logic
        # This would involve:
        # 1. Saving the answer to the profile structure
        # 2. Advancing to the next question
        # 3. Updating session progress
        # 4. Checking for completion
        
        # For now, just update questions answered count
        current_questions = session_data.get("questions_answered", 0)
        session_doc.reference.update({
            "questions_answered": current_questions + 1,
            "updated_at": datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": "Answer submitted successfully",
            "session_id": request.session_id,
            "questions_answered": current_questions + 1,
            "note": "Answer processing logic needs to be implemented"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit answer: {str(e)}"
        )

@router.post("/restart/{category}")
async def restart_category_interview(
    category: str,
    current_user: str = Depends(get_current_user)
):
    """Restart interview for a specific category"""
    try:
        db = get_firestore_client()
        
        # Validate category
        valid_categories = ["Movies", "Food", "Travel", "Books", "Music", "Fitness"]
        if category not in valid_categories:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {valid_categories}"
            )
        
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
        
        # Get first question
        current_question = get_first_question_for_category(category, db)
        current_question["user_id"] = current_user
        
        return {
            "success": True,
            "message": f"Restarted {category} interview",
            "session_id": session_id,
            "user_id": current_user,
            "category": category,
            "archived_sessions": len(existing_sessions),
            "status": "in_progress",
            "current_question": current_question,
            "progress": {
                "tier": "1/3",
                "phase": "General",
                "category": category
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to restart {category} interview: {str(e)}"
        )