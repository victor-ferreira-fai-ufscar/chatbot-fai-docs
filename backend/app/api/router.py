from fastapi import APIRouter
from app.api.endpoints import chat, history, documents

api_router = APIRouter()

api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(history.router, prefix="/history", tags=["Histórico"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documentos"])
