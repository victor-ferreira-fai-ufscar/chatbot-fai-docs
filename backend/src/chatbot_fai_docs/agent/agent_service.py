"""AgentService: o laco de tool calling nativo, model-agnostic.

O `model` e injetado e deve expor `chat(messages, tools)` como um gerador de
tuplas no mesmo protocolo do `generate()` ja usado no projeto:
  ("thought", str) | ("answer", str) | ("tool_calls", list) | ("usage", int)

O laco emite, alem dessas, ("tool_status", nome_da_skill) durante a execucao.
A resposta final (turno SEM tool_calls) e emitida de uma vez como ("answer", ...).
"""
from __future__ import annotations

import json
import re
from typing import Callable, Generator

from .types import AgentContext


# --- Sanitizacao do formato de canais de raciocinio ("harmony") -------------
# Alguns modelos de raciocinio (ex.: servidos via Ollama) as vezes colocam o
# canal `analysis` (raciocinio interno, formato "harmony") no `content` em vez do
# `reasoning_content`, fazendo o "plano" vazar para o usuario. Aqui garantimos
# que SO o canal `final` saia. Conservador: so age quando ha marcadores claros;
# respostas normais passam intactas.
#
# Formatos observados (capturas reais, multi-turno):
#   proper:       <|channel|>analysis<|message|>...<|channel|>final<|message|>RESPOSTA
#   degradado (a): thought\n{raciocinio}<channel|>{resposta final}
#   degradado (b): thought\n<channel|>{so raciocinio, sem final claro}
_CHAN = r"<\|?channel\|?>"
_MSG = r"<\|?message\|?>"
_STRUCT = r"<\|?(?:channel|message|start|end|return)\|?>"
# nome de canal "isolado": seguido de <|message|>, quebra de linha ou fim de texto
# (evita casar uma resposta que por acaso comece com a palavra, ex.: "Final: ...").
_NAME_GUARD = r"(?=\s*(?:" + _MSG + r"|\r?\n|$))"

_FINAL_RE = re.compile(
    _CHAN + r"\s*(?:assistant\s*)?final" + _NAME_GUARD + r"\s*(?:" + _MSG + r")?", re.I
)
_NAMED_CHANNEL_RE = re.compile(
    _CHAN + r"\s*(?:assistant\s*)?(?:analysis|commentary|final)" + _NAME_GUARD, re.I
)
_ANY_CHANNEL_RE = re.compile(_CHAN, re.I)
_STRUCT_RE = re.compile(_STRUCT, re.I)
# marcador que ENCERRA o conteudo do canal final (qualquer um, menos <|message|>)
_NEXT_STRUCT_RE = re.compile(r"<\|?(?:channel|start|end|return)\|?>", re.I)
# "thought" sozinho na linha (ou colado a um marcador) — assinatura do vazamento;
# nao casa um texto normal que comece com "Thought: ..." ou "Thoughts".
_LEADING_THOUGHT_RE = re.compile(r"^\s*thought\b[ \t]*(?:\r?\n|(?=<\|?))", re.I)
_LEADING_CHANNEL_NAME_RE = re.compile(
    r"^\s*(?:assistant|developer|system|user)?\s*(?:analysis|commentary|final)\b[ \t]*\r?\n?", re.I
)

# Quando so ha raciocinio (sem canal `final` claro), preferimos uma mensagem
# segura a vazar o plano interno ao usuario.
_HARMONY_FALLBACK = (
    "Desculpe, tive um problema ao formular a resposta. Pode reformular a pergunta?"
)


def _bound_final(rest: str) -> str:
    """Limita o conteudo do canal final ao proximo marcador estrutural (se houver),
    para nunca arrastar um canal seguinte (ex.: um analysis posterior)."""
    cut = _NEXT_STRUCT_RE.search(rest)
    return rest[: cut.start()] if cut else rest


