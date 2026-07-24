"""Skill consultar_base_conhecimento: LightRAG como ferramenta.

Envolve o LightRagService (variante NAO-stream `answer_question`) e devolve o
texto recuperado + as fontes citadas. `ctx.config` deve ser um AppConfig com o
`lightrag_api_url` ja resolvido (feito no endpoint, Fase 8.7).
"""
from src.chatbot_fai_docs.agent.types import AgentContext, SkillResult
from src.chatbot_fai_docs.lightrag_service import LightRagService

_VALID_MODES = {"mix", "hybrid", "local", "global"}


def _build_query_rewriter(ctx: AgentContext):
    """Closure LAZY p/ o estagio de reformulacao da cascata de aprofundamento
    (lightrag_service._deepen_retrieval): so executa se a cascata chegar ao estagio
    de reformulacao (imports preguicosos; caminho feliz nao paga nada). None quando
    a flag esta off ou nao ha modelo auxiliar no contexto."""
    if not getattr(ctx.config, "query_rewrite_enabled", False) or ctx.llm_settings is None:
        return None

    def _rewriter(question: str):
        from src.chatbot_fai_docs.query_rewrite import pgvector_vocab_hints, rewrite_query
        hints = []
        if getattr(ctx.config, "query_rewrite_pgvector_hints", False):
            hints = pgvector_vocab_hints(question, ctx.config)
        return rewrite_query(question, ctx.llm_settings, hints)

    return _rewriter


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
            query_rewriter=_build_query_rewriter(ctx),
        )
    except Exception as e:
        # LightRAG fora do ar / timeout / erro: nao aborta a skill — deixa o fallback tentar.
        print(f"[consultar_base_conhecimento] LightRAG falhou: {type(e).__name__}: {e}")
        texto, source_lines = "", []

    # Contexto recuperado (chunks) p/ a verificacao de grounding do endpoint. Do LightRAG;
    # se cair no fallback pgvector abaixo, fica o que veio (ou vazio) -> verificacao pula
    # (fail-open). O verificador confere a resposta contra ESTES trechos, nao contra o texto
    # da pagina (que vazava no graph-RAG).
    ctx.extras["kb_context"] = getattr(service, "last_retrieved_context", "") or ""

    # Fallback de RESILIENCIA: quando o LightRAG falha OU retorna vazio, responde pela base
    # vetorial Supabase (pgvector) + sintese Ollama. So quando o principal nao entregou —
    # uma NEGATIVA legitima do LightRAG (texto nao-vazio) NAO aciona o fallback. Ver
    # supabase_fallback.py. Desligavel via SUPABASE_FALLBACK_ENABLED.
    # Variante RECALL (recall_channel_pgvector_enabled, OFF por padrao): tambem aciona
    # quando o LightRAG respondeu SEM fundamentar (texto sem nenhuma source_line — o
    # sinal deterministico de nao-fundamentada); so substitui se o fallback entregar.
    recall_channel = (getattr(ctx.config, "recall_channel_pgvector_enabled", False)
                      and texto and not source_lines)
    if (not texto or recall_channel) and \
            getattr(ctx.config, "supabase_fallback_enabled", False) and ctx.llm_settings:
        try:
            from src.chatbot_fai_docs.supabase_fallback import answer_with_fallback
            fb_texto, fb_sources = answer_with_fallback(consulta, ctx.config, ctx.llm_settings)
            if fb_texto and (not recall_channel or fb_sources):
                texto, source_lines = fb_texto, fb_sources
                print("[consultar_base_conhecimento] respondido pelo FALLBACK Supabase "
                      f"({'canal de recall' if recall_channel else 'modo contingencia'})")
        except Exception as e:
            print(f"[consultar_base_conhecimento] fallback Supabase falhou: {type(e).__name__}: {e}")

    if not texto:
        # 2a TENTATIVA determinística: na 1a consulta vazia do turno, instrui o modelo a
        # REFORMULAR e re-consultar (o laco tem max_steps=5, ha espaco) em vez de ir direto
        # a negativa — o gap lexical medido nas baterias se resolve com outra formulacao.
        # Da 2a em diante, a mensagem de negativa original (nao insistir para sempre).
        tries = ctx.extras.get("kb_empty_tries", 0) + 1
        ctx.extras["kb_empty_tries"] = tries
        if tries == 1:
            texto = (
                "A base de conhecimento nao retornou conteudo para ESTA formulacao. "
                "NAO aplique o protocolo de negativa ainda: reformule a consulta com "
                "sinonimos ou com o termo oficial provavel do manual (vocabulario "
                "formal, sem girias) e chame consultar_base_conhecimento novamente, "
                "UMA unica vez."
            )
        else:
            texto = (
                "A base de conhecimento nao retornou conteudo para esta consulta. "
                "Informe que o assunto nao consta nos manuais disponiveis, aplicando o "
                "protocolo de negativa (direcionamento ao Gestor do Projeto e, sem gestor "
                "designado, aos Supervisores de Projetos), ou peca para o usuario reformular."
            )
    return SkillResult(for_model=texto, sources=source_lines)
