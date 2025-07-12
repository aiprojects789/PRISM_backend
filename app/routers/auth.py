# from fastapi import APIRouter, Depends, HTTPException, status
# from fastapi.security import OAuth2PasswordRequestForm
# from app.core.security import get_password_hash, create_access_token, verify_firebase_token, get_current_user, verify_password
# from app.models.user import UserCreate, UserResponse, TokenResponse
# from app.core.firebase import get_firestore_client
# from app.core.config import get_settings
# from firebase_admin import auth, firestore
# from datetime import datetime, timedelta

# router = APIRouter()

# @router.post("/register", response_model=UserResponse)
# async def register_user(user_data: UserCreate):
#     """Register a new user by saving their details to Firestore."""
#     try:
#         hashed_password = get_password_hash(user_data.password)
#         firestore_db = firestore.client()
#         users_collection = firestore_db.collection("users")

#         # Check if user already exists
#         query = users_collection.where("email", "==", user_data.email).limit(1)
#         results = query.get()
#         if results:
#             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

#         # Create new user
#         new_user_ref = users_collection.document()
#         user_id = new_user_ref.id

#         firestore_data = {
#             "email": user_data.email,
#             "hashed_password": hashed_password,
#             "display_name": user_data.display_name or user_data.email.split('@')[0],
#             "created_at": datetime.utcnow()
#         }
#         new_user_ref.set(firestore_data)

#         return UserResponse(
#             user_id=user_id,
#             email=user_data.email,
#             display_name=user_data.display_name or user_data.email.split('@')[0],
#             created_at=datetime.utcnow()
#         )
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail=f"Failed to register user: {str(e)}"
#         )

# @router.post("/login", response_model=TokenResponse)
# async def login(form_data: OAuth2PasswordRequestForm = Depends()):
#     """Authenticate a user and return a JWT access token."""
#     firestore_db = firestore.client()
#     users_collection = firestore_db.collection("users")

#     try:
#         # Find user by email
#         query = users_collection.where("email", "==", form_data.username).limit(1)
#         results = query.get()

#         if not results:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Incorrect email or password",
#                 headers={"WWW-Authenticate": "Bearer"},
#             )

#         user_doc = results[0]
#         user_data = user_doc.to_dict()
#         hashed_password = user_data.get("hashed_password")
#         user_id = user_doc.id

#         # Verify password
#         if not hashed_password or not verify_password(form_data.password, hashed_password):
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Incorrect email or password",
#                 headers={"WWW-Authenticate": "Bearer"},
#             )

#         # Create access token
#         settings = get_settings()
#         access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
#         access_token = create_access_token(
#             data={"sub": user_id}, expires_delta=access_token_expires
#         )

#         return TokenResponse(
#             access_token=access_token,
#             token_type="bearer",
#             user=UserResponse(
#                 user_id=user_id,
#                 email=user_data.get("email"),
#                 display_name=user_data.get("display_name"),
#                 created_at=user_data.get("created_at"),
#             ),
#         )
#     except HTTPException as e:
#         raise e
#     except Exception:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Could not log in user",
#             headers={"WWW-Authenticate": "Bearer"},
#         )

# @router.get("/me", response_model=UserResponse)
# async def get_current_user_info(current_user_id: str = Depends(get_current_user)):
#     """Retrieve the authenticated user's profile information."""
#     firestore_db = firestore.client()

#     try:
#         user_doc = firestore_db.collection("users").document(current_user_id).get()

#         if not user_doc.exists:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND, detail="User not found in Firestore"
#             )
#         user_data = user_doc.to_dict()

#         return UserResponse(
#             user_id=current_user_id,
#             email=user_data.get("email"),
#             display_name=user_data.get("display_name"),
#             created_at=user_data.get("created_at"),
#         )
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Error fetching user data: {str(e)}",
#         )
# app/routers/auth.py - Enhanced with proper user setup for multi-user app

# app/routers/auth.py - Enhanced with proper user setup for multi-user app

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.core.security import get_password_hash, create_access_token, verify_firebase_token, get_current_user, verify_password
from app.models.user import UserCreate, UserResponse, TokenResponse
from app.core.firebase import get_firestore_client
from app.core.config import get_settings
from firebase_admin import auth, firestore
from datetime import datetime, timedelta

router = APIRouter()

