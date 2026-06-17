"""Skill consultar_base_conhecimento: LightRAG como ferramenta.

Envolve o LightRagService (variante NAO-stream `answer_question`) e devolve o
texto recuperado + as fontes citadas. `ctx.config` deve ser um AppConfig com o
`lightrag_api_url` ja resolvido (feito no endpoint, Fase 8.7).
"""
from src.chatbot_fai_docs.agent.types import AgentContext, SkillResult
from src.chatbot_fai_docs.lightrag_service import LightRagService

_VALID_MODES = {"mix", "hybrid", "local", "global"}


def executar(args: dict, ctx: AgentContext) -> SkillResult:
    consulta = (args.get("consulta") or "").strip()
    if not consulta:
        return SkillResult(
            for_model="Erro: a skill consultar_base_conhecimento requer o parametro 'consulta'.",
            error=True,
        )

    modo = (args.get("modo") or "mix").strip().lower()
    if modo not in _VALID_MODES:
        modo = "mix"

    if ctx.config is None:
        return SkillResult(
            for_model="Erro: configuracao do LightRAG indisponivel no contexto do agente.",
            error=True,
        )

    service = LightRagService(config=ctx.config)
    texto, source_lines = service.answer_question(
        consulta,
        modo,
        conversation_history=ctx.conversation_history,
        history_turns=ctx.history_turns,
    )

    if not texto:
        texto = (
            "A base de conhecimento nao retornou conteudo para esta consulta. "
            "Informe que o assunto nao consta nos manuais disponiveis ou peca para o "
            "usuario reformular."
        )
    return SkillResult(for_model=texto, sources=source_lines)
