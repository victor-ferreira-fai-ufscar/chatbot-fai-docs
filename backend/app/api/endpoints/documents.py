import requests
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from app.core.config import settings
from src.chatbot_fai_docs import AppConfig, RagService
from src.chatbot_fai_docs.pdfs import list_pdf_files
from src.chatbot_fai_docs.storage_service import StorageService, StorageError
from src.chatbot_fai_docs.lightrag_resolver import resolve_lightrag_url
from pathlib import Path

router = APIRouter()


def get_storage() -> StorageService:
    """Factory do cliente de Storage; 503 se o Supabase Storage nao estiver configurado."""
    if not settings.SUPABASE_URL or not settings.SERVICE_ROLE_KEY:
        raise HTTPException(status_code=503, detail="Supabase Storage nao configurado (SUPABASE_URL/SERVICE_ROLE_KEY).")
    return StorageService(
        base_url=settings.SUPABASE_URL,
        service_key=settings.SERVICE_ROLE_KEY,
        bucket=settings.SUPABASE_BUCKET,
    )

@router.get("/")
async def list_documents():
    """Lista os nomes de todos os PDFs disponíveis na pasta sil."""
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
            lightrag_api_url=(resolve_lightrag_url(settings.lightrag_candidates()) or settings.LIGHTRAG_API_URL)
        )
        service = RagService(config)
        result = service.sync_documents(force=force)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), storage: StorageService = Depends(get_storage)):
    """Upload unificado: indexa o documento no LightRAG E o armazena no bucket do Supabase.

    Mantem os dois lados sincronizados — todo documento indexado fica disponivel para download.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    original_name = file.filename or "documento"
    content_type = file.content_type or "application/octet-stream"

    # 1) Encaminha para indexacao no LightRAG (nome original preservado)
    track_id = None
    try:
        lr_url = (resolve_lightrag_url(settings.lightrag_candidates()) or settings.LIGHTRAG_API_URL).rstrip("/")
        resp = requests.post(
            f"{lr_url}/documents/upload",
            files={"file": (original_name, content, content_type)},
            timeout=180,
        )
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"Falha ao indexar no LightRAG ({resp.status_code}): {resp.text}")
        try:
            track_id = resp.json().get("track_id")
        except Exception:
            track_id = None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao comunicar com o LightRAG: {e}")

    # 2) Sobe o mesmo arquivo para o bucket (nome sanitizado, deterministico)
    object_name = storage.sanitize_object_name(original_name)
    try:
        storage.upload(object_name, content, content_type=content_type, upsert=True)
    except StorageError as e:
        raise HTTPException(status_code=502, detail=f"Indexado no LightRAG, mas falhou no Storage: {e}")

    return {
        "status": "success",
        "filename": original_name,
        "object_name": object_name,
        "track_id": track_id,
    }


@router.get("/download-url")
async def get_download_url(name: str, storage: StorageService = Depends(get_storage)):
    """Gera uma URL assinada temporaria para baixar um documento do bucket.

    `name` pode ser o nome original (ex.: o citado nas fontes); a sanitizacao e
    deterministica, entao casa com o objeto armazenado no upload.
    """
    object_name = storage.sanitize_object_name(name)
    try:
        if not storage.exists(object_name):
            raise HTTPException(status_code=404, detail="Documento nao encontrado no repositorio.")
        signed_url = storage.create_signed_url(object_name, expires_in=settings.SIGNED_URL_TTL)
    except StorageError as e:
        raise HTTPException(status_code=502, detail=f"Erro no Storage: {e}")

    return {
        "filename": name,
        "object_name": object_name,
        "signed_url": signed_url,
        "expires_in": settings.SIGNED_URL_TTL,
    }


@router.get("/page-text")
async def get_page_text(name: str, page: int, storage: StorageService = Depends(get_storage)):
    """Texto limpo (layout-aware) de uma PAGINA do manual, para a sidebar de fontes.

    `name` e o nome citado nas fontes (ex.: 'Manual do Coordenador.pdf'); `page` e o
    numero de pagina citado (= ancora #page=N do PDF). Extrai com a mesma estrategia
    da re-indexacao (filtro por coordenada: descarta menu lateral, ordena 2 colunas),
    cacheado em memoria por objeto. Permite a sidebar mostrar o TRECHO-fonte real e
    destacar nele os termos da resposta, no estilo NotebookLM.
    """
    from src.chatbot_fai_docs.pdf_pages import get_page_text as _page_text

    object_name = storage.sanitize_object_name(name)
    try:
        if not storage.exists(object_name):
            raise HTTPException(status_code=404, detail="Documento nao encontrado no repositorio.")
        text = _page_text(object_name, page, lambda: storage.download(object_name))
    except StorageError as e:
        raise HTTPException(status_code=502, detail=f"Erro no Storage: {e}")

    return {"filename": name, "object_name": object_name, "page": page, "text": text}
