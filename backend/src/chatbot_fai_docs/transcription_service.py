"""Transcricao de audio (Speech-to-Text) 100% local via OpenAI Whisper.

Motor: pacote `openai-whisper` (https://github.com/openai/whisper) rodando em
PyTorch. O modelo e carregado uma unica vez (singleton lazy, protegido por lock)
e reutilizado entre requisicoes — carregar o `medium` custa alguns segundos e
ocupa VRAM, entao nao queremos recarregar a cada chamada.

Dispositivo: por padrao `auto` — usa CUDA (GPU) se disponivel, senao CPU. Assim
o mesmo codigo roda na RTX do host (quando o container tem acesso a GPU) e cai
graciosamente para CPU quando nao tem, sem quebrar.
"""

from __future__ import annotations

import os
import threading
import tempfile
from typing import Optional


class TranscriptionError(Exception):
    """Erro ao transcrever audio (modelo indisponivel, ffmpeg ausente, etc.)."""


class TranscriptionService:
    """Wrapper singleton sobre o Whisper local.

    Uso:
        svc = TranscriptionService.instance()
        texto = svc.transcribe(audio_bytes, filename="audio.webm")
    """

    _instance: Optional["TranscriptionService"] = None
    _instance_lock = threading.Lock()

    def __init__(
        self,
        model_name: str = "medium",
        device: str = "auto",
        language: Optional[str] = "pt",
    ) -> None:
        self.model_name = model_name
        self.language = language or None
        self._requested_device = device
        self._model = None
        self._device = None
        self._load_lock = threading.Lock()

    # --- Singleton compartilhado entre requisicoes ----------------------------
    @classmethod
    def instance(cls) -> "TranscriptionService":
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls(
                        model_name=os.getenv("WHISPER_MODEL", "medium"),
                        device=os.getenv("WHISPER_DEVICE", "auto"),
                        language=os.getenv("WHISPER_LANGUAGE", "pt"),
                    )
        return cls._instance

    # --- Resolucao de dispositivo --------------------------------------------
    def _resolve_device(self) -> str:
        if self._requested_device and self._requested_device != "auto":
            return self._requested_device
        try:
            import torch

            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    # --- Carregamento preguicoso do modelo -----------------------------------
    def _ensure_model(self):
        if self._model is not None:
            return self._model
        with self._load_lock:
            if self._model is not None:
                return self._model
            try:
                import whisper
            except ImportError as e:
                raise TranscriptionError(
                    "Pacote 'openai-whisper' nao instalado no backend."
                ) from e
            self._device = self._resolve_device()
            try:
                self._model = whisper.load_model(self.model_name, device=self._device)
            except Exception as e:
                raise TranscriptionError(
                    f"Falha ao carregar o modelo Whisper '{self.model_name}' "
                    f"no dispositivo '{self._device}': {e}"
                ) from e
        return self._model

    def warmup(self) -> None:
        """Forca o carregamento do modelo (util no startup)."""
        self._ensure_model()

    @property
    def device(self) -> Optional[str]:
        return self._device

    # --- Transcricao ----------------------------------------------------------
    def transcribe(self, audio_bytes: bytes, filename: str = "audio") -> str:
        """Transcreve os bytes de um arquivo de audio e retorna o texto.

        O Whisper usa ffmpeg para decodificar o audio a partir de um caminho de
        arquivo, entao gravamos os bytes recebidos num arquivo temporario.
        """
        if not audio_bytes:
            raise TranscriptionError("Audio vazio.")

        model = self._ensure_model()
        # fp16 acelera na GPU; na CPU o Whisper avisa e ignora, entao desligamos.
        use_fp16 = self._device == "cuda"

        suffix = os.path.splitext(filename)[1] or ".webm"
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            result = model.transcribe(
                tmp_path,
                language=self.language,
                fp16=use_fp16,
            )
            return (result.get("text") or "").strip()
        except TranscriptionError:
            raise
        except Exception as e:
            raise TranscriptionError(f"Erro ao transcrever o audio: {e}") from e
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