def setup_new_user_collections(user_id: str, db):
    """Set up initial collections and documents for a new user"""
    try:
        # Create user metadata document
        user_metadata = {
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "last_login": datetime.utcnow(),
            "profile_completed": False,
            "collections_initialized": True,
            "app_version": "1.0",
            "user_preferences": {
                "notification_enabled": True,
                "data_sharing_consent": False,
                "theme": "light"
            }
        }
        
        db.collection("user_metadata").document(user_id).set(user_metadata)
        
        # Initialize user conversations collection
        user_conversations_init = {
            "user_id": user_id,
            "initialized_at": datetime.utcnow(),
            "total_sessions": 0,
            "total_messages": 0
        }
        
        db.collection("user_conversations").document(user_id).set(user_conversations_init)
        
        # Initialize user recommendations collection
        user_recommendations_init = {
            "user_id": user_id,
            "initialized_at": datetime.utcnow(),
            "total_recommendations": 0,
            "categories_explored": []
        }
        
        db.collection("user_recommendations").document(user_id).set(user_recommendations_init)
        
        # Initialize user profiles collection
        user_profiles_init = {
            "user_id": user_id,
            "initialized_at": datetime.utcnow(),
            "active_profile_id": None,
            "total_profiles": 0
        }
        
        db.collection("user_profiles").document(user_id).set(user_profiles_init)
        
        # Create initial empty profile structure for the user
        initial_profile_structure = {
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "version": "1.0",
            "generalprofile": {},
            "recommendationProfiles": {},
            "simulationPreferences": {},
            "completion_status": {
                "general": 0,  # percentage
                "categories": {}
            }
        }
        
        db.collection("user_collection").document(f"{user_id}_profile_structure.json").set(initial_profile_structure)
        
        print(f"Successfully initialized collections for user: {user_id}")
        
    except Exception as e:
        print(f"Error setting up user collections: {e}")
        # Don't raise exception here to avoid blocking user registration
        # Log the error for manual intervention if needed

@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate):
    """Register a new user by saving their details to Firestore."""
    try:
        hashed_password = get_password_hash(user_data.password)
        firestore_db = firestore.client()
        users_collection = firestore_db.collection("users")

        # Check if user already exists
        query = users_collection.where("email", "==", user_data.email).limit(1)
        results = query.get()
        if results:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

        # Create new user
        new_user_ref = users_collection.document()
        user_id = new_user_ref.id

        firestore_data = {
            "user_id": user_id,
            "email": user_data.email,
            "hashed_password": hashed_password,
            "display_name": user_data.display_name or user_data.email.split('@')[0],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "is_verified": False,
            "login_count": 0,
            "last_login": None
        }
        new_user_ref.set(firestore_data)
        
        # Set up user collections and initial data
        setup_new_user_collections(user_id, firestore_db)

        return UserResponse(
            user_id=user_id,
            email=user_data.email,
            display_name=user_data.display_name or user_data.email.split('@')[0],
            created_at=datetime.utcnow()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to register user: {str(e)}"
        )

