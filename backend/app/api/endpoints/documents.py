from fastapi import APIRouter, HTTPException
from app.core.config import settings
from src.chatbot_fai_docs import AppConfig, RagService
from pathlib import Path

router = APIRouter()

@router.get("/")
async def list_documents():
    """Lista os nomes de todos os PDFs disponíveis na pasta sil."""
    from backend.src.chatbot_fai_docs.pdfs import list_pdf_files
    try:
        files = list_pdf_files(settings.DOCS_DIR)
        return {"documents": [f.name for f in files]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync")
async def sync_documents(force: bool = False):
    """Sincroniza os arquivos locais com o banco vetorial."""
    try:
        config = AppConfig(
            docs_dir=settings.DOCS_DIR,
            database_url=settings.DATABASE_URL,
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dimension=settings.EMBEDDING_DIMENSION,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            reranker_model=settings.RERANKER_MODEL,
            reranker_threshold=settings.RERANKER_THRESHOLD,
            lightrag_api_url=settings.LIGHTRAG_API_URL
        )
        service = RagService(config)
        result = service.sync_documents(force=force)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
