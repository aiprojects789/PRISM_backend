from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
import re
from collections import defaultdict
from openai import OpenAI

from app.core.security import get_current_user
from app.core.firebase import get_firestore_client
from app.core.config import get_settings

router = APIRouter()

# Pydantic models
class QuestionGenerationRequest(BaseModel):
    section: str  # 'General Profile', 'Recommendation Profile', 'Simulation Preferences'
    category: Optional[str] = None  # For recommendation profiles

class ProfileUploadRequest(BaseModel):
    profile_data: Dict[str, Any]
    filename: str

# Question Generation Logic (from generate_question.py)
def extract_json_array(s: str) -> str:
    """Extracts the first JSON array from a string."""
    pattern = r'\[\s*(?:\{.*?\}\s*,?\s*)+\]'
    match = re.search(pattern, s, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON array found in LLM response")
    return match.group(0)

def get_concept_paths(data: dict, parent_key: str = '', sep: str = '.') -> List[str]:
    """Recursively finds all dotted paths in a nested dictionary."""
    paths: List[str] = []
    for key, value in data.items():
        new_key = f"{parent_key}{sep}{key}" if parent_key else key
        if isinstance(value, dict):
            if 'description' in value or 'values' in value or 'value' in value:
                paths.append(new_key)
            else:
                for child_key, child_val in value.items():
                    if isinstance(child_val, dict):
                        paths.extend(get_concept_paths({child_key: child_val}, new_key, sep))
    return paths

def get_description_for_path(root: dict, dotted_path: str) -> str:
    """Given a dotted path, navigates through the nested dictionary and returns the 'description' field."""
    parts = dotted_path.split('.') if dotted_path else []
    node = root
    for key in parts:
        node = node.get(key, {}) if isinstance(node, dict) else {}
    return node.get('description', '') if isinstance(node, dict) else ''

def generate_single_question(field_path: str, intent_desc: str, openai_key: str) -> str:
    """Uses the field path and its description to generate a conversational, open-ended question."""
    prompt = f"""You are a friendly AI assistant helping users build their personalized digital twin for better recommendations. Your tone should be warm, encouraging, and respectful.

You will be given a field from a JSON schema and a description explaining its intent.

Generate a conversational, open-ended question that:
- Feels like part of a friendly dialogue
- Offers light guidance or an example to help the user answer
- Is inclusive and privacy-aware (especially if the topic is sensitive)
- Does NOT include multiple-choice options or lists
- Sounds like something a thoughtful assistant would naturally ask

Use the field name and description to craft the question.

Field Name: {field_path}  
Description: {intent_desc}

Generate a conversational question:"""
    
    client = OpenAI(api_key=openai_key)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a friendly AI assistant creating conversational interview questions."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=150
    )
    
    return response.choices[0].message.content.strip()

def rank_and_tier_with_gpt4o(questions: List[Dict[str, Any]], openai_key: str) -> List[Dict[str, Any]]:
    """Uses GPT-4o to rank a list of question dictionaries by their impact."""
    prompt = f"""Here is a JSON array of questions. 

Respond with ONLY a JSON array of the same objects, each with added:
- impactScore: integer 0–100 (based on how much this question impacts personalization)
- tier: "Tier 1", "Tier 2", or "Tier 3" (Tier 1 = highest impact, most essential)

Sort by descending impactScore and distribute evenly across tiers.

```json
{json.dumps(questions, indent=2)}
```"""
    
    client = OpenAI(api_key=openai_key)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an expert in personalization and recommendation logic. Score each question 0–100 on impact, rank, and bucket into three equal tiers."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=2000
    )
    
    try:
        json_text = extract_json_array(response.choices[0].message.content)
        return json.loads(json_text)
    except Exception as e:
        print(f"Error parsing ranked questions: {e}")
        # Return original questions with default scoring
        for i, q in enumerate(questions):
            q['impactScore'] = 100 - (i * 10)  # Simple descending score
            q['tier'] = f"Tier {(i // (len(questions) // 3)) + 1}" if len(questions) > 0 else "Tier 1"
        return questions