@router.post("/login", response_model=TokenResponse)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate a user and return a JWT access token."""
    firestore_db = firestore.client()
    users_collection = firestore_db.collection("users")

    try:
        # Find user by email
        query = users_collection.where("email", "==", form_data.username).limit(1)
        results = query.get()

        if not results:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_doc = results[0]
        user_data = user_doc.to_dict()
        hashed_password = user_data.get("hashed_password")
        user_id = user_doc.id

        # Verify password
        if not hashed_password or not verify_password(form_data.password, hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Update login statistics
        login_count = user_data.get("login_count", 0) + 1
        user_doc.reference.update({
            "last_login": datetime.utcnow(),
            "login_count": login_count,
            "updated_at": datetime.utcnow()
        })
        
        # Update user metadata
        try:
            user_metadata_ref = firestore_db.collection("user_metadata").document(user_id)
            user_metadata_doc = user_metadata_ref.get()
            
            if user_metadata_doc.exists:
                user_metadata_ref.update({
                    "last_login": datetime.utcnow(),
                    "login_count": login_count
                })
            else:
                # If metadata doesn't exist, create it (for existing users)
                setup_new_user_collections(user_id, firestore_db)
        except Exception as e:
            print(f"Error updating user metadata: {e}")

        # Create access token
        settings = get_settings()
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user_id}, expires_delta=access_token_expires
        )

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse(
                user_id=user_id,
                email=user_data.get("email"),
                display_name=user_data.get("display_name"),
                created_at=user_data.get("created_at"),
            ),
        )
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not log in user",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user_id: str = Depends(get_current_user)):
    """Retrieve the authenticated user's profile information."""
    firestore_db = firestore.client()

    try:
        user_doc = firestore_db.collection("users").document(current_user_id).get()

        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found in Firestore"
            )
        user_data = user_doc.to_dict()

        return UserResponse(
            user_id=current_user_id,
            email=user_data.get("email"),
            display_name=user_data.get("display_name"),
            created_at=user_data.get("created_at"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user data: {str(e)}",
        )

@router.get("/profile/status")
async def get_user_profile_status(current_user_id: str = Depends(get_current_user)):
    """Get user's profile completion status and app usage statistics"""
    try:
        firestore_db = firestore.client()
        
        # Get user metadata
        user_metadata_doc = firestore_db.collection("user_metadata").document(current_user_id).get()
        metadata = user_metadata_doc.to_dict() if user_metadata_doc.exists else {}
        
        # Get profile completion status
        profile_doc = firestore_db.collection("user_collection").document(f"{current_user_id}_profile_structure.json").get()
        profile_data = profile_doc.to_dict() if profile_doc.exists else {}
        
        # Get conversation statistics
        conversations_doc = firestore_db.collection("user_conversations").document(current_user_id).get()
        conversations_data = conversations_doc.to_dict() if conversations_doc.exists else {}
        
        # Get recommendation statistics
        recommendations_doc = firestore_db.collection("user_recommendations").document(current_user_id).get()
        recommendations_data = recommendations_doc.to_dict() if recommendations_doc.exists else {}
        
        # Calculate profile completion percentage
        completion_status = profile_data.get("completion_status", {})
        general_completion = completion_status.get("general", 0)
        category_completions = completion_status.get("categories", {})
        
        overall_completion = general_completion
        if category_completions:
            category_avg = sum(category_completions.values()) / len(category_completions)
            overall_completion = (general_completion + category_avg) / 2
        
        return {
            "user_id": current_user_id,
            "profile_status": {
                "overall_completion": round(overall_completion, 2),
                "general_profile_completion": general_completion,
                "category_completions": category_completions,
                "profile_exists": profile_doc.exists
            },
            "app_usage": {
                "total_conversations": conversations_data.get("total_sessions", 0),
                "total_messages": conversations_data.get("total_messages", 0),
                "total_recommendations": recommendations_data.get("total_recommendations", 0),
                "categories_explored": recommendations_data.get("categories_explored", []),
                "login_count": metadata.get("login_count", 0),
                "last_login": metadata.get("last_login"),
                "member_since": metadata.get("created_at")
            },
            "preferences": metadata.get("user_preferences", {}),
            "collections_initialized": metadata.get("collections_initialized", False)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching profile status: {str(e)}"
        )

@router.put("/preferences")
async def update_user_preferences(
    preferences: dict,
    current_user_id: str = Depends(get_current_user)
):
    """Update user preferences"""
    try:
        firestore_db = firestore.client()
        
        # Update user preferences in metadata
        user_metadata_ref = firestore_db.collection("user_metadata").document(current_user_id)
        
        user_metadata_ref.update({
            "user_preferences": preferences,
            "updated_at": datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": "User preferences updated successfully",
            "preferences": preferences
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating preferences: {str(e)}"
        )

@router.post("/logout")
async def logout_user(current_user_id: str = Depends(get_current_user)):
    """Log out user and update last activity"""
    try:
        firestore_db = firestore.client()
        
        # Update last activity
        user_metadata_ref = firestore_db.collection("user_metadata").document(current_user_id)
        user_metadata_ref.update({
            "last_activity": datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": "User logged out successfully"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error during logout: {str(e)}"
        )

@router.delete("/account")
async def delete_user_account(current_user_id: str = Depends(get_current_user)):
    """Delete user account and all associated data"""
    try:
        firestore_db = firestore.client()
        
        # This is a soft delete - mark user as inactive instead of hard delete
        # In production, you might want to implement a more comprehensive deletion process
        
        # Mark user as inactive
        user_ref = firestore_db.collection("users").document(current_user_id)
        user_ref.update({
            "is_active": False,
            "deleted_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        
        # Mark all user data as inactive
        collections_to_deactivate = [
            "user_metadata",
            "user_conversations", 
            "user_recommendations",
            "user_profiles"
        ]
        
        for collection_name in collections_to_deactivate:
            try:
                doc_ref = firestore_db.collection(collection_name).document(current_user_id)
                if doc_ref.get().exists:
                    doc_ref.update({
                        "is_active": False,
                        "deleted_at": datetime.utcnow()
                    })
            except Exception as e:
                print(f"Error deactivating {collection_name}: {e}")
        
        # Deactivate interview sessions
        try:
            sessions_query = firestore_db.collection("interview_sessions").where("user_id", "==", current_user_id)
            for session in sessions_query.stream():
                session.reference.update({
                    "is_active": False,
                    "deleted_at": datetime.utcnow()
                })
        except Exception as e:
            print(f"Error deactivating interview sessions: {e}")
        
        return {
            "success": True,
            "message": "Account has been deactivated. All data has been marked for deletion."
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting account: {str(e)}"
        )

@router.post("/admin/setup-existing-users")
async def setup_existing_users(current_user_id: str = Depends(get_current_user)):
    """
    Admin endpoint to set up collections for existing users who were created 
    before the enhanced user setup was implemented
    """
    try:
        firestore_db = firestore.client()
        
        # This should only be run by admin users
        # Add admin check here in production
        
        # Get all users
        users_ref = firestore_db.collection("users")
        users = users_ref.stream()
        
        setup_count = 0
        for user_doc in users:
            user_data = user_doc.to_dict()
            user_id = user_doc.id
            
            # Check if user already has metadata collection
            metadata_doc = firestore_db.collection("user_metadata").document(user_id).get()
            
            if not metadata_doc.exists:
                print(f"Setting up collections for existing user: {user_id}")
                setup_new_user_collections(user_id, firestore_db)
                setup_count += 1
        
        return {
            "success": True,
            "message": f"Set up collections for {setup_count} existing users",
            "setup_count": setup_count
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error setting up existing users: {str(e)}"
        )