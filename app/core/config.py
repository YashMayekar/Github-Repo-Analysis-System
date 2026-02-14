import secrets
from typing import List, Union
from pydantic import AnyHttpUrl, EmailStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "GitHub Commit Collector"
    
    # GitHub Config
    GITHUB_TOKEN: str
    GITHUB_API_URL: str = "https://api.github.com"
    GITHUB_API_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    RATE_LIMIT_BUFFER: int = 10
    
    # AI Config
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    AI_MODEL_NAME: str = "mistral"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database
    DATABASE_URL: str = "sqlite:///./commit_collector.db"

    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
