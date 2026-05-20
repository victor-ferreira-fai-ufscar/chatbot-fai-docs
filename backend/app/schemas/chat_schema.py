from pydantic import BaseModel, Field
from typing import List, Optional, Any

class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str
    sources: Optional[List[str]] = None
    gen_time: Optional[float] = None
    usage: Optional[int] = None

class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[int] = None
    rag_engine: str = Field("LightRAG (Grafo)", pattern=r"^(LightRAG \(Grafo\)|Supabase \(Padrão\))$")
    mode: str = "hybrid" # Specifical for LightRAG
    provider: str = "OpenAI API"
    model: str = "gpt-4o-mini"
    top_k: int = 4
    reranker_threshold: float = 0.0

class ChatResponse(BaseModel):
    answer: str
    conversation_id: int
    sources: List[str] = []
    gen_time: float
    usage: int
