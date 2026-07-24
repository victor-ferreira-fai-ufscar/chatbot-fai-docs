"""Verificacao de GROUNDING (2a opiniao) — rede de seguranca anti-alucinacao de
grounding PARCIAL de ALTO score.

O gate por score de recuperacao do endpoint pega o caso "fonte fraca" (trecho tangencial
recuperado com score baixo). Mas o pior caso e' o trecho tangencial com ALTO overlap
lexical: a pergunta usa um termo que aparece LITERALMENTE num trecho sobre OUTRO assunto,
o cross-encoder pontua alto, e o modelo INVENTA um procedimento a partir dele. Medido:
Q1 "como solicitar uma planilha orcamentaria" recuperou o trecho de BDI ("...na Planilha
Orcamentaria de obras...", pag. 65) a 64% e alucinou um passo a passo de solicitacao que
o manual NAO tem (regra 1.5(b) do Prompt: material tangencial -> token, sem oferecer como
consolo).

Aqui, apos uma resposta SUBSTANTIVA e FUNDAMENTADA, 1 chamada curta ao modelo LOCAL
confere se o NUCLEO da resposta (o procedimento/dado que ela afirma) REALMENTE aparece nos
trechos das PAGINAS CITADAS. So bloqueia (-> negativa) quando esta CLARO que a resposta
extrapolou; na DUVIDA mantem a resposta (default fundamentado) para nao super-abster. Toda
falha e' SUAVE (retorna True = nao bloqueia): o verificador nunca derruba uma resposta por
indisponibilidade propria. Mesmo padrao de chamada auxiliar do query_rewrite.py.
"""
from __future__ import annotations

import json

_VERIFY_SYSTEM = (
    "Voce e um verificador de FUNDAMENTACAO de respostas de um chatbot de manual "
    "institucional. Recebe uma PERGUNTA, os TRECHOS do manual (exatamente as paginas que a "
    "resposta citou) e a RESPOSTA gerada por outro assistente. Decida se o NUCLEO da "
    "RESPOSTA — o procedimento, os passos, os valores ou as afirmacoes que ela apresenta "
    "como sendo do manual — REALMENTE aparece nos TRECHOS. "
    "Marque fundamentado=false APENAS quando estiver CLARO que a resposta afirma um "
    "procedimento/dado que NAO esta nos trechos — o caso tipico: a pergunta pede COMO fazer "
    "ou COMO solicitar algo, os trechos apenas DEFINEM ou MENCIONAM esse algo (sem ensinar "
    "o procedimento) e a resposta INVENTA um passo a passo. "
    "Se os trechos sustentam o nucleo (ainda que a resposta parafraseie, organize ou "
    "resuma), marque fundamentado=true. Uma resposta que apenas OBSERVA que o manual nao "
    "detalha um ponto tambem e fundamentado=true. Na DUVIDA, responda fundamentado=true. "
    "Responda SOMENTE um JSON valido, sem comentarios: "
    '{"fundamentado": true|false, "motivo": "frase curta"}'
)


def _consume_text(out) -> str:
    """model.generate devolve str OU gerador de tuplas; so o canal 'answer' importa
    (mesmo helper do query_rewrite.py)."""
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
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(text[start:end + 1])
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def answer_is_grounded(question: str, answer: str, excerpts: str, llm_settings,
                       *, max_answer_chars: int = 2400, max_excerpt_chars: int = 5000) -> bool:
    """True = manter a resposta (fundamentada ou duvida); False = APENAS quando o modelo
    afirma CLARAMENTE que o nucleo nao esta nos trechos. Falha suave -> True."""
    try:
        answer = (answer or "").strip()
        excerpts = (excerpts or "").strip()
        if not answer or not excerpts:
            return True  # sem material p/ julgar -> nao bloqueia
        from src.IA.Models import OllamaModel, OpenAIModel
        if llm_settings.provider == "Ollama local":
            model = OllamaModel(base_url=llm_settings.base_url or "http://localhost:11434/v1",
                                model_name=llm_settings.model)
        else:
            model = OpenAIModel(api_key=llm_settings.api_key,
                                base_url=llm_settings.base_url,
                                model_name=llm_settings.model)

        user = (
            f"PERGUNTA:\n{question}\n\n"
            f"TRECHOS DO MANUAL (paginas citadas na resposta):\n{excerpts[:max_excerpt_chars]}\n\n"
            f"RESPOSTA GERADA:\n{answer[:max_answer_chars]}"
        )
        text = _consume_text(model.generate(system_prompt=_VERIFY_SYSTEM,
                                            user_prompt=user, history=[]))
        data = _extract_json(text)
        if not data or "fundamentado" not in data:
            return True  # veredito ilegivel -> nao bloqueia (conservador)
        grounded = bool(data.get("fundamentado"))
        if not grounded:
            print(f"[grounding_verify] NAO fundamentado: {str(data.get('motivo'))[:120]!r}",
                  flush=True)
        return grounded
    except Exception as e:
        print(f"[grounding_verify] falhou (fail-open): {type(e).__name__}: {e}", flush=True)
        return True
