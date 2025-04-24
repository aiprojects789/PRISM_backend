from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.core.security import get_password_hash, create_access_token, verify_firebase_token, get_current_user
from app.models.user import UserCreate, UserResponse, TokenResponse
from app.core.firebase import get_firestore_client
from app.core.config import get_settings
from firebase_admin import auth
from datetime import datetime, timedelta

router = APIRouter()

@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate):
    try:
        # Create user in Firebase Auth
        user = auth.create_user(
            email=user_data.email,
            password=user_data.password,
            display_name=user_data.display_name or user_data.email.split('@')[0]
        )
        
        # Store additional user info in Firestore
        db = get_firestore_client()
        db.collection("users").document(user.uid).set({
            "email": user_data.email,
            "display_name": user_data.display_name or user_data.email.split('@')[0],
            "created_at": datetime.utcnow()
        })
        
        return UserResponse(
            user_id=user.uid,
            email=user_data.email,
            display_name=user_data.display_name or user_data.email.split('@')[0],
            created_at=datetime.utcnow()
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to register user: {str(e)}"
        )

@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        # Sign in with Firebase Auth
        user = auth.get_user_by_email(form_data.username)
        
        # Create custom token
        settings = get_settings()
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.uid}, 
            expires_delta=access_token_expires
        )
        
        # Fetch user data from Firestore
        db = get_firestore_client()
        user_doc = db.collection("users").document(user.uid).get()
        user_data = user_doc.to_dict()
        
        return TokenResponse(
            access_token=access_token,
            user=UserResponse(
                user_id=user.uid,
                email=user.email,
                display_name=user.display_name,
                created_at=user_data.get("created_at")
            )
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/token", response_model=TokenResponse)
async def token_login(id_token: str):
    # Verify Firebase ID token
    decoded_token = verify_firebase_token(id_token)
    user_id = decoded_token["uid"]
    
    # Get user data
    user = auth.get_user(user_id)
    
    # Create session token
    settings = get_settings()
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_id}, 
        expires_delta=access_token_expires
    )
    
    # Fetch user data from Firestore
    db = get_firestore_client()
    user_doc = db.collection("users").document(user_id).get()
    user_data = user_doc.to_dict()
    
    return TokenResponse(
        access_token=access_token,
        user=UserResponse(
            user_id=user_id,
            email=user.email,
            display_name=user.display_name,
            created_at=user_data.get("created_at")
        )
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user = Depends(get_current_user)):
    db = get_firestore_client()
    user_doc = db.collection("users").document(current_user.uid).get()
    user_data = user_doc.to_dict()
    
    return UserResponse(
        user_id=current_user.uid,
        email=current_user.email,
        display_name=current_user.display_name,
        created_at=user_data.get("created_at")
    )