def sanitize_harmony(text: str) -> str:
    """Remove artefatos do formato de canais "harmony", entregando so o canal `final`.

    - Sem marcadores harmony  => devolve o texto inalterado (resposta normal).
    - Com canal `final`       => devolve apenas o conteudo desse canal.
    - So `analysis`/`commentary` (sem final) => devolve um fallback seguro, para
      nunca vazar o raciocinio interno ao usuario.
    """
    if not text:
        return text
    if not (_LEADING_THOUGHT_RE.match(text) or _STRUCT_RE.search(text)):
        return text  # resposta normal — nao mexer

    if _NAMED_CHANNEL_RE.search(text):
        # Harmony "proper": confie nos nomes de canal.
        finals = list(_FINAL_RE.finditer(text))
        if not finals:
            return _HARMONY_FALLBACK  # so analysis/commentary => sem resposta limpa
        body = _bound_final(text[finals[-1].end():])
    else:
        # Degradado (sem nome de canal). Discriminador ESTRUTURAL entre os casos:
        #   (a) thought\n{raciocinio}<channel|>{final}  -> HA texto antes do canal
        #   (b) thought\n<channel|>{raciocinio}          -> NADA antes do canal
        had_thought = bool(_LEADING_THOUGHT_RE.match(text))
        body = _LEADING_THOUGHT_RE.sub("", text, count=1)
        first = _ANY_CHANNEL_RE.search(body)
        if first is None:
            pass  # marcadores soltos sem canal: cai na limpeza generica abaixo
        elif had_thought and body[: first.start()].strip() == "":
            return _HARMONY_FALLBACK  # assinatura do caso (b): so raciocinio
        else:
            last = None
            for m in _ANY_CHANNEL_RE.finditer(body):
                last = m
            body = _bound_final(body[last.end():])

    body = _LEADING_THOUGHT_RE.sub("", body, count=1)
    body = _LEADING_CHANNEL_NAME_RE.sub("", body)
    body = _STRUCT_RE.sub("", body)  # marcadores residuais
    cleaned = body.strip()
    return cleaned or _HARMONY_FALLBACK


def to_openai_tool_calls(tool_calls: list[dict]) -> list[dict]:
    """Converte [{id, name, arguments(dict)}] -> formato OpenAI da msg `assistant`."""
    out = []
    for tc in tool_calls:
        out.append(
            {
                "id": tc.get("id") or "",
                "type": "function",
                "function": {
                    "name": tc.get("name") or "",
                    "arguments": json.dumps(tc.get("arguments") or {}, ensure_ascii=False),
                },
            }
        )
    return out


def history_to_messages(history: list[dict]) -> list[dict]:
    """Converte o historico (user/assistant) em mensagens do chat."""
    out = []
    for m in history or []:
        role = m.get("role")
        if role in ("user", "assistant") and m.get("content"):
            out.append({"role": role, "content": m["content"]})
    return out


class AgentService:
    def __init__(
        self,
        model,
        registry,
        *,
        max_steps: int = 5,
        instructions_mode: str = "preamble",
        system_prompt_builder: Callable[[AgentContext], str] | None = None,
    ):
        self.model = model
        self.registry = registry
        self.max_steps = max_steps
        self.instructions_mode = instructions_mode
        # O system prompt real (persona Lina + Protocolo de Skills) e montado na
        # integracao do endpoint (Fase 8.7); aqui ele e injetavel p/ testabilidade.
        self._build_system_prompt = system_prompt_builder or (lambda ctx: "")

    def run_stream(
        self, question: str, conversation_history: list[dict], ctx: AgentContext
    ) -> Generator[tuple, None, None]:
        messages: list[dict] = []
        system_prompt = self._build_system_prompt(ctx)
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages += history_to_messages(conversation_history)
        messages.append({"role": "user", "content": question})

        schemas = self.registry.schemas
        instructed: set[str] = set()  # skills cujas instrucoes ja foram injetadas (disclosure)

        for _step in range(self.max_steps):
            answer_buf = ""
            tool_calls = None
            for kind, payload in self.model.chat(messages, tools=schemas):
                if kind == "thought":
                    yield ("thought", payload)
                elif kind == "answer":
                    answer_buf += payload
                elif kind == "tool_calls":
                    tool_calls = payload
                elif kind == "usage":
                    yield ("usage", payload)

            if not tool_calls:
                # turno sem ferramentas = resposta final. Sanitiza aqui (texto ja
                # bufferizado) para garantir que o raciocinio interno (formato
                # "harmony") nunca vaze ao usuario.
                yield ("answer", sanitize_harmony(answer_buf))
                return

            # registra a intencao do assistente e executa cada skill
            messages.append(
                {
                    "role": "assistant",
                    "content": answer_buf or None,
                    "tool_calls": to_openai_tool_calls(tool_calls),
                }
            )
            for call in tool_calls:
                name = call.get("name") or ""
                yield ("tool_status", name)
                result = self.registry.dispatch(name, call.get("arguments") or {}, ctx)
                ctx.collect(result)

                content = result.for_model
                # disclosure progressivo (modo preamble): na 1a vez que uma skill e
                # usada, injetamos suas instrucoes detalhadas junto do resultado.
                if self.instructions_mode == "preamble" and name not in instructed:
                    instr = self.registry.instructions_for(name)
                    if instr:
                        content = f"[Instrucoes da skill '{name}']\n{instr}\n\n[Resultado]\n{content}"
                    instructed.add(name)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id") or "",
                        "content": content,
                    }
                )

        yield ("answer", "Nao consegui concluir a tarefa em tempo habil. Pode reformular?")
