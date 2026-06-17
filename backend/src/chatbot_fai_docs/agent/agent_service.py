"""AgentService: o laco de tool calling nativo, model-agnostic.

O `model` e injetado e deve expor `chat(messages, tools)` como um gerador de
tuplas no mesmo protocolo do `generate()` ja usado no projeto:
  ("thought", str) | ("answer", str) | ("tool_calls", list) | ("usage", int)

O laco emite, alem dessas, ("tool_status", nome_da_skill) durante a execucao.
A resposta final (turno SEM tool_calls) e emitida de uma vez como ("answer", ...).
"""
from __future__ import annotations

import json
from typing import Callable, Generator

from .types import AgentContext


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
                # turno sem ferramentas = resposta final
                yield ("answer", answer_buf)
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
