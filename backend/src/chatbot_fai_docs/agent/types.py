"""Tipos compartilhados do agente: o retorno de uma skill (SkillResult) e o
contexto da requisicao (AgentContext).

Tipos propositalmente FROUXOS (Any) para o pacote `agent` nao importar
pydantic/openai e permanecer testavel de forma isolada.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillResult:
    """Retorno de uma skill (handler kind=native).

    - for_model: texto que volta ao modelo como conteudo da mensagem `tool`.
    - sources:   linhas de fonte/citacao (ex.: do LightRAG) p/ o evento `done`.
    - downloads: pares (nome_arquivo, url_assinada) a oferecer como chips/links.
    - error:     marca que a execucao falhou (o texto do erro vai em for_model).
    """

    for_model: str
    sources: list = field(default_factory=list)
    downloads: list = field(default_factory=list)
    error: bool = False


@dataclass
class AgentContext:
    """Contexto de uma requisicao do agente, repassado a cada skill.

    Carrega dependencias (config, storage, historico) e ACUMULA efeitos
    colaterais (sources, downloads) que o endpoint emite no evento `done`.
    """

    config: Any = None
    storage: Any = None
    conversation_history: list = field(default_factory=list)
    history_turns: int = 5
    available_docs: list = field(default_factory=list)
    # acumuladores de efeitos colaterais (preenchidos via collect())
    sources: list = field(default_factory=list)
    downloads: list = field(default_factory=list)
    # espaco livre p/ skills guardarem estado entre passos do laco
    extras: dict = field(default_factory=dict)

    def collect(self, result: "SkillResult | None") -> None:
        """Agrega as fontes/downloads de um resultado de skill (com dedup de fontes)."""
        if result is None:
            return
        for s in result.sources:
            if s not in self.sources:
                self.sources.append(s)
        self.downloads.extend(result.downloads)
