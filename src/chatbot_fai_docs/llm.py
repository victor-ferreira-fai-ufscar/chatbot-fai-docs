from __future__ import annotations
from typing import Any
from dataclasses import dataclass
from pathlib import Path
from .models import SearchResult
from ..IA.Models import OpenAIModel, GeminiModel, OllamaModel


@dataclass(frozen=True)
class ChatSettings:
    provider: str
    api_key: str
    model: str
    base_url: str | None = None


def build_context(search_results: list[SearchResult]) -> str:
    if not search_results:
        return "Nenhum trecho relevante foi recuperado."

    parts: list[str] = []
    for item in search_results:
        parts.append(
            f"Fonte: {item.chunk.source} | Pagina: {item.chunk.page} | Similaridade: {item.score:.3f}\n"
            f"Trecho: {item.chunk.content}"
        )
    return "\n\n".join(parts)


class ChatClient:
    def __init__(self):
        prompt_path = Path(__file__).resolve().parent.parent / "IA" / "Prompt.md"
        if prompt_path.exists():
            self.system_prompt_base = prompt_path.read_text(encoding="utf-8").strip()
        else:
            self.system_prompt_base = (
                "Voce e um assistente para consulta de manuais institucionais.\n"
                "Responda em portugues do Brasil. Use apenas o contexto fornecido quando ele for suficiente.\n"
                "Se a resposta nao estiver clara nos trechos recuperados, diga isso explicitamente e indique a limitacao."
            )

    def answer(
        self,
        *,
        question: str,
        search_results: list[SearchResult],
        chat_history: list[dict[str, str]],
        settings: ChatSettings,
    ) -> Any:
        context = build_context(search_results)

        history_messages = [
            {"role": item["role"], "content": item["content"]}
            for item in chat_history[-6:]
            if item["role"] in {"user", "assistant"}
        ]

        system_prompt = (
            f"{self.system_prompt_base}\n\n"
            "Contexto recuperado dos documentos:\n"
            f"{context}\n\n"
            "Ao responder, cite o nome do arquivo e a pagina quando usar informacoes do contexto."
        )

        user_prompt = f"Pergunta do usuario:\n{question}"

        if settings.provider == "Ollama local":
            model = OllamaModel(base_url=settings.base_url or "http://localhost:11434/v1", model_name=settings.model)
        elif settings.provider == "Google Gemini":
            model = GeminiModel(api_key=settings.api_key, model_name=settings.model)
        else:
            model = OpenAIModel(api_key=settings.api_key, base_url=settings.base_url, model_name=settings.model)

        return model.generate(system_prompt=system_prompt, user_prompt=user_prompt, history=history_messages)
