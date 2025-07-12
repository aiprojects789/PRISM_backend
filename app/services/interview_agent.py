# app/services/interview_agent.py - Complete Database-compatible TieredInterviewAgent

from openai import OpenAI
from app.core.config import get_settings
from app.core.firebase import get_firestore_client
from typing import List, Dict, Any, Optional
import uuid
import json
from datetime import datetime

class TieredInterviewAgent:
    def __init__(self, db, openai_key, selected_category="Movies", user_id=None):
        self.db = db
        self.openai_key = openai_key
        self.user_id = user_id
        self.selected_category = selected_category
        self.current_tier_idx = 0
        self.current_phase = 'general'
        self.current_q_idx = 0
        self.tier_keys = []
        self.general_questions = {}
        self.category_questions = {}
        self.profile_structure = {}
        self.conversation = []  # Track conversation history
        self.follow_up_count = 0
        self.started_at = datetime.utcnow()
        self.completed_at = None
        
        # Category mapping
        selected = selected_category.lower()
        cat_map = {
            'movies': 'moviesAndTV_tiered_questions.json',
            'food': 'foodAndDining_tiered_questions.json',
            'travel': 'travel_tiered_questions.json'
        }
        self.cat_doc_id = cat_map.get(selected, 'moviesAndTV_tiered_questions.json')
        
        self.load_data()

    def load_data(self):
        """Load questions and profile data from Firestore"""
        try:
            # Load general questions
            gen_doc = self.db.collection("question_collection").document("general_tiered_questions.json").get()
            self.general_questions = gen_doc.to_dict() if gen_doc.exists else {}
            
            # Load category questions
            cat_doc = self.db.collection("question_collection").document(self.cat_doc_id).get()
            self.category_questions = cat_doc.to_dict() if cat_doc.exists else {}
            
            # Load user-specific profile structure
            profile_doc_id = f"{self.user_id}_profile_structure.json" if self.user_id else "profile_strcuture.json"
            profile_doc = self.db.collection("user_collection").document(profile_doc_id).get()
            self.profile_structure = profile_doc.to_dict() if profile_doc.exists else {}
            
            # Extract tier keys
            if self.general_questions:
                self.tier_keys = sorted(
                    [k for k in self.general_questions.keys() if k.startswith('tier')],
                    key=lambda x: int(x.replace('tier', ''))
                )
            else:
                self.tier_keys = ["tier1", "tier2", "tier3"]  # Fallback

        except Exception as e:
            print(f"Failed to load data: {e}")
            self.general_questions = {}
            self.category_questions = {}
            self.profile_structure = {}
            self.tier_keys = ["tier1", "tier2", "tier3"]  # Fallback

        self.pick_up_where_left_off()

    def pick_up_where_left_off(self):
        """Find the first tier that is not completed and set it to in_process"""
        for idx, tier_key in enumerate(self.tier_keys):
            status = self.general_questions.get(tier_key, {}).get('status', '')
            if status == 'completed':
                continue

            self.current_tier_idx = idx
            if status != 'in_process':
                self.general_questions[tier_key]['status'] = 'in_process'
            return

        # If no tier left, mark interview complete
        self.current_tier_idx = len(self.tier_keys)

    def get_current_tier_key(self):
        """Get current tier key"""
        if self.current_tier_idx < len(self.tier_keys):
            return self.tier_keys[self.current_tier_idx]
        return None

    def get_pending_questions(self, dataset, tier_key):
        """Get pending questions for a specific tier and dataset"""
        if not dataset or not tier_key or tier_key not in dataset:
            return []
            
        tier = dataset.get(tier_key, {})
        
        # For general questions, respect the tier status
        if dataset == self.general_questions:
            tier_status = tier.get('status', '')
            if tier_status != 'in_process' and tier_status != '':
                return []
        
        questions = tier.get('questions', [])
        if not isinstance(questions, list):
            return []
            
        return [q for q in questions if isinstance(q, dict) and q.get('qest') == 'pending']
    
    def get_current_question(self):
        """Get the current question to be asked"""
        tier_key = self.get_current_tier_key()
        if not tier_key:
            return None
            
        if self.current_phase == 'general':
            pending = self.get_pending_questions(self.general_questions, tier_key)
            if pending and 0 <= self.current_q_idx < len(pending):
                question_data = pending[self.current_q_idx]
                return {
                    'question': question_data.get('question', ''),
                    'field': question_data.get('field', ''),
                    'phase': 'general',
                    'tier': tier_key,
                    'question_id': question_data.get('id', ''),
                    'category': question_data.get('category', 'general')
                }
        elif self.current_phase == 'category':
            pending = self.get_pending_questions(self.category_questions, tier_key)
            if pending and 0 <= self.current_q_idx < len(pending):
                question_data = pending[self.current_q_idx]
                return {
                    'question': question_data.get('question', ''),
                    'field': question_data.get('field', ''),
                    'phase': 'category',
                    'tier': tier_key,
                    'question_id': question_data.get('id', ''),
                    'category': question_data.get('category', self.selected_category.lower())
                }
        
        return None

    def regenerate_question_with_motivation(self, next_question: str, user_response: str = None) -> str:
        """Generate a conversational follow-up by acknowledging the user's response"""
        try:
            client = OpenAI(api_key=self.openai_key)

            prompt = f"Next question: {next_question}\n"
            if user_response:
                prompt += f"User's previous response: {user_response}\n"
            prompt += (
                "Please write a natural, conversational transition that acknowledges the user's response "
                "and leads into the next question. Keep it warm, curious, and supportive."
            )

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a friendly, engaging interviewer having a casual, supportive conversation. When provided with a user's previous response and a next question, create a natural, conversational transition. Acknowledge or positively reflect on the user's response, and then smoothly ask the next question. Keep the tone friendly, curious, and encouraging, and avoid robotic phrasing. Do not rigidly repeat the question; weave it naturally into your words."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating motivated question: {e}")
            return next_question  # Fallback to original question

    def submit_answer(self, answer):
        """Submit answer and update profile structure"""
        tier_key = self.get_current_tier_key()
        if not tier_key:
            return False
            
        current_q = self.get_current_question()
        if not current_q:
            return False
        
        # Update the question status in the appropriate dataset
        if self.current_phase == 'general':
            dataset = self.general_questions
        else:
            dataset = self.category_questions
            
        pending = self.get_pending_questions(dataset, tier_key)
        if pending and 0 <= self.current_q_idx < len(pending):
            # Find the question in the original dataset and mark as answered
            question_to_update = pending[self.current_q_idx]
            question_text = question_to_update.get('question', '')
            
            tier_questions = dataset.get(tier_key, {}).get('questions', [])
            for q in tier_questions:
                if q.get('question') == question_text:
                    q['qest'] = 'answered'
                    q['answered_at'] = datetime.utcnow().isoformat()
                    q['answer'] = answer
                    break
            
            # Update profile structure with the answer
            field_path = current_q.get('field', '')
            if field_path:
                self.update_profile_structure(field_path, answer)
            
            # Add to conversation history with enhanced metadata
            conversation_entry = {
                "question": current_q.get('question'),
                "answer": answer,
                "field": field_path,
                "phase": self.current_phase,
                "tier": tier_key,
                "timestamp": datetime.utcnow().isoformat(),
                "question_id": current_q.get('question_id', ''),
                "category": current_q.get('category', 'general'),
                "answer_metadata": {
                    "word_count": len(answer.split()),
                    "character_count": len(answer),
                    "answer_quality": self._assess_answer_quality(answer)
                }
            }
            
            self.conversation.append(conversation_entry)
            
            # Move to next question or phase
            self.advance_to_next()
            
            return True
        
        return False

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

    def update_profile_structure(self, field_path, answer):
        """Update profile structure with the answer"""
        if not field_path or not isinstance(field_path, str):
            return
            
        keys = field_path.split('.')
        current = self.profile_structure
        
        try:
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            final_key = keys[-1]
            if final_key in current and isinstance(current[final_key], dict):
                current[final_key]['value'] = answer
                current[final_key]['updated_at'] = datetime.utcnow().isoformat()
            else:
                if final_key not in current:
                    current[final_key] = {}
                if isinstance(current[final_key], dict):
                    current[final_key]['value'] = answer
                    current[final_key]['updated_at'] = datetime.utcnow().isoformat()
                else:
                    current[final_key] = {
                        'value': answer,
                        'updated_at': datetime.utcnow().isoformat()
                    }
        except (KeyError, TypeError, AttributeError) as e:
            print(f"Error updating profile structure for field '{field_path}': {e}")
            return

    def advance_to_next(self):
        """Advance to next question, phase, or tier"""
        tier_key = self.get_current_tier_key()
        if not tier_key:
            return
        
        if self.current_phase == 'general':
            pending = self.get_pending_questions(self.general_questions, tier_key)
            if pending and self.current_q_idx + 1 < len(pending):
                self.current_q_idx += 1
            else:
                # Move to category phase
                self.current_phase = 'category'
                self.current_q_idx = 0
                
                cat_pending = self.get_pending_questions(self.category_questions, tier_key)
                if not cat_pending:
                    self.complete_current_tier()
                    self.advance_to_next_tier()
        
        elif self.current_phase == 'category':
            pending = self.get_pending_questions(self.category_questions, tier_key)
            if pending and self.current_q_idx + 1 < len(pending):
                self.current_q_idx += 1
            else:
                self.complete_current_tier()
                self.advance_to_next_tier()

    def complete_current_tier(self):
        """Mark current tier as completed"""
        tier_key = self.get_current_tier_key()
        if tier_key:
            if tier_key in self.general_questions:
                self.general_questions[tier_key]['status'] = 'completed'
                self.general_questions[tier_key]['completed_at'] = datetime.utcnow().isoformat()
            
            if tier_key in self.category_questions:
                self.category_questions[tier_key]['status'] = 'completed'
                self.category_questions[tier_key]['completed_at'] = datetime.utcnow().isoformat()

    def advance_to_next_tier(self):
        """Move to the next tier"""
        if self.current_tier_idx + 1 < len(self.tier_keys):
            self.current_tier_idx += 1
            self.current_phase = 'general'
            self.current_q_idx = 0
            
            next_tier_key = self.get_current_tier_key()
            if next_tier_key and next_tier_key in self.general_questions:
                self.general_questions[next_tier_key]['status'] = 'in_process'
        else:
            self.current_tier_idx = len(self.tier_keys)
            self.completed_at = datetime.utcnow()

    def is_complete(self):
        """Check if interview is complete"""
        return self.current_tier_idx >= len(self.tier_keys)

    def save_to_firestore(self):
        """Save all data back to Firestore with user-specific documents"""
        try:
            # Save user-specific profile structure
            profile_doc_id = f"{self.user_id}_profile_structure.json" if self.user_id else "profile_structure.json"
            self.db.collection("user_collection").document(profile_doc_id).set(self.profile_structure)
            
            # Save updated question collections
            self.db.collection("question_collection").document("general_tiered_questions.json").set(self.general_questions)
            self.db.collection("question_collection").document(self.cat_doc_id).set(self.category_questions)
            
            return True
        except Exception as e:
            print(f"Failed to save to Firestore: {e}")
            return False

    def to_dict(self):
        """Convert agent state to dictionary for database storage"""
        return {
            "user_id": self.user_id,
            "selected_category": self.selected_category,
            "current_tier_idx": self.current_tier_idx,
            "current_phase": self.current_phase,
            "current_q_idx": self.current_q_idx,
            "tier_keys": self.tier_keys,
            "cat_doc_id": self.cat_doc_id,
            "conversation": self.conversation,
            "follow_up_count": self.follow_up_count,
            "started_at": self.started_at.isoformat() if hasattr(self.started_at, 'isoformat') else str(self.started_at),
            "completed_at": self.completed_at.isoformat() if self.completed_at and hasattr(self.completed_at, 'isoformat') else None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

    @classmethod
    def from_dict(cls, db, openai_key, data, selected_category="Movies"):
        """Create agent from database data"""
        user_id = data.get("user_id")
        agent = cls(db, openai_key, selected_category, user_id)
        
        # Restore state from database
        agent.current_tier_idx = data.get("current_tier_idx", 0)
        agent.current_phase = data.get("current_phase", 'general')
        agent.current_q_idx = data.get("current_q_idx", 0)
        agent.conversation = data.get("conversation", [])
        agent.follow_up_count = data.get("follow_up_count", 0)
        
        # Restore timestamps
        started_at_str = data.get("started_at")
        if started_at_str:
            try:
                agent.started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
            except:
                agent.started_at = datetime.utcnow()
        
        completed_at_str = data.get("completed_at")
        if completed_at_str:
            try:
                agent.completed_at = datetime.fromisoformat(completed_at_str.replace('Z', '+00:00'))
            except:
                agent.completed_at = None
        
        return agent

    def get_progress_summary(self):
        """Get a summary of interview progress"""
        total_questions = 0
        answered_questions = len(self.conversation)
        
        # Count total questions across all tiers
        for tier_key in self.tier_keys:
            if tier_key in self.general_questions:
                total_questions += len(self.general_questions[tier_key].get('questions', []))
            if tier_key in self.category_questions:
                total_questions += len(self.category_questions[tier_key].get('questions', []))
        
        progress_percentage = (answered_questions / total_questions * 100) if total_questions > 0 else 0
        
        return {
            "current_tier": self.current_tier_idx + 1,
            "total_tiers": len(self.tier_keys),
            "current_phase": self.current_phase,
            "questions_answered": answered_questions,
            "total_questions": total_questions,
            "progress_percentage": round(progress_percentage, 2),
            "is_complete": self.is_complete(),
            "selected_category": self.selected_category,
            "started_at": self.started_at.isoformat() if hasattr(self.started_at, 'isoformat') else str(self.started_at),
            "duration_minutes": self._calculate_duration_minutes()
        }

    def _calculate_duration_minutes(self):
        """Calculate how long the interview has been running"""
        try:
            if self.completed_at:
                end_time = self.completed_at
            else:
                end_time = datetime.utcnow()
            
            duration = end_time - self.started_at
            return round(duration.total_seconds() / 60, 2)
        except:
            return 0

    def get_conversation_analytics(self):
        """Get analytics about the conversation"""
        if not self.conversation:
            return {}
        
        word_counts = []
        quality_distribution = {}
        tier_distribution = {}
        
        for entry in self.conversation:
            # Word count analysis
            answer_meta = entry.get("answer_metadata", {})
            word_count = answer_meta.get("word_count", 0)
            word_counts.append(word_count)
            
            # Quality distribution
            quality = answer_meta.get("answer_quality", "unknown")
            quality_distribution[quality] = quality_distribution.get(quality, 0) + 1
            
            # Tier distribution
            tier = entry.get("tier", "unknown")
            tier_distribution[tier] = tier_distribution.get(tier, 0) + 1
        
        return {
            "total_responses": len(self.conversation),
            "average_word_count": sum(word_counts) / len(word_counts) if word_counts else 0,
            "total_words": sum(word_counts),
            "longest_response": max(word_counts) if word_counts else 0,
            "shortest_response": min(word_counts) if word_counts else 0,
            "quality_distribution": quality_distribution,
            "tier_distribution": tier_distribution,
            "phases_completed": len(set([entry.get("phase") for entry in self.conversation])),
            "categories_covered": len(set([entry.get("category") for entry in self.conversation]))
        }

    def generate_follow_up(self, question: str, answer: str, context: Dict[str, Any] = None) -> str:
        """Generate follow-up question based on user's answer with enhanced context"""
        try:
            client = OpenAI(api_key=self.openai_key)
            
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
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an empathetic interview agent that creates insightful follow-up questions to understand users better."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=100
            )
            
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating follow-up: {e}")
            return "Can you tell me more about that?"

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
        try:
            client = OpenAI(api_key=self.openai_key)
            
            prompt = f"""Assess if this interview response needs a follow-up question (respond with only YES or NO):
            
            Response: {answer[:300]}
            
            Consider:
            - Does it include specific examples or details?
            - Does it show personal reflection or depth?
            - Does it fully address what was asked?
            - Would a follow-up help uncover more valuable insights?
            
            Response length: {word_count} words
            """
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
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