from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.core.config import settings
from app.schemas.history_schema import Conversation, ConversationCreate, Message
from src.chatbot_fai_docs.repository import get_repo_from_url
from typing import Optional

router = APIRouter()

def get_repo():
    # Persistencia do historico independe do motor RAG: usa Postgres se DATABASE_URL
    # estiver configurado, senao cai no repo em memoria (fallback de desenvolvimento).
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

@router.delete("/")
async def clear_conversations(user_id: str = "guest", repo = Depends(get_repo)):
    """Exclui todas as conversas (e mensagens) de um usuário."""
    try:
        repo.clear_conversations(user_id)
        return {"status": "success", "message": "History cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{conversation_id}/messages", response_model=List[Message])
async def get_messages(conversation_id: int, user_id: str = "guest", repo = Depends(get_repo)):
    """Recupera todas as mensagens de uma conversa específica."""
    try:
        return repo.get_messages(conversation_id, user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: int, user_id: str = "guest", repo = Depends(get_repo)):
    """Exclui uma conversa e todas as suas mensagens."""
    try:
        repo.delete_conversation(conversation_id, user_id)
        return {"status": "success", "message": "Conversation deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
