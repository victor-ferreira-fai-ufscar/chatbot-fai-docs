from fastapi import FastAPI
import asyncio
import requests
import sys
from urllib.parse import urlsplit
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.router import api_router
from src.chatbot_fai_docs.repository import get_repo_from_url
from src.chatbot_fai_docs.lightrag_resolver import resolve_lightrag_url
from src.chatbot_fai_docs.storage_service import StorageService
from src.chatbot_fai_docs.temp_cleanup import cleanup_once

# Mantem referencia forte das tasks de background: asyncio.create_task nao a
# guarda, e sem isso o GC pode coletar a task e matar o loop silenciosamente.
_BACKGROUND_TASKS: set = set()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API de Backend para o Chatbot FAI Docs com suporte a RAG (Supabase e LightRAG).",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.on_event("startup")
def check_lightrag_available():
    """Registra o endpoint do LightRAG ativo no startup."""
    if getattr(settings, "DEFAULT_RAG_ENGINE", "") != "LightRAG":
        return

    candidates = settings.lightrag_candidates()
    active = resolve_lightrag_url(candidates)
    print(f"[LightRAG] Endpoint ativo: {active} (candidatos: {candidates})")


@app.on_event("startup")
def log_whisper_config():
    """Loga a config de transcricao de audio. O modelo Whisper e carregado
    sob demanda na primeira requisicao (carga preguicosa) para nao atrasar
    o startup nem ocupar VRAM quando o recurso nao e usado."""
    if not getattr(settings, "WHISPER_ENABLED", False):
        print("[Whisper] Transcricao de audio DESATIVADA (WHISPER_ENABLED=false).")
        return
    print(
        f"[Whisper] Transcricao ATIVA — modelo='{settings.WHISPER_MODEL}', "
        f"device='{settings.WHISPER_DEVICE}', idioma='{settings.WHISPER_LANGUAGE}' "
        f"(carregado sob demanda na 1a transcricao)."
    )


@app.on_event("startup")
def check_database_connection():
    """Loga se a conexao com o banco de historico (Supabase/Postgres) teve sucesso.
    Nao aborta o startup: sem banco, a aplicacao usa o repositorio em memoria como fallback.
    """
    if not settings.DATABASE_URL:
        print("[DB] DATABASE_URL nao configurada -> usando historico EM MEMORIA (nao persistente).")
        return

    # Esconde a senha ao logar o destino da conexao
    try:
        parts = urlsplit(settings.DATABASE_URL)
        target = f"{parts.hostname}:{parts.port or 5432}{parts.path or ''}"
    except Exception:
        target = "(endereco nao identificado)"

    try:
        repo = get_repo_from_url(settings.DATABASE_URL)
        repo.ensure_ready()  # conecta e garante as tabelas chat_conversations/chat_messages
        print(f"[DB] Conexao com Supabase/Postgres OK em {target} (tabelas de historico prontas).")
    except Exception as e:
        print(f"[DB] FALHA ao conectar com Supabase/Postgres em {target}: {e}")
        print("[DB] O historico de conversas NAO sera persistido ate a conexao ser restabelecida.")

@app.on_event("startup")
async def start_temp_bucket_cleanup():
    """Garante o bucket de documentos GERADOS (temporarios) e agenda a varredura
    que remove arquivos com mais de TEMP_DOC_TTL_DAYS dias. Documentos gerados
    pelo agente (planilha/PDF) vivem nesse bucket separado e sao limpos sozinhos.

    Roda como task de background no proprio backend (sem dependencia/infra extra);
    as chamadas de rede (bloqueantes) vao para um thread para nao travar o loop."""
    if not (settings.SUPABASE_URL and settings.SERVICE_ROLE_KEY):
        print("[Limpeza] Storage nao configurado -> bucket temporario/limpeza DESATIVADOS.")
        return
    if not settings.TEMP_DOC_CLEANUP_ENABLED:
        print("[Limpeza] TEMP_DOC_CLEANUP_ENABLED=false -> limpeza DESATIVADA.")
        return

    storage = StorageService(
        base_url=settings.SUPABASE_URL,
        service_key=settings.SERVICE_ROLE_KEY,
        bucket=settings.SUPABASE_TEMP_BUCKET,
    )
    try:
        await asyncio.to_thread(storage.ensure_bucket, False)  # privado
        print(f"[Limpeza] Bucket temporario '{settings.SUPABASE_TEMP_BUCKET}' pronto (privado).")
    except Exception as e:
        print(f"[Limpeza] Falha ao garantir bucket '{settings.SUPABASE_TEMP_BUCKET}': {e}")

    async def _loop():
        interval = max(1, settings.TEMP_DOC_SWEEP_HOURS) * 3600
        while True:
            try:
                summary = await asyncio.to_thread(cleanup_once, storage, settings.TEMP_DOC_TTL_DAYS)
                if summary["deleted"]:
                    print(f"[Limpeza] Removidos {len(summary['deleted'])} arquivo(s) "
                          f">{settings.TEMP_DOC_TTL_DAYS}d de '{settings.SUPABASE_TEMP_BUCKET}': "
                          f"{summary['deleted']}")
                for nome, msg in summary["errors"]:
                    print(f"[Limpeza] Falha ao remover '{nome}': {msg}")
            except Exception as e:
                print(f"[Limpeza] Erro na varredura: {e}")
            await asyncio.sleep(interval)

    task = asyncio.create_task(_loop())
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    print(f"[Limpeza] Varredura agendada a cada {settings.TEMP_DOC_SWEEP_HOURS}h "
          f"(TTL {settings.TEMP_DOC_TTL_DAYS} dias).")


# CORS Configuration
# Em produção, substitua "*" pelos domínios específicos do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "http://200.136.209.163:3000",
        "http://200.136.209.163:3001",
        "http://200.136.209.180:3000",
        "http://200.136.209.180:3001",
        "http://200.136.209.173:3000",
        "http://200.136.209.173:3001",
        "http://192.168.223.150:3000",
        "http://192.168.223.150:3001",
        "http://200.136.209.229:3000",
        "http://200.136.209.229:3001",

    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/", tags=["Health"])
def root():
    return {
        "message": "FAI Chatbot API is running",
        "docs": "/docs",
        "version": settings.VERSION
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
