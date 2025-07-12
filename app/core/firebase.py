# app/core/firebase.py
import firebase_admin
from firebase_admin import credentials, firestore
from app.core.config import get_settings
from typing import Optional

# Global Firebase client
_firestore_client: Optional[firestore.Client] = None

def get_firestore_client() -> firestore.Client:
    """Initialize and return Firestore client (singleton pattern)"""
    global _firestore_client
    
    if _firestore_client is None:
        settings = get_settings()
        
        # Create credentials from settings
        cred_dict = settings.firebase_credentials
        cred = credentials.Certificate(cred_dict)
        
        # Initialize Firebase app if not already initialized
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        
        _firestore_client = firestore.client()
    
    return _firestore_client

def initialize_firebase():
    """Initialize Firebase (call this at app startup)"""
    get_firestore_client()
    print("Firebase initialized successfully")

def close_firestore_client():
    """Close Firestore client (for cleanup)"""
    global _firestore_client
    if _firestore_client:
        _firestore_client = None
    
    # Delete Firebase app
    if firebase_admin._apps:
        firebase_admin.delete_app(firebase_admin.get_app())