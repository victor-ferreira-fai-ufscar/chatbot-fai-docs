from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.core.config import settings
from app.schemas.history_schema import Conversation, ConversationCreate, ConversationRename, Message
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

@router.patch("/{conversation_id}")
async def rename_conversation(
    conversation_id: int,
    payload: ConversationRename,
    user_id: str = "guest",
    repo = Depends(get_repo),
):
    """Renomeia o título de uma conversa (escopo pelo user_id: só o dono renomeia)."""
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="O título não pode ser vazio.")
    title = title[:200]  # teto defensivo (o título vira label na sidebar)
    try:
        ok = repo.update_title(conversation_id, title, user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return {"status": "success", "id": conversation_id, "title": title}

@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: int, user_id: str = "guest", repo = Depends(get_repo)):
    """Exclui uma conversa e todas as suas mensagens."""
    try:
        repo.delete_conversation(conversation_id, user_id)
        return {"status": "success", "message": "Conversation deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
