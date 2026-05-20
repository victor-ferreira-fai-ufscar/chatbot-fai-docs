from fastapi import FastAPI
import requests
import sys
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.router import api_router

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

# CORS Configuration
# Em produção, substitua "*" pelos domínios específicos do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
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
