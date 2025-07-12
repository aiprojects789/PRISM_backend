# app/core/database_migrations.py - Database schema setup and migrations

from datetime import datetime
from app.core.firebase import get_firestore_client
from typing import Dict, Any, List
import uuid

class DatabaseMigrations:
    def __init__(self):
        self.db = get_firestore_client()
    
    def create_indexes(self):
        """Create necessary indexes for optimal querying"""
        # Note: Firestore indexes are typically created through the Firebase console
        # or automatically when queries are first run. This is documentation of needed indexes.
        
        indexes_needed = [
            # User Conversations
            {
                "collection": "user_conversations/{userId}/sessions",
                "fields": ["user_id", "session_type", "is_active", "updated_at"]
            },
            {
                "collection": "user_conversations/{userId}/messages", 
                "fields": ["user_id", "session_id", "timestamp"]
            },
            
            # Interview Sessions
            {
                "collection": "interview_sessions",
                "fields": ["user_id", "is_active", "created_at"]
            },
            
            # User Recommendations
            {
                "collection": "user_recommendations/{userId}/recommendations",
                "fields": ["user_id", "category", "is_active", "generated_at"]
            },
            
            # Recommendation History
            {
                "collection": "recommendation_history",
                "fields": ["user_id", "category", "created_at"]
            },
            
            # Recommendation Feedback
            {
                "collection": "recommendation_feedback",
                "fields": ["recommendation_id", "user_id", "created_at"]
            },
            
            # User Profiles
            {
                "collection": "user_profiles/{userId}/profiles",
                "fields": ["user_id", "is_active", "created_at"]
            }
        ]
        
        print("Indexes needed for optimal performance:")
        for index in indexes_needed:
            print(f"Collection: {index['collection']}")
            print(f"Fields: {index['fields']}")
            print("---")
    
    def migrate_existing_data(self):
        """Migrate any existing data to new schema"""
        try:
            # This would handle migration of existing conversation data
            # if you have any data that needs to be restructured
            print("Starting data migration...")
            
            # Example: Migrate old conversation format to new format
            self._migrate_conversations()
            
            # Example: Add missing fields to existing documents
            self._add_missing_fields()
            
            print("Data migration completed successfully")
            
        except Exception as e:
            print(f"Error during data migration: {e}")
            raise
    
    def _migrate_conversations(self):
        """Migrate conversation data to new format"""
        try:
            # Get all user conversation collections
            users_ref = self.db.collection("user_conversations")
            
            for user_doc in users_ref.list_documents():
                user_id = user_doc.id
                
                # Check sessions collection
                sessions_ref = user_doc.collection("sessions")
                for session_doc in sessions_ref.stream():
                    session_data = session_doc.to_dict()
                    
                    # Add missing fields if they don't exist
                    updates = {}
                    
                    if "is_active" not in session_data:
                        updates["is_active"] = True
                    
                    if "metadata" not in session_data:
                        updates["metadata"] = {}
                    
                    if "last_message" not in session_data:
                        # Try to get last message from messages collection
                        messages_ref = user_doc.collection("messages")
                        last_message_query = messages_ref.where("session_id", "==", session_data.get("session_id")).order_by("timestamp", direction="DESCENDING").limit(1)
                        
                        try:
                            last_messages = list(last_message_query.stream())
                            if last_messages:
                                last_msg_data = last_messages[0].to_dict()
                                content = last_msg_data.get("content", "")
                                updates["last_message"] = content[:100] + "..." if len(content) > 100 else content
                                updates["last_message_role"] = last_msg_data.get("role", "user")
                        except:
                            updates["last_message"] = ""
                            updates["last_message_role"] = "user"
                    
                    if updates:
                        session_doc.reference.update(updates)
                        print(f"Updated session {session_data.get('session_id')} for user {user_id}")
            
        except Exception as e:
            print(f"Error migrating conversations: {e}")
    
    def _add_missing_fields(self):
        """Add missing fields to existing documents"""
        try:
            # Add missing fields to interview sessions if any exist
            interview_sessions = self.db.collection("interview_sessions").stream()
            
            for session_doc in interview_sessions:
                session_data = session_doc.to_dict()
                updates = {}
                
                if "is_active" not in session_data:
                    updates["is_active"] = True
                
                if "status" not in session_data:
                    updates["status"] = "in_progress"
                
                if updates:
                    session_doc.reference.update(updates)
            
            print("Added missing fields to existing documents")
            
        except Exception as e:
            print(f"Error adding missing fields: {e}")
    
    def setup_user_collections(self, user_id: str):
        """Set up initial collections for a new user"""
        try:
            # Create user-specific document structure
            user_setup = {
                "user_id": user_id,
                "created_at": datetime.utcnow(),
                "collections_initialized": True,
                "profile_version": "1.0"
            }
            
            # Initialize user metadata
            self.db.collection("user_metadata").document(user_id).set(user_setup)
            
            # Initialize empty collections by creating placeholder documents
            # These will be removed when real data is added
            
            # User conversations
            self.db.collection("user_conversations").document(user_id).set({
                "user_id": user_id,
                "initialized_at": datetime.utcnow()
            })
            
            # User recommendations
            self.db.collection("user_recommendations").document(user_id).set({
                "user_id": user_id,
                "initialized_at": datetime.utcnow()
            })
            
            # User profiles
            self.db.collection("user_profiles").document(user_id).set({
                "user_id": user_id,
                "initialized_at": datetime.utcnow()
            })
            
            print(f"User collections initialized for user: {user_id}")
            
        except Exception as e:
            print(f"Error setting up user collections: {e}")
            raise
    
    def cleanup_inactive_sessions(self, days_old: int = 30):
        """Clean up old inactive sessions"""
        try:
            from datetime import timedelta
            
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # Clean up old interview sessions
            old_sessions = self.db.collection("interview_sessions").where("updated_at", "<", cutoff_date).where("is_active", "==", False).stream()
            
            batch = self.db.batch()
            count = 0
            
            for session in old_sessions:
                batch.delete(session.reference)
                count += 1
                
                if count >= 500:  # Firestore batch limit
                    batch.commit()
                    batch = self.db.batch()
                    count = 0
            
            if count > 0:
                batch.commit()
            
            print(f"Cleaned up {count} old interview sessions")
            
        except Exception as e:
            print(f"Error cleaning up inactive sessions: {e}")
    
    def verify_data_integrity(self) -> Dict[str, Any]:
        """Verify data integrity across collections"""
        integrity_report = {
            "users_with_conversations": 0,
            "users_with_recommendations": 0,
            "users_with_profiles": 0,
            "orphaned_sessions": 0,
            "orphaned_messages": 0,
            "issues": []
        }
        
        try:
            # Get all users from different collections
            conversation_users = set()
            recommendation_users = set()
            profile_users = set()
            
            # Check user_conversations
            for doc in self.db.collection("user_conversations").list_documents():
                conversation_users.add(doc.id)
                integrity_report["users_with_conversations"] += 1
            
            # Check user_recommendations
            for doc in self.db.collection("user_recommendations").list_documents():
                recommendation_users.add(doc.id)
                integrity_report["users_with_recommendations"] += 1
            
            # Check user_profiles  
            for doc in self.db.collection("user_profiles").list_documents():
                profile_users.add(doc.id)
                integrity_report["users_with_profiles"] += 1
            
            # Check for orphaned interview sessions
            interview_sessions = self.db.collection("interview_sessions").stream()
            for session in interview_sessions:
                session_data = session.to_dict()
                user_id = session_data.get("user_id")
                
                if user_id and user_id not in conversation_users:
                    integrity_report["orphaned_sessions"] += 1
                    integrity_report["issues"].append(f"Orphaned interview session: {session.id}")
            
            return integrity_report
            
        except Exception as e:
            integrity_report["issues"].append(f"Error during integrity check: {str(e)}")
            return integrity_report

# Migration runner
def run_migrations():
    """Run all necessary migrations"""
    try:
        migrator = DatabaseMigrations()
        
        print("=== Starting Database Migrations ===")
        
        # Show required indexes
        migrator.create_indexes()
        
        # Migrate existing data
        migrator.migrate_existing_data()
        
        # Verify data integrity
        integrity_report = migrator.verify_data_integrity()
        print(f"Data Integrity Report: {integrity_report}")
        
        print("=== Migrations Completed ===")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    run_migrations()