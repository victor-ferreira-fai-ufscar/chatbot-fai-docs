from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.core.config import settings
from app.schemas.history_schema import Conversation, ConversationCreate, Message
from src.chatbot_fai_docs.repository import get_repo_from_url
from typing import Optional

router = APIRouter()

def get_repo():
    # If DEFAULT_RAG_ENGINE is LightRAG, prefer in-memory repo for history persistence
    if getattr(settings, "DEFAULT_RAG_ENGINE", "") == "LightRAG":
        repo = get_repo_from_url(None)
    else:
        repo = get_repo_from_url(settings.DATABASE_URL)
    # ensure_ready is a no-op for in-memory repo
    try:
        repo.ensure_ready()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")
    return repo

@router.get("/", response_model=List[Conversation])
async def list_conversations(user_id: str = "guest", repo = Depends(get_repo)):
    """Lista todas as conversas de um usuário."""
    try:
        return repo.list_conversations(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{conversation_id}/messages", response_model=List[Message])
async def get_messages(conversation_id: int, repo = Depends(get_repo)):
    """Recupera todas as mensagens de uma conversa específica."""
    try:
        return repo.get_messages(conversation_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: int, repo = Depends(get_repo)):
    """Exclui uma conversa e todas as suas mensagens."""
    try:
        repo.delete_conversation(conversation_id)
        return {"status": "success", "message": "Conversation deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
