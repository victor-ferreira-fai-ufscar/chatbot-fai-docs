"""Cache de RESPOSTA no backend (consistência + latência) para a rota do chatbot.

Motivação: o LightRAG NÃO cacheia respostas em streaming (utils.py:2084 / ollama.py:174:
"cannot cache stream response and process reasoning"), e o chatbot usa /query/stream ->
o cache interno do LightRAG nunca atua na rota real. Além disso, o {{HORA_ATUAL}} (minuto)
entra no hash do cache do LightRAG e giraria a chave a cada minuto. Resultado prático:
toda pergunta re-roda a síntese NÃO-determinística (gpt-oss), o que produz o "às vezes
responde, às vezes não" para a MESMA pergunta.

Este cache resolve isso na camada do backend, com controle total da chave:
  - chave = (pergunta normalizada, modo, caminho agente/legado, versão-dos-manuais, versão-do-cache)
    SEM a hora -> estável dentro do dia (TTL).
  - um ACERTO devolve a resposta byte-a-byte idêntica -> consistência forte para repetições.

Política (decidida com o time):
  - SÓ cacheia 1º turno (sem histórico) -> nunca serve resposta de contexto multi-turno errado.
  - SÓ cacheia resposta FUNDAMENTADA (com fontes) e sem erro/truncamento -> nunca trava uma
    abstenção/instabilidade; a pergunta flaky continua tendo chance de acertar no próximo turno,
    e quando acerta, o resultado bom fica fixado.

Implementação: LRU + TTL em memória do processo (uso interno de baixo tráfego, 1 worker).
Limitação conhecida: não compartilha entre múltiplos workers e zera no restart do backend
(re-aquece rápido). Migrar para Postgres se um dia precisar persistir/compartilhar.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
import unicodedata
from collections import OrderedDict


def normalize_question(q: str) -> str:
    """Normaliza a pergunta para a CHAVE do cache: minúsculas, acentos removidos,
    pontuação -> espaço, espaços colapsados. Mantém dígitos (R$ 40.000 -> '40 000').
    Conservador o bastante para casar repetições reais sem colidir perguntas distintas."""
    q = (q or "").strip().lower()
    q = "".join(c for c in unicodedata.normalize("NFD", q) if unicodedata.category(c) != "Mn")
    q = re.sub(r"[^a-z0-9\s]", " ", q)
    return re.sub(r"\s+", " ", q).strip()


def manuals_version(manual_names) -> str:
    """Hash curto da lista de manuais disponíveis. Muda quando um manual entra/sai do
    bucket -> invalida o cache automaticamente. NÃO detecta reedição do MESMO arquivo
    (mesmo nome, conteúdo novo): para isso, suba RESPONSE_CACHE_VERSION na reindexação."""
    names = sorted(n for n in (manual_names or []) if n)
    return hashlib.sha256(" ".join(names).encode("utf-8")).hexdigest()[:12]


_PROMPT_FP_CACHE: dict = {}


def prompts_fingerprint(paths) -> str:
    """Hash curto do CONTEUDO dos arquivos de prompt (Prompt.md, Prompt_Skills.md),
    memoizado por mtime (custo ~zero por request). Entra na chave do cache: editar o
    prompt invalida o cache AUTOMATICAMENTE. Antes, a invalidacao dependia de bump
    manual de RESPONSE_CACHE_VERSION e era facil esquecer (respostas do prompt antigo
    eram servidas por ate 24h). A versao manual permanece p/ reindexacoes de documento."""
    parts = []
    for p in paths or []:
        try:
            st = p.stat()
            hit = _PROMPT_FP_CACHE.get(str(p))
            if hit and hit[0] == st.st_mtime_ns:
                parts.append(hit[1])
                continue
            h = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
            _PROMPT_FP_CACHE[str(p)] = (st.st_mtime_ns, h)
            parts.append(h)
        except OSError:
            parts.append("ausente")
    return "-".join(parts)


def make_key(question: str, mode: str, agent_on: bool, manual_names, cache_version: str,
             prompts_fp: str = "") -> str:
    payload = [normalize_question(question), (mode or "").lower(),
               "agent" if agent_on else "legacy", manuals_version(manual_names),
               str(cache_version or ""), str(prompts_fp or "")]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False).encode("utf-8")).hexdigest()


class ResponseCache:
    """LRU + TTL thread-safe. Guarda {key: (expires_at, {"answer","sources"})}."""

    def __init__(self, ttl_seconds: int = 86400, max_entries: int = 2000):
        self.ttl = ttl_seconds
        self.max = max_entries
        self._d: "OrderedDict[str, tuple]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str):
        now = time.time()
        with self._lock:
            item = self._d.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at < now:
                self._d.pop(key, None)
                return None
            self._d.move_to_end(key)  # LRU: marca como recém-usado
            return value

    def put(self, key: str, value: dict):
        with self._lock:
            self._d[key] = (time.time() + self.ttl, value)
            self._d.move_to_end(key)
            while len(self._d) > self.max:
                self._d.popitem(last=False)  # descarta o menos recentemente usado

    def clear(self):
        with self._lock:
            self._d.clear()
