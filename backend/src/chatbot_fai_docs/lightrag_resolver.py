from __future__ import annotations

import time
from typing import Optional

import requests

# Cache simples do endpoint ativo, para nao sondar a cada requisicao.
_cache: dict = {"url": None, "expiry": 0.0}


def _is_alive(url: str, timeout: float) -> bool:
    """Considera o LightRAG acessivel se /health (ou a raiz) responder sem erro de servidor."""
    for path in ("/health", ""):
        try:
            resp = requests.get(f"{url}{path}", timeout=timeout)
            if resp.status_code < 500:
                return True
        except Exception:
            continue
    return False


def resolve_lightrag_url(candidates: list[str], timeout: float = 1.5,
                         cache_ttl: float = 15.0) -> Optional[str]:
    """Retorna a primeira URL da lista diretamente, sem realizar a checagem de conexao."""
    if not candidates:
        return None
    return candidates[0]
