import re
import unicodedata
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Response
from typing import List
from app.core.config import settings
from app.schemas.history_schema import Conversation, ConversationCreate, ConversationRename, Message
from src.chatbot_fai_docs.repository import get_repo_from_url
from typing import Optional

router = APIRouter()


def _pdf_slug(title: str, conversation_id: int) -> str:
    """Nome de arquivo ASCII seguro p/ o Content-Disposition (sem acento/espaço)."""
    base = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower()
    base = base[:60].strip("-")
    return f"conversa-{base}" if base else f"conversa-{conversation_id}"

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

@router.post("/{conversation_id}/share")
async def share_conversation(
    conversation_id: int,
    user_id: str = "guest",
    repo = Depends(get_repo),
):
    """Gera (ou reusa) o link de compartilhamento read-only de uma conversa. Escopo pelo
    user_id: só o dono compartilha. Devolve o token e o caminho relativo da view pública
    (o frontend prefixa com a origem para montar o link completo)."""
    try:
        token = repo.create_share_token(conversation_id, user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not token:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    return {"status": "success", "id": conversation_id, "token": token, "path": f"/shared/{token}"}

@router.get("/{conversation_id}/export.pdf")
async def export_conversation_pdf(
    conversation_id: int,
    user_id: str = "guest",
    download: bool = False,
    repo = Depends(get_repo),
):
    """Exporta a conversa como PDF branded (FAI). Escopo pelo user_id (só o dono).
    download=true força attachment; senão inline (abre no visualizador p/ imprimir)."""
    try:
        conv = next((c for c in repo.list_conversations(user_id) if c.id == conversation_id), None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")

    messages = repo.get_messages(conversation_id, user_id)
    if not messages:
        raise HTTPException(status_code=404, detail="Conversa sem mensagens para exportar.")

    # Teto defensivo: WeasyPrint é CPU/memória-intensivo. Conversa gigante -> erro claro
    # em vez de segurar o servidor (o offload abaixo evita travar o event loop, mas o
    # teto limita o pior caso de tamanho).
    total_chars = sum(len(getattr(m, "content", "") or "") for m in messages)
    if len(messages) > 1000 or total_chars > 800_000:
        raise HTTPException(status_code=413, detail="Conversa muito longa para exportar em PDF.")

    from src.chatbot_fai_docs.conversation_pdf import build_conversation_pdf
    from starlette.concurrency import run_in_threadpool
    try:
        # Offload para thread: write_pdf() é síncrono e bloquearia o event loop async
        # (nenhuma outra requisição seria atendida durante a renderização).
        pdf_bytes = await run_in_threadpool(
            build_conversation_pdf,
            conv.title, messages, conversation_id=conversation_id, exported_at=datetime.now(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar o PDF: {e}")

    slug = _pdf_slug(conv.title, conversation_id)
    disposition = "attachment" if download else "inline"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'{disposition}; filename="{slug}.pdf"'},
    )


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: int, user_id: str = "guest", repo = Depends(get_repo)):
    """Exclui uma conversa e todas as suas mensagens."""
    try:
        repo.delete_conversation(conversation_id, user_id)
        return {"status": "success", "message": "Conversation deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
