from datetime import datetime
from google.cloud.firestore_v1 import DocumentSnapshot
from google.protobuf.timestamp_pb2 import Timestamp

def convert_firestore_timestamp_to_iso(timestamp):
    """Convert Firestore timestamp to ISO format string"""
    if hasattr(timestamp, 'isoformat'):
        return timestamp.isoformat()
    elif isinstance(timestamp, Timestamp):
        return datetime.fromtimestamp(timestamp.seconds).isoformat()
    return timestamp

def clean_session_data(session_data: dict) -> dict:
    """Convert Firestore-specific types to JSON-serializable formats"""
    cleaned = {}
    for key, value in session_data.items():
        if hasattr(value, 'isoformat'):  # Handle datetime objects
            cleaned[key] = value.isoformat()
        elif isinstance(value, dict):
            cleaned[key] = clean_session_data(value)
        elif isinstance(value, list):
            cleaned[key] = [clean_session_data(item) if isinstance(item, dict) else convert_firestore_timestamp_to_iso(item) for item in value]
        else:
            cleaned[key] = value
    return cleaned
