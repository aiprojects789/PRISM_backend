from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from app.routers import auth, interview, recommendations, questions, profiles, conversations
from app.core.firebase import initialize_firebase
from app.core.config import get_settings
from mangum import Mangum
# Initialize settings
settings = get_settings()

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION
)

# Add CORS middleware with proper configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Use the property that handles string/list conversion
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Firebase on startup
@app.on_event("startup")
async def startup_event():
    initialize_firebase()

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(interview.router, prefix="/api/interview", tags=["Interview"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["Recommendations"])
app.include_router(questions.router, prefix="/api/questions", tags=["Question Generation"])
app.include_router(profiles.router, prefix="/api/profiles", tags=["Profile Management"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["Conversation History"])

@app.get("/")
async def root():
    return {
        "message": "Welcome to Prism API",
        "version": settings.VERSION,
        "description": settings.DESCRIPTION,
        "endpoints": {
            "auth": "/api/auth",
            "interview": "/api/interview", 
            "recommendations": "/api/recommendations",
            "questions": "/api/questions",
            "profiles": "/api/profiles",
            "conversations": "/api/conversations",
            "docs": "/docs",
            "health": "/health"
        }
    }
handler = Mangum(app)
@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "timestamp": "2024-01-01T00:00:00Z",
        "version": settings.VERSION,
        "debug": settings.DEBUG
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
