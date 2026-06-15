from fastapi import APIRouter
from app.api.endpoints import chat, history, documents, audio

api_router = APIRouter()

api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
api_router.include_router(history.router, prefix="/history", tags=["Histórico"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documentos"])
api_router.include_router(audio.router, prefix="/audio", tags=["Áudio"])
