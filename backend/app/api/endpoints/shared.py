"""Rota PÚBLICA de visualização de conversa compartilhada (read-only, sem auth).

Quem tiver o link (`/shared/{token}`) consegue ver a conversa. O token é gerado por
`POST /history/{id}/share` (só o dono gera) e é imprevisível (secrets.token_urlsafe).
Aqui NÃO há user scoping — é o modelo "compartilhar por link". Somente leitura: este
router não expõe nenhuma escrita.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.core.config import settings
from app.schemas.history_schema import Message
from src.chatbot_fai_docs.repository import get_repo_from_url

router = APIRouter()


def get_repo():
    repo = get_repo_from_url(settings.DATABASE_URL)
    try:
        repo.ensure_ready()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")
    return repo


@router.get("/{token}")
async def get_shared_conversation(token: str, repo = Depends(get_repo)):
    """Devolve título + mensagens da conversa apontada pelo token. 404 se o token não existe."""
    result = repo.get_shared(token)
    if result is None:
        raise HTTPException(status_code=404, detail="Link inválido ou conversa indisponível.")
    conv, messages = result
    return {
        "title": conv.title,
        "created_at": conv.created_at,
        "messages": [Message.model_validate(m) for m in messages],
    }
