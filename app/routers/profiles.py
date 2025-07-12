from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from app.core.security import get_current_user
from app.core.firebase import get_firestore_client
from app.core.config import get_settings

router = APIRouter()

# Pydantic models for profile management
class ProfileCreateRequest(BaseModel):
    profile_name: str
    profile_data: Dict[str, Any]
    description: Optional[str] = None

class ProfileUpdateRequest(BaseModel):
    profile_data: Dict[str, Any]
    description: Optional[str] = None

class ProfileResponse(BaseModel):
    profile_id: str
    profile_name: str
    description: Optional[str]
    profile_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    user_id: str

class ProfileListResponse(BaseModel):
    profiles: List[Dict[str, Any]]
    total_count: int
    user_id: str

@router.post("/create", response_model=ProfileResponse)
async def create_user_profile(
    request: ProfileCreateRequest,
    current_user: str = Depends(get_current_user)
):
    """Create a new profile for the current user"""
    try:
        db = get_firestore_client()
        profile_id = str(uuid.uuid4())
        
        # Create profile document
        profile_doc = {
            "profile_id": profile_id,
            "profile_name": request.profile_name,
            "description": request.description,
            "profile_data": request.profile_data,
            "user_id": current_user,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "version": 1
        }
        
        # Save to user-specific collection
        db.collection("user_profiles").document(current_user).collection("profiles").document(profile_id).set(profile_doc)
        
        # Also save to the main profile structure for interview use
        db.collection("user_collection").document(f"{current_user}_profile_structure.json").set(request.profile_data)
        
        return ProfileResponse(
            profile_id=profile_id,
            profile_name=request.profile_name,
            description=request.description,
            profile_data=request.profile_data,
            created_at=profile_doc["created_at"],
            updated_at=profile_doc["updated_at"],
            user_id=current_user
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create profile: {str(e)}")

@router.get("/list", response_model=ProfileListResponse)
async def list_user_profiles(current_user: str = Depends(get_current_user)):
    """Get all profiles for the current user"""
    try:
        db = get_firestore_client()
        
        # Get all profiles for the user
        profiles_ref = db.collection("user_profiles").document(current_user).collection("profiles")
        profiles = profiles_ref.where("is_active", "==", True).order_by("created_at", direction="DESCENDING").stream()
        
        profile_list = []
        for profile in profiles:
            profile_data = profile.to_dict()
            profile_list.append({
                "profile_id": profile_data["profile_id"],
                "profile_name": profile_data["profile_name"],
                "description": profile_data.get("description"),
                "created_at": profile_data["created_at"],
                "updated_at": profile_data["updated_at"],
                "version": profile_data.get("version", 1),
                "data_fields_count": len(profile_data.get("profile_data", {}))
            })
        
        return ProfileListResponse(
            profiles=profile_list,
            total_count=len(profile_list),
            user_id=current_user
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list profiles: {str(e)}")

@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_user_profile(
    profile_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get a specific profile by ID"""
    try:
        db = get_firestore_client()
        
        # Get the specific profile
        profile_doc = db.collection("user_profiles").document(current_user).collection("profiles").document(profile_id).get()
        
        if not profile_doc.exists:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        profile_data = profile_doc.to_dict()
        
        return ProfileResponse(
            profile_id=profile_data["profile_id"],
            profile_name=profile_data["profile_name"],
            description=profile_data.get("description"),
            profile_data=profile_data["profile_data"],
            created_at=profile_data["created_at"],
            updated_at=profile_data["updated_at"],
            user_id=profile_data["user_id"]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get profile: {str(e)}")

@router.post("/{profile_id}/activate")
async def activate_profile(
    profile_id: str,
    current_user: str = Depends(get_current_user)
):
    """Set a profile as the active profile for interviews"""
    try:
        db = get_firestore_client()
        
        # Get the profile
        profile_doc = db.collection("user_profiles").document(current_user).collection("profiles").document(profile_id).get()
        
        if not profile_doc.exists:
            raise HTTPException(status_code=404, detail="Profile not found")
        
        profile_data = profile_doc.to_dict()
        
        # Set this profile as the active profile structure
        db.collection("user_collection").document(f"{current_user}_profile_structure.json").set(profile_data["profile_data"])
        
        # Update profile to mark as active
        db.collection("user_profiles").document(current_user).collection("profiles").document(profile_id).update({
            "last_activated": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": f"Profile {profile_data['profile_name']} activated successfully",
            "profile_id": profile_id,
            "profile_name": profile_data["profile_name"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to activate profile: {str(e)}")