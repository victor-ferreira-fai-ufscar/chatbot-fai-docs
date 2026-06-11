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
    # Modelo do Ollama usado em tarefas auxiliares (titulo de conversa,
    # resolucao de documentos) quando nao ha OPENAI_API_KEY configurada.
    OLLAMA_MODEL: str = "llama3.2:3b"
    
    # External Services
    DATABASE_URL: Optional[str] = None
    LIGHTRAG_API_URL: str = "http://localhost:9621"
    # Lista de candidatos (separados por virgula); o backend usa o primeiro acessivel.
    LIGHTRAG_API_URLS: Optional[str] = None
    # API key do servidor LightRAG (header X-API-Key), usada quando ele exige autenticacao
    LIGHTRAG_API_KEY: Optional[str] = None
    # Default RAG engine to use when multiple are available: 'LightRAG' or 'Supabase'
    DEFAULT_RAG_ENGINE: str = "LightRAG"
    # Numero de turnos (pares user/assistant) do historico enviados ao LightRAG como contexto
    HISTORY_TURNS: int = 5

    # Supabase Storage (Fase 6: repositorio de documentos e entrega ao usuario)
    SUPABASE_URL: Optional[str] = None
    SERVICE_ROLE_KEY: Optional[str] = None
    ANON_KEY: Optional[str] = None
    SUPABASE_BUCKET: str = "manuais"
    SIGNED_URL_TTL: int = 3600

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        extra="ignore"
    )

    def lightrag_candidates(self) -> list[str]:
        """Lista de URLs candidatas do LightRAG, normalizadas (sem barra final)."""
        raw = self.LIGHTRAG_API_URLS or self.LIGHTRAG_API_URL or ""
        urls = [u.strip().rstrip("/") for u in raw.split(",") if u.strip()]
        return urls or [self.LIGHTRAG_API_URL.rstrip("/")]

settings = Settings()
