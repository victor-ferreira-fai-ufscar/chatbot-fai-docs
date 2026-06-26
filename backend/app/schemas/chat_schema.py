from pydantic import BaseModel, Field
from typing import List, Optional, Any

class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    sources: Optional[List[str]] = None
    gen_time: Optional[float] = None
    usage: Optional[int] = None

class QuotedMessage(BaseModel):
    """Mensagem anterior citada/mencionada pelo usuario (estilo "responder" do WhatsApp)."""
    role: str = Field("assistant", pattern="^(user|assistant)$")
    content: str

class ChatRequest(BaseModel):
    question: str
    quoted: Optional[QuotedMessage] = None
    conversation_id: Optional[int] = None
    user_id: str = "guest"
    rag_engine: str = Field("LightRAG (Grafo)", pattern=r"^(LightRAG \(Grafo\)|Supabase \(Padrão\))$")
    mode: str = "mix" # Specifical for LightRAG: "mix" une grafo + vetorial (recupera o trecho exato)
    provider: str = "OpenAI API"
    model: str = "gpt-4o-mini"
    top_k: int = 4
    reranker_threshold: float = 0.0
    # Override por-requisicao do "Modo Agentico" (tool calling + Skills). None = usa o
    # default do servidor (AGENT_ENABLED). Permite a UI desligar o agente (ex.: testar
    # alucinacao). Desligado NAO gera planilha/PDF/DOCX (skills).
    agentic: Optional[bool] = None

class ChatResponse(BaseModel):
    answer: str
    conversation_id: int
    sources: List[str] = []
    gen_time: float
    usage: int
