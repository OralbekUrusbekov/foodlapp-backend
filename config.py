from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os

class Settings(BaseSettings):

    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/foodlab_db"
    SECRET_KEY: str

    AUTH_GOOGLE_CLIENT_ID: str
    AUTH_GOOGLE_SECRET_ID: str 

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # QR Code
    QR_CODE_EXPIRE_MINUTES: int = 15

    AWS_ACCESS_KEY_ID:str
    AWS_SECRET_ACCESS_KEY:str
    AWS_S3_BUCKET_NAME:str = "free-cloud"
    AWS_S3_REGION_NAME:str = "us-east-1"
    AWS_S3_ENDPOINT_URL:str = "https://object.pscloud.io"

    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # Mail Settings (Optional)
    MAIL_USERNAME: Optional[str] = None
    MAIL_PASSWORD: Optional[str] = None
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_PORT: int = 587
    
    # AI Settings
    GEMINI_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
