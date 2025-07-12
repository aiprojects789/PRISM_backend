#!/usr/bin/env python3
"""
Standalone script to list all Firestore collections
Run this file directly to see all collections in your database

Usage:
    python list_firestore_collections.py
"""

import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from datetime import datetime

def load_env_file():
    """Load environment variables from .env file"""
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value
        print("✅ Loaded .env file")
        return True
    return False

def create_firebase_config_from_env():
    """Create Firebase config from environment variables"""
    try:
        # Load .env file first
        load_env_file()
        
        # Extract Firebase config from environment
        firebase_config = {
            "type": os.environ.get("FIREBASE_CONFIG__type"),
            "project_id": os.environ.get("FIREBASE_CONFIG__project_id"),
            "private_key_id": os.environ.get("FIREBASE_CONFIG__private_key_id"),
            "private_key": os.environ.get("FIREBASE_CONFIG__private_key", "").replace("\\n", "\n"),
            "client_email": os.environ.get("FIREBASE_CONFIG__client_email"),
            "client_id": os.environ.get("FIREBASE_CONFIG__client_id"),
            "auth_uri": os.environ.get("FIREBASE_CONFIG__auth_uri"),
            "token_uri": os.environ.get("FIREBASE_CONFIG__token_uri"),
            "auth_provider_x509_cert_url": os.environ.get("FIREBASE_CONFIG__auth_provider_x509_cert_url"),
            "client_x509_cert_url": os.environ.get("FIREBASE_CONFIG__client_x509_cert_url")
        }
        
        # Check if all required fields are present
        required_fields = ["type", "project_id", "private_key", "client_email"]
        missing_fields = [field for field in required_fields if not firebase_config.get(field)]
        
        if missing_fields:
            print(f"❌ Missing Firebase config fields: {missing_fields}")
            return None
        
        print("✅ Firebase config loaded from .env file")
        return firebase_config
        
    except Exception as e:
        print(f"❌ Error loading Firebase config from .env: {e}")
        return None

def initialize_firebase():
    """Initialize Firebase Admin SDK"""
    try:
        # Try to initialize if not already done
        if not firebase_admin._apps:
            # Option 1: Use .env file configuration
            firebase_config = create_firebase_config_from_env()
            if firebase_config:
                cred = credentials.Certificate(firebase_config)
                firebase_admin.initialize_app(cred)
                print("✅ Firebase initialized from .env file")
                return firestore.client()
            
            # Option 2: Use service account key file
            elif os.path.exists("serviceAccountKey.json"):
                cred = credentials.Certificate("serviceAccountKey.json")
                firebase_admin.initialize_app(cred)
                print("✅ Firebase initialized with service account key")
                return firestore.client()
            
            # Option 3: Use environment variable
            elif os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred)
                print("✅ Firebase initialized with environment credentials")
                return firestore.client()
            
            # Option 4: Default credentials (if running on Google Cloud)
            else:
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred)
                print("✅ Firebase initialized with default credentials")
                return firestore.client()
        else:
            print("✅ Firebase already initialized")
            return firestore.client()
            
    except Exception as e:
        print(f"❌ Error initializing Firebase: {e}")
        print("\n💡 Setup options:")
        print("1. Keep your .env file in the same directory as this script")
        print("2. Download serviceAccountKey.json from Firebase Console")
        print("3. Set GOOGLE_APPLICATION_CREDENTIALS environment variable")
        return None

def get_all_collections_simple():
    """Get just the collection names"""
    db = initialize_firebase()
    if not db:
        return []
    
    try:
        collections = db.collections()
        return [collection.id for collection in collections]
    except Exception as e:
        print(f"❌ Error getting collections: {e}")
        return []

def get_collection_details(collection_name):
    """Get detailed info about a specific collection"""
    db = initialize_firebase()
    if not db:
        return None
    
    try:
        collection_ref = db.collection(collection_name)
        
        # Get sample documents (limit to avoid long queries)
        docs = list(collection_ref.limit(10).stream())
        doc_count = len(docs)
        
        # Get sample document
        sample_doc = None
        subcollections = []
        
        if docs:
            first_doc = docs[0]
            sample_doc = {
                "id": first_doc.id,
                "fields": list(first_doc.to_dict().keys())
            }
            
            # Check for subcollections
            try:
                subcolls = first_doc.reference.collections()
                subcollections = [subcoll.id for subcoll in subcolls]
            except:
                pass
        
        return {
            "name": collection_name,
            "document_count": doc_count,
            "sample_document": sample_doc,
            "subcollections": subcollections,
            "has_data": doc_count > 0
        }
        
    except Exception as e:
        print(f"❌ Error getting details for {collection_name}: {e}")
        return None

