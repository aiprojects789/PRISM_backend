import firebase_admin
from firebase_admin import credentials, firestore
from app.core.config import get_settings

def initialize_firebase():
    """Initialize Firebase Admin SDK if not already initialized"""
    settings = get_settings()
    
    if not firebase_admin._apps:
        cred = credentials.Certificate(dict(settings.FIREBASE_CONFIG))
        firebase_admin.initialize_app(cred)
    
    return firestore.client()

def get_firestore_client():
    """Get Firestore client"""
    if not firebase_admin._apps:
        initialize_firebase()
    return firestore.client()