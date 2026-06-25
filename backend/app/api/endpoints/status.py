"""Endpoint de status/saude da stack.

Existe para que o frontend exiba um indicador de conexao (bolinha verde/vermelha)
do servico de RAG. Diferente da raiz `/` (que so confirma que o backend subiu),
aqui SONDAMOS o LightRAG via /health.

ALCANCE (importante para nao prometer demais): /health e uma checagem de LIVENESS
do servidor LightRAG (processo no ar + config), nao de READINESS de geracao. Ele
responde 200 mesmo com o LLM (Ollama) saturado ou sem VRAM. Portanto "online" aqui
significa "servico acessivel", e NAO "a resposta vai sair rapido". Falhas durante a
geracao (timeout de sintese) aparecem como erro no proprio chat, nao neste indicador.
"""
import time

import requests
from fastapi import APIRouter

from app.core.config import settings
from src.chatbot_fai_docs.lightrag_resolver import resolve_lightrag_url

router = APIRouter()

# Cache curto do resultado da sondagem: o frontend faz polling (a cada ~15s) e pode
# haver varios navegadores abertos. Sem cache, cada poll vira uma chamada ao /health
# do LightRAG. 5s de TTL mantem o indicador "ao vivo" sem martelar o servico.
_PROBE_TTL_S = 5.0
_cache: dict = {"at": 0.0, "value": None}


def _probe_lightrag(url: str, timeout: float = 4.0) -> dict:
    """Sonda GET {url}/health. Online = HTTP 200. Falha de rede / timeout / >=500
    contam como offline, com um `detail` curto para diagnostico (sem vazar segredos)."""
    headers = {}
    if settings.LIGHTRAG_API_KEY:
        headers["X-API-Key"] = settings.LIGHTRAG_API_KEY
    try:
        resp = requests.get(f"{url}/health", timeout=timeout, headers=headers)
    except requests.exceptions.Timeout:
        return {"status": "offline", "url": url, "detail": "timeout"}
    except requests.exceptions.RequestException as e:
        # Nome da excecao (ConnectionError etc.) — nao o texto, que pode conter a URL/host.
        return {"status": "offline", "url": url, "detail": type(e).__name__}

    if resp.status_code != 200:
        return {"status": "offline", "url": url, "detail": f"HTTP {resp.status_code}"}

    # 200: online. Tenta extrair o modelo de sintese p/ enriquecer o tooltip da UI.
    model = None
    try:
        model = (resp.json().get("configuration") or {}).get("llm_model")
    except Exception:
        pass
    detail = f"modelo: {model}" if model else "healthy"
    return {"status": "online", "url": url, "detail": detail, "model": model}


@router.get("")
@router.get("/")
def get_status():
    """Estado agregado da stack para o indicador de conexao do frontend.

    O backend responder ja prova que ele esta no ar (`backend: "ok"`); o campo
    `lightrag` reflete a sondagem real do servico de RAG."""
    now = time.monotonic()
    if _cache["value"] is not None and (now - _cache["at"]) < _PROBE_TTL_S:
        return _cache["value"]

    # Sondamos sempre o LightRAG: e o unico motor de RAG ativo (o caminho Supabase
    # esta desativado, ver chat.py). Se um dia DEFAULT_RAG_ENGINE deixar de ser
    # LightRAG, este probe precisara ramificar por engine.
    url = resolve_lightrag_url(settings.lightrag_candidates())
    if url:
        lightrag = _probe_lightrag(url)
    else:
        lightrag = {"status": "offline", "url": None, "detail": "sem endpoint configurado"}

    value = {
        "backend": "ok",
        "rag_engine": settings.DEFAULT_RAG_ENGINE,
        "lightrag": lightrag,
    }
    _cache["at"] = now
    _cache["value"] = value
    return value
