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
    # Gate conversacional: quando True, mensagens puramente sociais (saudacao,
    # agradecimento, despedida, pergunta sobre quem e a Lina) respondem direto pelo
    # modelo auxiliar, SEM acionar a busca no LightRAG (economiza ~13s nesses turnos).
    # Conservador por design: na duvida, cai no LightRAG. Desligue com env=false.
    SMALLTALK_GATE_ENABLED: bool = True

    # Agente (Fase 8: tool calling + Skills). Desligado por padrao -> rollback
    # instantaneo para o fluxo RAG fixo atual. Skills ficam em backend/skills/*/SKILL.md
    # (uma pasta por skill com SKILL.md + handler). Ver docs/plano-agente-tool-calling.md.
    AGENT_ENABLED: bool = False
    MAX_TOOL_STEPS: int = 5            # teto de iteracoes do laco (guarda anti-loop)
    TOOL_TIMEOUT_S: int = 60           # timeout por execucao de skill
    SKILLS_DIR: Path = BASE_DIR / "skills"
    SKILL_INSTRUCTIONS_MODE: str = "preamble"   # preamble | on_demand (disclosure)

    # Transcricao de Audio (Fase 4: Speech-to-Text via Whisper local)
    # WHISPER_DEVICE: 'auto' (cuda se disponivel, senao cpu) | 'cuda' | 'cpu'
    WHISPER_ENABLED: bool = True
    WHISPER_MODEL: str = "medium"
    WHISPER_DEVICE: str = "auto"
    WHISPER_LANGUAGE: str = "pt"

    # Supabase Storage (Fase 6: repositorio de documentos e entrega ao usuario)
    SUPABASE_URL: Optional[str] = None
    SERVICE_ROLE_KEY: Optional[str] = None
    ANON_KEY: Optional[str] = None
    SUPABASE_BUCKET: str = "manuais"
    SIGNED_URL_TTL: int = 3600
    # Bucket SEPARADO para documentos GERADOS pelo agente (planilhas/PDF/DOCX).
    # Mantem o bucket de manuais limpo; estes arquivos sao TEMPORARIOS e removidos
    # automaticamente apos TEMP_DOC_TTL_DAYS (varredura a cada TEMP_DOC_SWEEP_HOURS).
    SUPABASE_TEMP_BUCKET: str = "gerados"
    TEMP_DOC_CLEANUP_ENABLED: bool = True
    TEMP_DOC_TTL_DAYS: int = 3
    TEMP_DOC_SWEEP_HOURS: int = 6

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