def print_collections_summary():
    """Print a summary of all collections"""
    print("🔥 FIRESTORE DATABASE COLLECTIONS")
    print("=" * 50)
    
    # Get all collections
    collections = get_all_collections_simple()
    
    if not collections:
        print("❌ No collections found or unable to connect to database")
        return
    
    print(f"📊 Found {len(collections)} collections:\n")
    
    # Print each collection with details
    for i, collection_name in enumerate(collections, 1):
        details = get_collection_details(collection_name)
        
        if details:
            status = "📄" if details["has_data"] else "📭"
            print(f"{i}. {status} {collection_name}")
            print(f"   Documents: {details['document_count']}")
            
            if details['subcollections']:
                print(f"   Subcollections: {', '.join(details['subcollections'])}")
            
            if details['sample_document']:
                fields = details['sample_document']['fields'][:5]  # Show first 5 fields
                fields_str = ', '.join(fields)
                if len(details['sample_document']['fields']) > 5:
                    fields_str += f" (+{len(details['sample_document']['fields']) - 5} more)"
                print(f"   Sample fields: {fields_str}")
            
            print()
        else:
            print(f"{i}. ❌ {collection_name} (error getting details)")

def check_expected_collections():
    """Check if expected collections for your app exist"""
    expected = [
        "users",
        "interview_sessions", 
        "user_profiles",
        "recommendation_history",
        "question_collections",
        "user_collection",
        "conversation_analytics",
        "user_conversations"
    ]
    
    existing = get_all_collections_simple()
    
    print("\n🔍 CHECKING EXPECTED COLLECTIONS")
    print("=" * 50)
    
    found = 0
    missing = []
    
    for collection in expected:
        if collection in existing:
            print(f"✅ {collection}")
            found += 1
        else:
            print(f"❌ {collection} - NOT FOUND")
            missing.append(collection)
    
    print(f"\n📊 Result: {found}/{len(expected)} expected collections found")
    
    if missing:
        print(f"\n⚠️  Missing collections:")
        for m in missing:
            print(f"   • {m}")
    
    # Show any unexpected collections
    unexpected = [col for col in existing if col not in expected]
    if unexpected:
        print(f"\n🆕 Additional collections found:")
        for col in unexpected:
            print(f"   • {col}")

def explore_specific_collection():
    """Interactive exploration of a specific collection"""
    collections = get_all_collections_simple()
    
    if not collections:
        print("❌ No collections available to explore")
        return
    
    print("\n🔍 EXPLORE SPECIFIC COLLECTION")
    print("=" * 50)
    print("Available collections:")
    
    for i, collection in enumerate(collections, 1):
        print(f"{i}. {collection}")
    
    try:
        choice = input(f"\nEnter collection name or number (1-{len(collections)}): ").strip()
        
        # Handle numeric choice
        if choice.isdigit():
            choice_num = int(choice)
            if 1 <= choice_num <= len(collections):
                collection_name = collections[choice_num - 1]
            else:
                print("❌ Invalid number")
                return
        else:
            collection_name = choice
        
        if collection_name not in collections:
            print(f"❌ Collection '{collection_name}' not found")
            return
        
        # Get detailed info
        details = get_collection_details(collection_name)
        if not details:
            return
        
        print(f"\n📁 Collection: {collection_name}")
        print(f"📄 Documents: {details['document_count']}")
        
        if details['subcollections']:
            print(f"📂 Subcollections: {', '.join(details['subcollections'])}")
        
        if details['sample_document']:
            print(f"🔧 Sample Document ID: {details['sample_document']['id']}")
            print(f"🔧 Fields: {', '.join(details['sample_document']['fields'])}")
        
        # Offer to show actual document data
        if details['has_data']:
            show_data = input("\nShow sample document data? (y/n): ").lower().startswith('y')
            if show_data:
                show_sample_document_data(collection_name)
        
    except KeyboardInterrupt:
        print("\n👋 Cancelled")
    except Exception as e:
        print(f"❌ Error: {e}")

def show_sample_document_data(collection_name):
    """Show actual data from a sample document"""
    db = initialize_firebase()
    if not db:
        return
    
    try:
        collection_ref = db.collection(collection_name)
        docs = list(collection_ref.limit(1).stream())
        
        if docs:
            doc = docs[0]
            data = doc.to_dict()
            
            print(f"\n📄 Sample Document Data:")
            print(f"Document ID: {doc.id}")
            print(json.dumps(data, indent=2, default=str))
        else:
            print("📭 No documents found")
            
    except Exception as e:
        print(f"❌ Error getting document data: {e}")

def main():
    """Main function - run the collection listing"""
    print("🚀 FIRESTORE COLLECTION EXPLORER")
    print("=" * 50)
    
    # Basic summary
    print_collections_summary()
    
    # Check expected collections
    check_expected_collections()
    
    # Ask if user wants to explore specific collection
    print("\n" + "=" * 50)
    try:
        explore = input("Explore a specific collection? (y/n): ").lower().startswith('y')
        if explore:
            explore_specific_collection()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()