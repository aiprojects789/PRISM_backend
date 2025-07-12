#!/usr/bin/env python3
"""
Prism FastAPI Startup Script
Main entry point for the Prism API application
"""
import uvicorn
from app.main import app
from app.core.firebase import initialize_firebase

def start_server():
    """Start the FastAPI server with Firebase initialization"""
    try:
        # Initialize Firebase
        initialize_firebase()
        print("🔥 Firebase initialized successfully")
        
        # Start the server
        print("🚀 Starting Prism API server...")
        print("📖 API Documentation: http://localhost:8000/docs")
        print("🔍 Alternative Docs: http://localhost:8000/redoc")
        print("❤️  Health Check: http://localhost:8000/health")
        
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,  # Set to False in production
            log_level="info"
        )
    except Exception as e:
        print(f"❌ Failed to start server: {e}")

if __name__ == "__main__":
    start_server()