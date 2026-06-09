from fastapi import FastAPI
import requests
import sys
from urllib.parse import urlsplit
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.router import api_router
from src.chatbot_fai_docs.repository import get_repo_from_url

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
    """Abort startup if LightRAG is configured as default but not reachable."""
    try:
        if getattr(settings, "DEFAULT_RAG_ENGINE", "") == "LightRAG":
            url = settings.LIGHTRAG_API_URL.rstrip("/")
            # Try health endpoints commonly exposed; fall back to root
            candidates = [f"{url}/health", url]
            ok = False
            for u in candidates:
                try:
                    resp = requests.get(u, timeout=3)
                    if resp.status_code < 400:
                        ok = True
                        break
                except Exception:
                    continue
            if not ok:
                print(f"LightRAG not available at {settings.LIGHTRAG_API_URL}; aborting startup")
                raise RuntimeError("LightRAG engine unreachable; server will not start when LightRAG is default")
    except Exception as e:
        # Reraise to stop app startup
        raise


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
