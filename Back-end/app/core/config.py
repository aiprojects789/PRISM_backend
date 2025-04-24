import os
# from pydantic import BaseSettings
from pydantic_settings import BaseSettings

from typing import Dict, Any, Optional
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "Prism API"
    OPENAI_API_KEY: str
    FIREBASE_CONFIG: Dict[str, Any]
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    class Config:
        env_file = ".env"
        env_nested_delimiter = "__"

@lru_cache()
def get_settings() -> Settings:
    return Settings()