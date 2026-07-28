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
        ia_dir = Path(__file__).resolve().parent.parent / "IA"
        prompt_path = ia_dir / "Prompt.md"
        if prompt_path.exists():
            self.system_prompt_base = prompt_path.read_text(encoding="utf-8").strip()
        else:
            self.system_prompt_base = (
                "Voce e um assistente para consulta de manuais institucionais.\n"
                "Responda em portugues do Brasil. Use apenas o contexto fornecido quando ele for suficiente.\n"
                "Se a resposta nao estiver clara nos trechos recuperados, diga isso explicitamente e indique a limitacao."
            )
        # Protocolo de Skills (modo agente, Fase 8): carregado de um arquivo SEPARADO
        # para NAO poluir o Prompt.md compartilhado com o fluxo RAG legado. Anexado
        # apenas por build_agent_system_prompt(). Bind-mounted -> editavel sem rebuild.
        skills_prompt_path = ia_dir / "Prompt_Skills.md"
        self.skills_protocol_base = (
            skills_prompt_path.read_text(encoding="utf-8").strip()
            if skills_prompt_path.exists() else ""
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
            # NOTA para o fluxo de CONTINGENCIA (Supabase/pgvector): aqui os trechos NAO
            # trazem os marcadores [PÁGINA N] citados na regra de citacao do prompt — a
            # pagina vem no cabecalho 'Pagina: N' de cada trecho. Sem esta nota, a regra
            # do prompt seria mecanicamente falsa neste fluxo.
            "NOTA DE SISTEMA (fluxo de contingencia): os trechos acima NAO contem marcadores "
            "[PÁGINA N]; a pagina de cada trecho esta no cabecalho 'Pagina: N'. Ao usar "
            "informacoes do contexto, use esse numero na linha final de fonte: "
            "'> Fonte: [arquivo.pdf, pág. N]'."
        )

        user_prompt = f"Pergunta do usuario:\n{question}"

        if settings.provider == "Ollama local":
            model = OllamaModel(base_url=settings.base_url or "http://localhost:11434/v1", model_name=settings.model)
        elif settings.provider == "Google Gemini":
            model = GeminiModel(api_key=settings.api_key, model_name=settings.model)
        else:
            model = OpenAIModel(api_key=settings.api_key, base_url=settings.base_url, model_name=settings.model)

        return model.generate(system_prompt=system_prompt, user_prompt=user_prompt, history=history_messages)

    def answer_conversational(
        self,
        *,
        question: str,
        chat_history: list[dict[str, str]],
        settings: ChatSettings,
        available_docs: list[str] | None = None,
    ) -> Any:
        """Resposta para turnos puramente sociais (saudacao, agradecimento,
        despedida, pergunta sobre quem e a Lina) que NAO exigem busca documental.

        Usa a mesma persona do RAG, porem SEM bloco de contexto recuperado e com
        uma nota de sistema deixando claro que este turno e conversacional: assim
        a Lina nao dispara o protocolo de negativa ("nao encontrei nos manuais")
        nem tenta inventar conteudo. Retorna o mesmo gerador de tuplas
        (("answer"|"thought"|"usage", ...)) que o endpoint ja consome."""
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
            "NOTA DE SISTEMA (turno conversacional): esta mensagem do usuario e uma "
            "interacao social (saudacao, agradecimento, despedida ou pergunta sobre "
            "quem voce e e o que faz). NAO ha consulta a documentos neste turno, e "
            "isso e esperado e correto. Responda de forma breve e cordial como a "
            "Lina. NAO aplique o protocolo de negativa (nao diga que 'nao encontrou "
            "nos manuais'), NAO invente conteudo de manuais e NAO cite fontes. Se "
            "for saudacao ou pergunta sobre voce, apresente-se brevemente e ofereca "
            "ajuda; se for agradecimento ou despedida, responda com cordialidade."
        )

        user_prompt = f"Mensagem do usuario:\n{question}"

        if settings.provider == "Ollama local":
            model = OllamaModel(base_url=settings.base_url or "http://localhost:11434/v1", model_name=settings.model)
        elif settings.provider == "Google Gemini":
            model = GeminiModel(api_key=settings.api_key, model_name=settings.model)
        else:
            model = OpenAIModel(api_key=settings.api_key, base_url=settings.base_url, model_name=settings.model)

        return model.generate(system_prompt=system_prompt, user_prompt=user_prompt, history=history_messages)

    def build_agent_system_prompt(self, available_docs: list[str] | None = None) -> str:
        """System prompt do AGENTE (Fase 8): a mesma persona (Lina) do RAG, com os
        placeholders preenchidos, porem SEM bloco de contexto recuperado — no modo
        agente o contexto factual vem da skill consultar_base_conhecimento. Anexa o
        Protocolo de Skills (arquivo separado) que reorienta a ancoragem para o
        RESULTADO das skills. As instrucoes detalhadas de cada skill chegam via
        disclosure progressivo no proprio laco (nao aqui)."""
        date_str, time_str = get_current_date_time_pt_br()
        docs_str = ", ".join(available_docs) if available_docs else "Nenhum documento detectado."

        prompt_with_vars = (
            self.system_prompt_base
            .replace("{{DATA_ATUAL}}", date_str)
            .replace("{{HORA_ATUAL}}", time_str)
            .replace("{{LISTA_MANUAIS}}", docs_str)
        )
        if self.skills_protocol_base:
            return f"{prompt_with_vars}\n\n{self.skills_protocol_base}"
        return prompt_with_vars

    @staticmethod
    def _clean_title(raw: str, fallback: str = "") -> str:
        """Higieniza o título devolvido pelo modelo.

        Modelos pequenos (OLLAMA_TITLE_MODEL é de propósito um modelo enxuto)
        desobedecem o "sem aspas" do system prompt e às vezes prefixam
        "Título:" ou devolvem mais de uma linha. Nada disso pode vazar para o
        rótulo da sidebar, então a limpeza é feita aqui e não no prompt.
        """
        title = (raw or "").strip()
        # Só a primeira linha não-vazia (modelo pode "explicar" o título embaixo).
        for line in title.splitlines():
            if line.strip():
                title = line.strip()
                break
        # Prefixo rotulado ("Titulo: X" / "Título - X").
        low = title.lower()
        for pref in ("titulo:", "título:", "titulo -", "título -"):
            if low.startswith(pref):
                title = title[len(pref):].strip()
                break
        # Aspas envolventes (retas, curvas e angulares).
        pairs = (('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’"), ("«", "»"))
        for _ in range(2):  # pode vir aspas duplicada: «"X"»
            for op, cl in pairs:
                if len(title) >= 2 and title.startswith(op) and title.endswith(cl):
                    title = title[1:-1].strip()
                    break
        title = " ".join(title.split())  # colapsa espaços/quebras internas
        if not title:
            return (fallback[:30] + "...") if fallback else "Nova conversa"
        # Teto de tamanho: o modelo pequeno às vezes ecoa a pergunta inteira.
        return title if len(title) <= 60 else title[:57].rstrip() + "..."

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
            return self._clean_title(full_title, question)

        return self._clean_title(title, question)
