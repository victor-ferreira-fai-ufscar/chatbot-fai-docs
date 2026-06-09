from __future__ import annotations
from typing import Any
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from .models import SearchResult
from src.IA.Models import OpenAIModel, GeminiModel, OllamaModel


from .utils import get_current_date_time_pt_br


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
        available_docs: list[str] | None = None,
    ) -> Any:
        context = build_context(search_results)

        history_messages = [
            {"role": item["role"], "content": item["content"]}
            for item in chat_history[-6:]
            if item["role"] in {"user", "assistant"}
        ]

        date_str, time_str = get_current_date_time_pt_br()
        docs_str = ", ".join(available_docs) if available_docs else "Nenhum documento detectado."
        
        prompt_with_vars = (
            self.system_prompt_base
            .replace("{{DATA_ATUAL}}", date_str)
            .replace("{{HORA_ATUAL}}", time_str)
            .replace("{{LISTA_MANUAIS}}", docs_str)
        )

        system_prompt = (
            f"{prompt_with_vars}\n\n"
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

    def generate_title(self, question: str, settings: ChatSettings) -> str:
        """Gera um título curto para a conversa baseado na primeira pergunta."""
        system_prompt = "Voce e um assistente que gera titulos curtos e descritivos. Responda apenas com o titulo, sem aspas, com no maximo 5 palavras."
        user_prompt = f"Gere um titulo para esta pergunta: {question}"

        if settings.provider == "Ollama local":
            model = OllamaModel(base_url=settings.base_url or "http://localhost:11434/v1", model_name=settings.model)
        elif settings.provider == "Google Gemini":
            model = GeminiModel(api_key=settings.api_key, model_name=settings.model)
        else:
            model = OpenAIModel(api_key=settings.api_key, base_url=settings.base_url, model_name=settings.model)

        # Usar o método de geração sem stream para o título
        title = model.generate(system_prompt=system_prompt, user_prompt=user_prompt, history=[])
        
        # Caso retorne um gerador (stream), extrair o conteúdo
        if not isinstance(title, str):
            full_title = ""
            for chunk in title:
                if isinstance(chunk, tuple):
                    ctype, content = chunk
                    # Ignora chunks de metadados (ex.: ("usage", <int>)); só texto entra no título
                    if ctype == "answer":
                        full_title += content
                else:
                    full_title += chunk
            return full_title.strip()
        
        return title.strip()
