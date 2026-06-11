"""Resolvedor de pedidos de download de documentos baseado em IA.

Em vez de casar o nome do arquivo por palavras-chave (fragil com pronomes como
"esse documento" ou referencias ao que foi citado antes), este modulo usa o LLM
para, a partir do historico da conversa + documentos citados na ultima resposta +
lista de documentos disponiveis no repositorio, decidir:

  - se o usuario esta de fato pedindo para BAIXAR/RECEBER um arquivo;
  - QUAL documento da lista ele quer (resolvendo referencias por contexto);
  - quando ambiguo, sinalizar que e preciso PERGUNTAR ao usuario qual documento.
"""

from __future__ import annotations

import json
import re
from pathlib import PurePosixPath

from src.IA.Models import OpenAIModel, GeminiModel, OllamaModel
from .llm import ChatSettings


_RESOLVER_SYSTEM = """Voce e um classificador. Sua unica tarefa e decidir se a mensagem atual do usuario e um pedido para BAIXAR/RECEBER o arquivo de um documento e, em caso afirmativo, identificar QUAL documento da lista disponivel ele deseja.

Use o historico da conversa: pedidos como "me envia esse documento", "pode mandar o manual", "quero baixar ele", "manda o anterior" referem-se ao documento discutido nos turnos anteriores ou citado na ultima resposta do assistente.

Responda SOMENTE com um objeto JSON valido, sem markdown, sem cercas de codigo e sem texto extra, no formato exato:
{"wants_download": bool, "object_name": string|null, "needs_clarification": bool, "candidates": [string]}

Regras:
- "wants_download" = true APENAS se o usuario pede claramente para RECEBER/BAIXAR o arquivo. Pedir um resumo, explicacao ou conteudo NAO conta como download.
- "object_name" deve ser EXATAMENTE um dos nomes da lista de documentos disponiveis, ou null se nenhuma correspondencia for clara.
- Se for um pedido de download mas voce nao conseguir identificar com seguranca qual documento (ambiguo, ou sem pista no contexto), defina "needs_clarification": true e preencha "candidates" com os nomes mais provaveis da lista (use a lista toda se nao houver nenhuma pista).
- Quando "object_name" for identificado com seguranca, deixe "needs_clarification": false.
- Se "wants_download" = false, use object_name=null, needs_clarification=false, candidates=[]."""


def _build_model(settings: ChatSettings):
    if settings.provider == "Ollama local":
        return OllamaModel(base_url=settings.base_url or "http://localhost:11434/v1", model_name=settings.model)
    if settings.provider == "Google Gemini":
        return GeminiModel(api_key=settings.api_key, model_name=settings.model)
    return OpenAIModel(api_key=settings.api_key, base_url=settings.base_url, model_name=settings.model)


def _consume_answer(result) -> str:
    """Junta o texto da resposta, ignorando chunks de 'thought'/'usage'."""
    if isinstance(result, str):
        return result
    text = ""
    for chunk in result:
        if isinstance(chunk, tuple):
            ctype, content = chunk
            if ctype == "answer":
                text += content
        else:
            text += chunk
    return text


def _extract_json(raw: str) -> dict:
    """Extrai o primeiro objeto JSON do texto bruto do modelo (tolerante a cercas)."""
    if not raw:
        return {}
    cleaned = raw.strip()
    # Remove cercas de codigo ```json ... ```
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE).strip()
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    # Fallback: pega o primeiro {...} que aparecer
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return {}
    return {}


def _empty_decision() -> dict:
    return {"wants_download": False, "object_name": None, "needs_clarification": False, "candidates": []}


def resolve_document_request(
    *,
    question: str,
    conversation_history: list[dict] | None,
    cited_sources: list[str],
    available_objects: list[str],
    settings: ChatSettings,
) -> dict:
    """Decide, via LLM, se/qual documento deve ser entregue.

    Retorna sempre um dict com as chaves: wants_download (bool), object_name
    (str|None, garantidamente presente em available_objects ou None),
    needs_clarification (bool) e candidates (list[str], subconjunto de available_objects).
    """
    if not available_objects:
        return _empty_decision()

    docs_block = "\n".join(f"- {name}" for name in available_objects)
    cited_block = "\n".join(f"- {s}" for s in cited_sources) if cited_sources else "(nenhuma)"

    user_prompt = (
        "Documentos disponiveis no repositorio (use o nome EXATO ao responder object_name):\n"
        f"{docs_block}\n\n"
        "Documentos citados na ultima resposta do assistente (pistas para 'esse documento'):\n"
        f"{cited_block}\n\n"
        f"Mensagem atual do usuario:\n{question}"
    )

    history = [
        {"role": m["role"], "content": m["content"]}
        for m in (conversation_history or [])[-6:]
        if m.get("role") in {"user", "assistant"}
    ]

    model = _build_model(settings)
    raw = _consume_answer(model.generate(system_prompt=_RESOLVER_SYSTEM, user_prompt=user_prompt, history=history))
    data = _extract_json(raw)
    if not data:
        return _empty_decision()

    wants = bool(data.get("wants_download"))
    if not wants:
        return _empty_decision()

    # Valida object_name: precisa existir na lista do bucket (casamento exato ou por basename).
    obj = data.get("object_name")
    object_name = _match_to_available(obj, available_objects) if obj else None

    # Sanitiza candidates para nomes que existem de fato no bucket.
    raw_candidates = data.get("candidates") or []
    candidates = []
    for c in raw_candidates:
        m = _match_to_available(c, available_objects)
        if m and m not in candidates:
            candidates.append(m)

    needs_clarification = bool(data.get("needs_clarification")) or object_name is None

    return {
        "wants_download": True,
        "object_name": object_name,
        "needs_clarification": needs_clarification and object_name is None,
        "candidates": candidates,
    }


def _match_to_available(name: str, available_objects: list[str]) -> str | None:
    """Mapeia um nome retornado pelo LLM para um objeto real do bucket.

    Tenta casamento exato; depois por basename (ignorando caminho); por fim
    ignorando diferencas de caixa.
    """
    if not name:
        return None
    if name in available_objects:
        return name
    target = PurePosixPath(name).name
    for obj in available_objects:
        if PurePosixPath(obj).name == target:
            return obj
    lowered = target.lower()
    for obj in available_objects:
        if PurePosixPath(obj).name.lower() == lowered:
            return obj
    return None