def enrich_questions(flat_questions: List[Dict[str, Any]], schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Enriches flat question data by extracting section/subsection and adding descriptions from schema."""
    enriched: List[Dict[str, Any]] = []
    for q in flat_questions:
        full = q['field']
        section, *rest = full.split('.', 1)
        subsection = rest[0] if rest else ''
        description = get_description_for_path(schema.get(section, {}), subsection)
        enriched.append({
            **q, 
            'section': section, 
            'subsection': subsection, 
            'description': description, 
            'qest': 'pending'
        })
    return enriched

def wrap_questions_by_tier(flat_questions: List[Dict[str, Any]], status: str = 'in_process') -> Dict[str, Any]:
    """Groups a flat list of enriched questions into tiers based on the 'tier' key."""
    grouped = defaultdict(list)
    for q in flat_questions:
        grouped[q['tier']].append(q)
    return {
        'tier1': {'status': status, 'questions': grouped.get('Tier 1', [])},
        'tier2': {'status': status, 'questions': grouped.get('Tier 2', [])},
        'tier3': {'status': status, 'questions': grouped.get('Tier 3', [])},
    }

# FastAPI endpoints
@router.post("/upload-profile")
async def upload_profile(
    request: ProfileUploadRequest,
    current_user: str = Depends(get_current_user)
):
    """Upload profile JSON and save to Firestore"""
    try:
        db = get_firestore_client()
        
        # Check if document already exists
        doc_ref = db.collection('user_collection').document(request.filename)
        if doc_ref.get().exists:
            return {
                "success": True,
                "message": f"Profile '{request.filename}' already exists. Skipped upload.",
                "filename": request.filename,
                "exists": True
            }
        
        # Upload the profile data
        doc_ref.set(request.profile_data)
        
        return {
            "success": True,
            "message": f"Uploaded profile as '{request.filename}'",
            "filename": request.filename,
            "exists": False
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload profile: {str(e)}")

@router.post("/upload-profile-file")
async def upload_profile_file(
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user)
):
    """Upload profile JSON file and save to Firestore"""
    try:
        if not file.filename.endswith('.json'):
            raise HTTPException(status_code=400, detail="Only JSON files are allowed")
        
        # Read and parse the JSON file
        content = await file.read()
        json_data = json.loads(content)
        
        db = get_firestore_client()
        doc_id = file.filename
        
        # Check if document already exists
        doc_ref = db.collection('user_collection').document(doc_id)
        if doc_ref.get().exists:
            return {
                "success": True,
                "message": f"Profile '{doc_id}' already exists. Skipped upload.",
                "filename": doc_id,
                "exists": True
            }
        
        # Upload the profile data
        doc_ref.set(json_data)
        
        return {
            "success": True,
            "message": f"Uploaded profile as '{doc_id}'",
            "filename": doc_id,
            "exists": False
        }
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload profile file: {str(e)}")

@router.post("/generate")
async def generate_questions(
    request: QuestionGenerationRequest,
    current_user: str = Depends(get_current_user)
):
    """Generate tiered questions for a specific section"""
    try:
        settings = get_settings()
        db = get_firestore_client()
        
        # Get the uploaded profile data
        profile_doc = db.collection('user_collection').document('profile_strcuture.json').get()
        if not profile_doc.exists:
            raise HTTPException(
                status_code=404, 
                detail="No profile structure found. Please upload a profile first."
            )
        
        json_data = profile_doc.to_dict()
        
        # Generate questions based on section
        sect_key = request.section.lower().replace(' ', '')
        flat: List[Dict[str, Any]] = []
        
        if sect_key == 'generalprofile':
            for p in get_concept_paths(json_data.get('generalprofile', {})):
                path = f"generalprofile.{p}"
                question = generate_single_question(
                    path, 
                    get_description_for_path(json_data['generalprofile'], p),
                    settings.OPENAI_API_KEY
                )
                flat.append({'field': path, 'question': question})
                
        elif sect_key == 'recommendationprofile' and request.category:
            category_data = json_data.get('recommendationProfiles', {}).get(request.category, {})
            for p in get_concept_paths(category_data):
                path = f"recommendationProfiles.{request.category}.{p}"
                question = generate_single_question(
                    path, 
                    get_description_for_path(category_data, p),
                    settings.OPENAI_API_KEY
                )
                flat.append({'field': path, 'question': question})
                
        elif sect_key == 'simulationpreferences':
            for p in get_concept_paths(json_data.get('simulationPreferences', {})):
                path = f"simulationPreferences.{p}"
                question = generate_single_question(
                    path, 
                    '',
                    settings.OPENAI_API_KEY
                )
                flat.append({'field': path, 'question': question})
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid section: {request.section}"
            )
        
        if not flat:
            raise HTTPException(
                status_code=404,
                detail=f"No questions could be generated for section: {request.section}"
            )
        
        # Rank and tier questions
        ranked = rank_and_tier_with_gpt4o(flat, settings.OPENAI_API_KEY)
        
        # Enrich questions
        enriched = enrich_questions(ranked, json_data)
        
        # Wrap into tier structure
        wrapped = wrap_questions_by_tier(enriched)
        
        # Generate filename
        file_name = f"{('general' if sect_key=='generalprofile' else request.category if request.category else 'simulation')}_tiered_questions.json"
        
        # Save to Firestore
        db.collection('question_collection').document(file_name).set(wrapped)
        
        return {
            "success": True,
            "message": f"Uploaded questions as '{file_name}'",
            "filename": file_name,
            "questions": wrapped,
            "total_questions": sum(len(tier['questions']) for tier in wrapped.values()),
            "section": request.section,
            "category": request.category
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate questions: {str(e)}")

@router.get("/list-profiles")
async def list_profiles(current_user: str = Depends(get_current_user)):
    """List all available profiles in Firestore"""
    try:
        db = get_firestore_client()
        docs = []
        
        collection_ref = db.collection("user_collection")
        for doc in collection_ref.list_documents():
            docs.append(doc.id)
        
        return {
            "success": True,
            "profiles": docs,
            "count": len(docs)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list profiles: {str(e)}")

@router.get("/list-questions")
async def list_question_collections(current_user: str = Depends(get_current_user)):
    """List all question collections in Firestore"""
    try:
        db = get_firestore_client()
        docs = []
        
        collection_ref = db.collection("question_collection")
        for doc in collection_ref.list_documents():
            docs.append(doc.id)
        
        return {
            "success": True,
            "question_collections": docs,
            "count": len(docs)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list question collections: {str(e)}")

@router.delete("/delete-document/{collection}/{document_id}")
async def delete_document(
    collection: str,
    document_id: str,
    current_user: str = Depends(get_current_user)
):
    """Delete a document from Firestore"""
    try:
        if collection not in ["user_collection", "question_collection"]:
            raise HTTPException(status_code=400, detail="Invalid collection name")
        
        db = get_firestore_client()
        db.collection(collection).document(document_id).delete()
        
        return {
            "success": True,
            "message": f"Deleted '{document_id}' from {collection}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

@router.get("/download-document/{collection}/{document_id}")
async def download_document(
    collection: str,
    document_id: str,
    current_user: str = Depends(get_current_user)
):
    """Download a document from Firestore"""
    try:
        if collection not in ["user_collection", "question_collection"]:
            raise HTTPException(status_code=400, detail="Invalid collection name")
        
        db = get_firestore_client()
        doc = db.collection(collection).document(document_id).get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found in '{collection}'")
        
        return {
            "success": True,
            "document_id": document_id,
            "collection": collection,
            "data": doc.to_dict()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download document: {str(e)}")

@router.get("/supported-sections")
async def get_supported_sections():
    """Get list of supported sections for question generation"""
    return {
        "success": True,
        "sections": [
            {
                "id": "generalprofile",
                "name": "General Profile",
                "description": "General user profile questions"
            },
            {
                "id": "recommendationprofile", 
                "name": "Recommendation Profile",
                "description": "Category-specific recommendation questions",
                "requires_category": True
            },
            {
                "id": "simulationpreferences",
                "name": "Simulation Preferences", 
                "description": "User simulation preference questions"
            }
        ],
        "categories": [
            "Movies",
            "Food", 
            "Travel",
            "Books",
            "Music",
            "Fitness"
        ]
    }

@router.get("/validate-profile/{filename}")
async def validate_profile_structure(
    filename: str,
    current_user: str = Depends(get_current_user)
):
    """Validate a profile structure for question generation"""
    try:
        db = get_firestore_client()
        
        # Get the profile document
        doc_ref = db.collection('user_collection').document(filename)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Profile '{filename}' not found")
        
        profile_data = doc.to_dict()
        
        # Validate structure
        validation_results = {
            "valid": True,
            "sections_found": [],
            "total_paths": 0,
            "issues": []
        }
        
        # Check for expected sections
        expected_sections = ['generalprofile', 'recommendationProfiles', 'simulationPreferences']
        
        for section in expected_sections:
            if section in profile_data:
                validation_results["sections_found"].append(section)
                paths = get_concept_paths(profile_data[section])
                validation_results["total_paths"] += len(paths)
                
                if len(paths) == 0:
                    validation_results["issues"].append(f"Section '{section}' has no valid paths for question generation")
            else:
                validation_results["issues"].append(f"Missing section: '{section}'")
        
        if len(validation_results["sections_found"]) == 0:
            validation_results["valid"] = False
            validation_results["issues"].append("No valid sections found for question generation")
        
        return {
            "success": True,
            "filename": filename,
            "validation": validation_results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate profile: {str(e)}")