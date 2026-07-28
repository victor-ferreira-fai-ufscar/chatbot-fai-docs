"""Reformulação CANÔNICA de query (estágio da cascata de aprofundamento do retrieval).

Traduz uma pergunta coloquial/sintomática para o vocabulário FORMAL dos manuais
("numerozinho vermelho no topo da tela" -> "ícone de notificações"), o modo de falha
nº 1 do retrieval medido nas baterias (prova A/B: COORD-15 coloquial = negativa;
reformulada canônica = acerto pág. 59 a 88%). Determinístico no ACIONAMENTO (o
handler injeta; a cascata decide quando chamar), com 1 chamada curta ao modelo
auxiliar local (OLLAMA_MODEL) — mesmo padrão do ChatClient.generate_title.

Também devolve keywords hi/low-level enviadas POR REQUEST ao LightRAG, pulando a
extração de keywords do gpt-oss no re-probe (a parte lenta do retry).

Dicas de vocabulário (opcional): top-k chunks do pgvector/Supabase — o embedding
bge-m3 atravessa o gap lexical que mata o cross-encoder. Os trechos NUNCA chegam à
síntese nem ao usuário; só orientam a reescrita (risco de citação zero). Custo
conhecido: o 1º uso paga o load do bge-m3 em CPU (~90s, singleton do processo —
mesmo do supabase_fallback).

Toda falha é SUAVE (retorna None/[]): a cascata simplesmente pula o estágio.
"""
from __future__ import annotations

import json
import re

# Remove o marcador de página da ingestão page-aware antes de usar o trecho como dica.
_PAGE_MARK_RE = re.compile(r"\[P[ÁA]GINA\s+\d{1,4}\]")

_REWRITE_SYSTEM = (
    "Voce reescreve perguntas coloquiais no VOCABULARIO FORMAL de manuais "
    "administrativos institucionais, para melhorar a busca documental. Regras: "
    "NAO invente siglas nem conteudo; preserve valores, nomes de sistemas, "
    "formularios e setores; troque termos coloquiais/sintomaticos pelo termo "
    "oficial provavel. PRESERVE o TIPO e o OBJETO da pergunta: pergunta de "
    "justificativa/motivo ('por que', 'qual a justificativa') continua perguntando "
    "o MOTIVO — nunca a converta em pergunta de procedimento ('como', 'quando') "
    "nem troque o objeto por um tema vizinho (a busca responderia OUTRA pergunta). "
    "Responda SOMENTE um JSON valido, sem comentarios: "
    '{"consulta": "pergunta reescrita", "hl_keywords": ["2-4 temas amplos"], '
    '"ll_keywords": ["3-6 termos/entidades especificos"]}'
)


def pgvector_vocab_hints(question: str, config, k: int = 3) -> list:
    """Top-k trechos do pgvector como glossário p/ o reformulador. Falha suave -> [].

    Load frio: o 1º uso do singleton pagaria ~90s de load do bge-m3 CPU DENTRO do
    orçamento da skill (TOOL_TIMEOUT_S) — somado à síntese think=high, estouraria o
    timeout. Se o singleton ainda não subiu, dispara o load em thread de fundo e
    devolve [] nesta consulta (o rewrite roda sem glossário); as próximas usam."""
    try:
        if not getattr(config, "database_url", None):
            return []
        # Reusa o singleton do fallback (evita 2º load do bge-m3 CPU). Import lazy:
        # sentence-transformers é pesado e só quem chega a este estágio paga.
        import threading

        from src.chatbot_fai_docs import supabase_fallback
        from src.chatbot_fai_docs.supabase_fallback import _get_service
        if supabase_fallback._singleton is None:
            threading.Thread(target=_get_service, args=(config,), daemon=True).start()
            print("[query_rewrite] bge-m3 frio: aquecendo em background; hints pulados nesta consulta",
                  flush=True)
            return []
        svc = _get_service(config)
        from src.chatbot_fai_docs.config import retired_ilike_patterns
        results = svc.vector_store.search(
            svc.embedder.embed_query(question), top_k=k,
            exclude_sources=retired_ilike_patterns(getattr(config, "retired_manual_patterns", ())))
        hints = []
        for r in results:
            content = _PAGE_MARK_RE.sub(" ", r.chunk.content or "")
            snippet = " ".join(content.split())[:240]
            if snippet:
                hints.append(snippet)
        return hints
    except Exception as e:
        print(f"[query_rewrite] hints pgvector indisponiveis: {type(e).__name__}: {e}", flush=True)
        return []


def _consume_text(out) -> str:
    """model.generate devolve str OU gerador de tuplas; só o canal 'answer' importa."""
    if isinstance(out, str):
        return out
    full = ""
    for chunk in out:
        if isinstance(chunk, tuple):
            kind, content = chunk
            if kind == "answer":
                full += content
        else:
            full += str(chunk)
    return full


def _extract_json(text: str) -> dict | None:
    """Primeiro objeto {...} do texto (o modelo às vezes envolve em cercas/markdown)."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def rewrite_query(question: str, llm_settings, vocab_hints: list | None = None):
    """-> (consulta, hl_keywords, ll_keywords) ou None (falha suave / sem ganho)."""
    try:
        from src.IA.Models import OllamaModel, OpenAIModel
        if llm_settings.provider == "Ollama local":
            model = OllamaModel(base_url=llm_settings.base_url or "http://localhost:11434/v1",
                                model_name=llm_settings.model)
        else:
            model = OpenAIModel(api_key=llm_settings.api_key,
                                base_url=llm_settings.base_url,
                                model_name=llm_settings.model)

        user = f"Pergunta original: {question}"
        if vocab_hints:
            user += ("\n\nTrechos dos manuais sobre o tema (use ESTE vocabulario na "
                     "reescrita):\n" + "\n".join(f"- {h}" for h in vocab_hints))

        text = _consume_text(model.generate(system_prompt=_REWRITE_SYSTEM,
                                            user_prompt=user, history=[]))
        data = _extract_json(text)
        if not data:
            return None
        consulta = str(data.get("consulta") or "").strip()
        hl = [str(x).strip() for x in (data.get("hl_keywords") or []) if str(x).strip()]
        ll = [str(x).strip() for x in (data.get("ll_keywords") or []) if str(x).strip()]
        # Sem reescrita útil (vazia ou idêntica) -> None; a cascata pula o estágio.
        if not consulta or consulta.strip().lower() == question.strip().lower():
            return None
        print(f"[query_rewrite] {question[:60]!r} -> {consulta[:80]!r} "
              f"(hl={len(hl)} ll={len(ll)} hints={len(vocab_hints or [])})", flush=True)
        return consulta, hl, ll
    except Exception as e:
        print(f"[query_rewrite] falhou: {type(e).__name__}: {e}", flush=True)
        return None
