from __future__ import annotations

from dataclasses import dataclass

from openai import OpenAI

from .models import SearchResult


@dataclass(frozen=True)
class ChatSettings:
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
    def answer(
        self,
        *,
        question: str,
        search_results: list[SearchResult],
        chat_history: list[dict[str, str]],
        settings: ChatSettings,
    ) -> str:
        client = OpenAI(api_key=settings.api_key, base_url=settings.base_url or None)
        context = build_context(search_results)

        history_messages = [
            {"role": item["role"], "content": item["content"]}
            for item in chat_history[-6:]
            if item["role"] in {"user", "assistant"}
        ]

        response = client.chat.completions.create(
            model=settings.model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Voce e um assistente para consulta de manuais institucionais. "
                        "Responda em portugues do Brasil. Use apenas o contexto fornecido quando ele for suficiente. "
                        "Se a resposta nao estiver clara nos trechos recuperados, diga isso explicitamente e indique a limitacao."
                    ),
                },
                *history_messages,
                {
                    "role": "user",
                    "content": (
                        "Pergunta do usuario:\n"
                        f"{question}\n\n"
                        "Contexto recuperado dos documentos:\n"
                        f"{context}\n\n"
                        "Ao responder, cite o nome do arquivo e a pagina quando usar informacoes do contexto."
                    ),
                },
            ],
        )

        return (
            response.choices[0].message.content
            or "Nao foi possivel gerar uma resposta."
        )
