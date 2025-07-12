# app/core/security.py - Fixed JWT Authentication

from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from firebase_admin import auth
from app.core.config import get_settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate password hash"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    settings = get_settings()
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt

def verify_token(token: str):
    """Verify JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        settings = get_settings()
        
        # Debug logging
        print(f"🔍 DEBUG - Verifying token: {token[:50]}...")
        print(f"🔍 DEBUG - SECRET_KEY exists: {'Yes' if settings.SECRET_KEY else 'No'}")
        print(f"🔍 DEBUG - SECRET_KEY value: {settings.SECRET_KEY[:10]}..." if settings.SECRET_KEY else "None")
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        
        print(f"🔍 DEBUG - Decoded payload: {payload}")
        print(f"🔍 DEBUG - User ID from token: {user_id}")
        
        if user_id is None:
            print("❌ DEBUG - No user_id found in token payload")
            raise credentials_exception
            
        return user_id
    except JWTError as e:
        print(f"❌ DEBUG - JWT Error: {str(e)}")
        raise credentials_exception
    except Exception as e:
        print(f"❌ DEBUG - General Error: {str(e)}")
        raise credentials_exception

def verify_firebase_token(id_token: str):
    """Verify Firebase ID token"""
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token['uid']
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Firebase token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user from JWT token"""
    print(f"🔍 DEBUG - get_current_user called")
    print(f"🔍 DEBUG - Credentials received: {credentials}")
    
    if not credentials:
        print("❌ DEBUG - No credentials received")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No credentials provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not credentials.scheme == "Bearer":
        print(f"❌ DEBUG - Invalid scheme: {credentials.scheme}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    print(f"🔍 DEBUG - Extracted token: {token[:50]}..." if token else "None")
    
    if not token:
        print("❌ DEBUG - Empty token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = verify_token(token)
    print(f"✅ DEBUG - Token verified, user_id: {user_id}")
    return user_id

# Optional: For development/testing without auth
async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """Get current user from JWT token (optional for testing)"""
    if credentials is None:
        return "test_user"  # Default user for testing
    
    token = credentials.credentials
    user_id = verify_token(token)
    return user_id

# 🔥 CRITICAL: Debug function to test token verification
def debug_token_verification(token_string: str):
    """Debug function to manually test token verification"""
    try:
        settings = get_settings()
        
        print(f"🔍 DEBUG MANUAL TEST:")
        print(f"  Token: {token_string[:50]}...")
        print(f"  SECRET_KEY: {settings.SECRET_KEY[:10]}..." if settings.SECRET_KEY else "None")
        print(f"  Algorithm: HS256")
        
        # Try to decode
        payload = jwt.decode(token_string, settings.SECRET_KEY, algorithms=["HS256"])
        print(f"  ✅ Payload: {payload}")
        
        # Check expiration
        exp = payload.get("exp")
        if exp:
            exp_datetime = datetime.fromtimestamp(exp)
            now = datetime.utcnow()
            print(f"  Expires at: {exp_datetime}")
            print(f"  Current time: {now}")
            print(f"  Is expired: {now > exp_datetime}")
        
        user_id = payload.get("sub")
        print(f"  User ID: {user_id}")
        
        return {
            "valid": True,
            "payload": payload,
            "user_id": user_id
        }
        
    except Exception as e:
        print(f"  ❌ Error: {str(e)}")
        return {
            "valid": False,
            "error": str(e)
        }