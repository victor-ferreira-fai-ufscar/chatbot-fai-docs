"""Fallback de RESILIÊNCIA: quando o LightRAG falha (fora do ar, timeout, erro ou
resposta vazia), responde pela base vetorial Supabase/pgvector (RagService legado)
com síntese no Ollama local. Modo DEGRADADO (sem grafo; reranker cross-encoder de CPU),
acionado SÓ quando o motor principal falha — melhor uma resposta fundamentada e mais
simples do que um erro ao usuário.

Independência do LightRAG: o RagService embeda a query com sentence-transformers em CPU
e busca no Postgres/pgvector, então sobrevive à queda do container LightRAG, do reranker
TEI/GPU e até do embedding do Ollama. A única dependência compartilhada é a síntese
(aqui, Ollama local via ctx.llm_settings).

Custo conhecido: o RagService carrega o bge-m3 em CPU (~90s no 1o uso), por isso é mantido
como SINGLETON de processo — paga o load uma vez e reusa. O import do RagService é LAZY
(sentence-transformers é pesado) para nunca onerar quem não aciona o fallback.
"""
from __future__ import annotations

import re
import threading

# Marcador de página inserido na ingestão page-aware ("[PAGINA N]" — sem acento no
# ingest_supabase.py). Fallback para extrair a página do texto se o campo `page` faltar.
_PAGE_RE = re.compile(r"\[P[ÁA]GINA\s+(\d{1,4})\]")

_singleton = None
_lock = threading.Lock()


def _get_service(config):
    """RagService singleton (thread-safe). O 1o acesso paga o load do bge-m3 (~90s)."""
    global _singleton
    with _lock:
        if _singleton is None:
            # Import LAZY: puxa sentence-transformers/torch só quando o fallback aciona.
            from src.chatbot_fai_docs.service import RagService
            _singleton = RagService(config)
        return _singleton


def answer_with_fallback(question, config, chat_settings, *, top_k: int = 6, max_sources: int = 4):
    """Responde pela base vetorial Supabase + Ollama. Retorna (texto, source_lines).

    As fontes vêm dos CHUNKS recuperados (campo `page` do ingest page-aware), NÃO da
    citação que o modelo escreve — mais robusto. O nome do arquivo é canonizado depois,
    no endpoint (canonicalize_source_line), quando há um único manual no bucket.
    Levanta em caso de falha do próprio fallback; o chamador decide como reportar."""
    svc = _get_service(config)
    # Recupera DIRETO pelo embedding (bge-m3), SEM o reranker cross-encoder de CPU do
    # RagService (ms-marco, treinado em ingles): ele reintroduz o MESMO gap lexical do
    # LightRAG (reforma != obra) e produz logits NEGATIVOS que o threshold 0.0 zera ->
    # contexto vazio. O embedding bge-m3 casa esses sinonimos (mesma licao do fallback
    # rerank-off do LightRAG), entao usamos os top_k por similaridade de embedding.
    from src.chatbot_fai_docs.config import is_retired_manual, retired_ilike_patterns
    retired = getattr(config, "retired_manual_patterns", ())
    query_embedding = svc.embedder.embed_query(question)
    # Exclui do fallback os chunks de manuais aposentados (seguem no pgvector p/
    # resiliencia, mas nao podem reaparecer numa resposta ao usuario).
    results = svc.vector_store.search(query_embedding, top_k=top_k,
                                      exclude_sources=retired_ilike_patterns(retired))

    from src.chatbot_fai_docs.pdfs import list_pdf_files
    available = [f.name for f in list_pdf_files(config.docs_dir)
                 if not is_retired_manual(f.name, retired)] if config.docs_dir.exists() else []

    # A síntese do Ollama chega como gerador de tuplas ("answer"/"thought"/"usage").
    # Só o canal "answer" vai ao usuário (o "thought" é raciocínio interno).
    gen = svc.chat_client.answer(
        question=question, search_results=results, chat_history=[],
        settings=chat_settings, available_docs=available,
    )
    texto = "".join(c for kind, c in gen if kind == "answer").strip()

    source_lines: list[str] = []
    seen: set = set()
    for r in results[:max_sources]:
        src = r.chunk.source
        page = r.chunk.page
        if not page:
            m = _PAGE_RE.search(r.chunk.content or "")
            page = int(m.group(1)) if m else None
        key = (src, page)
        if key in seen:
            continue
        seen.add(key)
        source_lines.append(f"- {src} (pág. {page})" if page else f"- {src}")
    return texto, source_lines
