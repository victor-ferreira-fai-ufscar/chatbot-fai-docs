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
    try:
        texto, source_lines = service.answer_question(
            consulta,
            modo,
            conversation_history=ctx.conversation_history,
            history_turns=ctx.history_turns,
            # Sem isso, o {{LISTA_MANUAIS}} do user_prompt interno da skill caia no
            # fallback local e divergia do system prompt do agente (lista do bucket).
            available_docs=ctx.available_docs,
        )
    except Exception as e:
        # LightRAG fora do ar / timeout / erro: nao aborta a skill — deixa o fallback tentar.
        print(f"[consultar_base_conhecimento] LightRAG falhou: {type(e).__name__}: {e}")
        texto, source_lines = "", []

    # Fallback de RESILIENCIA: quando o LightRAG falha OU retorna vazio, responde pela base
    # vetorial Supabase (pgvector) + sintese Ollama. So quando o principal nao entregou —
    # uma NEGATIVA legitima do LightRAG (texto nao-vazio) NAO aciona o fallback. Ver
    # supabase_fallback.py. Desligavel via SUPABASE_FALLBACK_ENABLED.
    if not texto and getattr(ctx.config, "supabase_fallback_enabled", False) and ctx.llm_settings:
        try:
            from src.chatbot_fai_docs.supabase_fallback import answer_with_fallback
            texto, source_lines = answer_with_fallback(consulta, ctx.config, ctx.llm_settings)
            if texto:
                print("[consultar_base_conhecimento] respondido pelo FALLBACK Supabase (modo contingencia)")
        except Exception as e:
            print(f"[consultar_base_conhecimento] fallback Supabase falhou: {type(e).__name__}: {e}")

    if not texto:
        texto = (
            "A base de conhecimento nao retornou conteudo para esta consulta. "
            "Informe que o assunto nao consta nos manuais disponiveis, aplicando o "
            "protocolo de negativa (direcionamento ao Gestor do Projeto e, sem gestor "
            "designado, aos Supervisores de Projetos), ou peca para o usuario reformular."
        )
    return SkillResult(for_model=texto, sources=source_lines)
