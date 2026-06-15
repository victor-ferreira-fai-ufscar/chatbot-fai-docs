"""Endpoints de audio — transcricao de voz (Speech-to-Text) via Whisper local."""

from fastapi import APIRouter, HTTPException, UploadFile, File
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from src.chatbot_fai_docs.transcription_service import (
    TranscriptionService,
    TranscriptionError,
)

router = APIRouter()

# Limite defensivo de tamanho do audio enviado (perguntas de voz sao curtas).
MAX_AUDIO_BYTES = 25 * 1024 * 1024  # 25 MB


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Recebe um arquivo de audio e retorna a transcricao em texto.

    Roda 100% local com o Whisper (`WHISPER_MODEL`, default `medium`). A
    inferencia e bloqueante (CPU/GPU intensiva), entao executa num threadpool
    para nao travar o event loop.
    """
    if not settings.WHISPER_ENABLED:
        raise HTTPException(status_code=503, detail="Transcricao de audio desativada.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Arquivo de audio vazio.")
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio muito grande (limite de 25 MB).")

    service = TranscriptionService.instance()
    try:
        text = await run_in_threadpool(
            service.transcribe, content, file.filename or "audio"
        )
    except TranscriptionError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro inesperado na transcricao: {e}")

    return {"text": text, "device": service.device}
