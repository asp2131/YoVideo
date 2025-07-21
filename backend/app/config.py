import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # API Configuration
    app_name: str = "VideoThingy AI Service"
    version: str = "1.0.0"
    debug: bool = False
    
    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    
    # CORS Configuration
    allowed_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:3002",
        "https://*.vercel.app",
        "https://videothingy.vercel.app",
    ]
    
    # Supabase Configuration
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379"
    
    # File Upload Configuration
    max_upload_size: int = 2 * 1024 * 1024 * 1024  # 2GB
    allowed_file_types: List[str] = [
        "video/mp4",
        "video/avi",
        "video/mov",
        "video/wmv",
        "video/flv",
        "video/webm",
        "video/mkv"
    ]
    
    # Processing Configuration
    whisper_model: str = "base"  # Options: tiny, base, small, medium, large
    max_processing_time: int = 1800  # 30 minutes in seconds
    
    # Environment
    environment: str = "production"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()
