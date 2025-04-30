from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from app.core.security import get_password_hash, create_access_token, verify_firebase_token, get_current_user, verify_password
from app.models.user import UserCreate, UserResponse, TokenResponse
from app.core.firebase import get_firestore_client
from app.core.config import get_settings
from firebase_admin import auth, firestore
from datetime import datetime, timedelta

router = APIRouter()

@router.post("/register", response_model=UserResponse)
async def register_user(user_data: UserCreate):
    """
    Registers a new user by saving their details to Firestore.

    Args:
        user_data (UserCreate): The user's registration information, including email and password.

    Returns:
        UserResponse: A response containing the created user's public information.

    Raises:
        HTTPException: If the email is already registered or any error occurs during the process.
    """
    try:
        # Hash the plain-text password using a secure hash function
        hashed_password = get_password_hash(user_data.password)
         # Initialize Firestore client
        firestore_db = firestore.client()
        users_collection = firestore_db.collection("users")

        # Check if a user with the same email already exists
        query = users_collection.where("email", "==", user_data.email).limit(1)
        results = query.get()
        if results:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

        # Generate a new user document reference (auto-generated ID)
        new_user_ref = users_collection.document()
        user_id = new_user_ref.id

        # Prepare user data to be stored in Firestore
        firestore_data = {
            "email": user_data.email,
            "hashed_password": hashed_password,
            "display_name": user_data.display_name or user_data.email.split('@')[0],
            "created_at": datetime.utcnow()
        }
        # Store the new user data in Firestore
        new_user_ref.set(firestore_data)

        # Return the user info (excluding the password)
        return UserResponse(
            user_id=user_id,
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
    """
    Authenticates a user and returns a JWT access token if credentials are valid.

    Args:
        form_data (OAuth2PasswordRequestForm): Form data that includes 'username' (email) and 'password'.

    Returns:
        TokenResponse: Contains JWT access token, token type, and user information.

    Raises:
        HTTPException: If credentials are invalid or login fails due to internal error.
    """

    firestore_db = firestore.client()
    users_collection = firestore_db.collection("users")

    try:
        # Find user by email in Firestore
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

        # Verify the password
        if not hashed_password or not verify_password(form_data.password, hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

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

@router.post("/token", response_model=TokenResponse)
async def token_login(id_token: str):
    """
    Authenticates a user using a provided token (e.g., from Firebase) and returns an app-specific JWT.

    Args:
        id_token (str): A user identifier or identity token (e.g., from Firebase).

    Returns:
        TokenResponse: Contains a JWT access token, token type, and user information.

    Raises:
        HTTPException: If the token is invalid or the user is not found.
    """
    firestore_db = firestore.client()
    try:
        user_id = id_token  # Insecure assumption - replace with actual verification
        # Fetch user data from Firestore
        user_doc = firestore_db.collection("users").document(user_id).get()
        if not user_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        user_data = user_doc.to_dict()

        # Create your app's access token
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token or user not found: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    
@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user_id: str = Depends(get_current_user)):
    """
    Retrieves the authenticated user's profile information from Firestore.

    Args:
        current_user_id (str): The user ID extracted from the JWT access token via dependency injection.

    Returns:
        UserResponse: A response model containing the user's ID, email, display name, and account creation timestamp.

    Raises:
        HTTPException: 404 if the user is not found in Firestore.
        HTTPException: 500 if any unexpected error occurs while fetching user data.
    """
    firestore_db = firestore.client()

    try:
        # Fetch user data from Firestore using the user ID
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