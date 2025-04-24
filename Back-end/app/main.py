from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, interview, recommendations
from app.core.firebase import initialize_firebase

# Initialize the app
app = FastAPI(
    title="Prism API",
    description="API for Prism digital twin and recommendation system",
    version="1.0.0"
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Firebase
initialize_firebase()

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(interview.router, prefix="/api/interview", tags=["Interview"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["Recommendations"])

@app.get("/")
async def root():
    return {"message": "Welcome to Prism API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}