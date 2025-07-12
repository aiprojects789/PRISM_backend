# app/core/config.py
from pydantic_settings import BaseSettings
from typing import Optional, List, Union
import os

class Settings(BaseSettings):
    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Prism API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Digital Twin Interview and Recommendation System"
    
    # OpenAI API Key
    OPENAI_API_KEY: str
    
    # JWT Configuration  
    SECRET_KEY: str = "your-secret-key-here"  # Change in production
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days
    
    # Firebase Configuration
    FIREBASE_CONFIG__type: str = "service_account"
    FIREBASE_CONFIG__project_id: str
    FIREBASE_CONFIG__private_key_id: str
    FIREBASE_CONFIG__private_key: str
    FIREBASE_CONFIG__client_email: str
    FIREBASE_CONFIG__client_id: str
    FIREBASE_CONFIG__auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    FIREBASE_CONFIG__token_uri: str = "https://oauth2.googleapis.com/token"
    FIREBASE_CONFIG__auth_provider_x509_cert_url: str = "https://www.googleapis.com/oauth2/v1/certs"
    FIREBASE_CONFIG__client_x509_cert_url: str
    
    # CORS Settings - Fixed to handle string input properly
    BACKEND_CORS_ORIGINS: Union[str, List[str]] = ["*"]
    
    # Interview Settings
    MAX_ACTIVE_SESSIONS: int = 1000
    SESSION_TIMEOUT_MINUTES: int = 60
    
    # Recommendation Settings
    MAX_SEARCH_RESULTS: int = 3
    SEARCH_RETRY_ATTEMPTS: int = 3
    
    # Application Settings
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    @property
    def firebase_credentials(self) -> dict:
        """Get Firebase credentials as a dictionary"""
        return {
            "type": self.FIREBASE_CONFIG__type,
            "project_id": self.FIREBASE_CONFIG__project_id,
            "private_key_id": self.FIREBASE_CONFIG__private_key_id,
            "private_key": self.FIREBASE_CONFIG__private_key.replace("\\n", "\n"),
            "client_email": self.FIREBASE_CONFIG__client_email,
            "client_id": self.FIREBASE_CONFIG__client_id,
            "auth_uri": self.FIREBASE_CONFIG__auth_uri,
            "token_uri": self.FIREBASE_CONFIG__token_uri,
            "auth_provider_x509_cert_url": self.FIREBASE_CONFIG__auth_provider_x509_cert_url,
            "client_x509_cert_url": self.FIREBASE_CONFIG__client_x509_cert_url
        }
    
    @property
    def cors_origins(self) -> List[str]:
        """Get CORS origins as a list"""
        if isinstance(self.BACKEND_CORS_ORIGINS, str):
            # If it's a string, split by comma and strip whitespace
            if self.BACKEND_CORS_ORIGINS == "*":
                return ["*"]
            return [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",")]
        return self.BACKEND_CORS_ORIGINS
    
    class Config:
        case_sensitive = True
        env_file = ".env"
        # Allow parsing of comma-separated strings
        env_parse_none_str = None

# Global settings instance
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Get settings instance (singleton pattern)"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings