import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Base Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    PROJECT_ROOT: Path = BASE_DIR.parent
    DOCS_DIR: Path = PROJECT_ROOT / "docs" / "sil"
    
    # API Settings
    PROJECT_NAME: str = "FAI Chatbot API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # LLM Settings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RERANKER_THRESHOLD: float = 0.0
    
    # Provider Settings
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"
    
    # External Services
    DATABASE_URL: Optional[str] = None
    LIGHTRAG_API_URL: str = "http://localhost:9621"
    # Default RAG engine to use when multiple are available: 'LightRAG' or 'Supabase'
    DEFAULT_RAG_ENGINE: str = "LightRAG"

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        extra="ignore"
    )

settings = Settings()
