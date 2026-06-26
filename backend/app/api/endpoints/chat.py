import json
import re
import time
import requests
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from app.core.config import settings
from app.schemas.chat_schema import ChatRequest
from src.chatbot_fai_docs import AppConfig, RagService
from src.chatbot_fai_docs.llm import ChatSettings, ChatClient
from src.chatbot_fai_docs.repository import get_repo_from_url
from src.chatbot_fai_docs.lightrag_service import LightRagService
from src.chatbot_fai_docs.lightrag_resolver import resolve_lightrag_url
from src.chatbot_fai_docs.smalltalk_gate import is_smalltalk
from src.chatbot_fai_docs.storage_service import StorageService
from src.chatbot_fai_docs.document_resolver import resolve_document_request

router = APIRouter()

# Pre-filtro barato (regex) para decidir se vale a pena acionar o resolvedor de
# documentos por IA — evita uma chamada extra de LLM em perguntas puramente
# informativas. A decisao final (intencao real + qual documento) e do LLM.
# Sem \b final para casar conjugacoes (enviar, baixar, compartilhar...).
DOWNLOAD_INTENT_RE = re.compile(
    r"(?i)\b(envi[ae]|mand[ae]|baix[ae]|download|compartilh[ae]|disponibiliz[ae]|"
    r"me\s+passa|quero|gostaria|preciso|obter)"
)
DOC_NOUN_RE = re.compile(r"(?i)\b(arquivo|documento|manual|pdf|c[oó]pia|material)\b")
# Pronomes/referencias que apontam para um documento ja mencionado no contexto
# (ex.: "me envia esse documento", "manda ele", "quero o anterior").
DOC_REF_RE = re.compile(
    r"(?i)\b(esse|essa|este|esta|aquele|aquela|isso|ele|ela|anterior|"
    r"citad[oa]|mencionad[oa]|acima|mesmo)\b"
)


def _maybe_download_request(question: str) -> bool:
    """Pre-filtro: ha verbo de envio/obtencao + um alvo (substantivo de documento
    OU um pronome/referencia)? Se sim, o resolvedor por IA decide o resto."""
    has_verb = bool(DOWNLOAD_INTENT_RE.search(question))
    has_target = bool(DOC_NOUN_RE.search(question) or DOC_REF_RE.search(question))
    return has_verb and has_target


def _bucket_manual_names(storage=None) -> list:
    """Lista os documentos disponiveis a partir do bucket 'manuais' do Supabase
    Storage (fonte da verdade), em vez de uma pasta local. Alimenta {{LISTA_MANUAIS}}
    no system prompt. Retorna [] se o Storage estiver indisponivel ou em erro."""
    try:
        if storage is None:
            if not (settings.SUPABASE_URL and settings.SERVICE_ROLE_KEY):
                return []
            storage = StorageService(
                base_url=settings.SUPABASE_URL,
                service_key=settings.SERVICE_ROLE_KEY,
                bucket=settings.SUPABASE_BUCKET,
            )
        return [o.get("name", "") for o in storage.list_objects(limit=100) if o.get("name")]
    except Exception:
        return []


def _run_agent(config, question: str, conversation_history: list):
    """Monta o AgentService (laco de tool calling + Skills) e devolve
    (gerador_de_tuplas, AgentContext). O ctx e populado DURANTE a iteracao do
    gerador (sources/downloads coletados a cada skill), entao leia ctx.sources /
    ctx.downloads APOS consumir o gerador. Imports do agente sao preguicosos para
    que o fluxo legado (AGENT_ENABLED=False) nunca os carregue."""
    from src.chatbot_fai_docs.agent import AgentService, ToolRegistry, AgentContext
    from src.IA.Models import OllamaModel, OpenAIModel, GeminiModel

    # Documentos disponiveis = objetos do bucket 'manuais' do Supabase (fonte da
    # verdade), nao uma pasta local. Mesmo conjunto que a skill entregar_documento usa.
    storage = None
    temp_storage = None
    manual_names: list = []
    if settings.SUPABASE_URL and settings.SERVICE_ROLE_KEY:
        storage = StorageService(
            base_url=settings.SUPABASE_URL,
            service_key=settings.SERVICE_ROLE_KEY,
            bucket=settings.SUPABASE_BUCKET,
        )
        manual_names = _bucket_manual_names(storage)
        # Bucket separado para os documentos GERADOS (temporarios). As skills de
        # geracao sobem aqui; entregar_documento continua lendo de `storage` (manuais).
        temp_storage = StorageService(
            base_url=settings.SUPABASE_URL,
            service_key=settings.SERVICE_ROLE_KEY,
            bucket=settings.SUPABASE_TEMP_BUCKET,
        )

    llm_settings = ChatSettings(
        provider="Ollama local" if not settings.OPENAI_API_KEY else "OpenAI API",
        api_key="ollama" if not settings.OPENAI_API_KEY else settings.OPENAI_API_KEY,
        model=settings.OLLAMA_MODEL if not settings.OPENAI_API_KEY else "gpt-4o-mini",
        base_url=settings.OLLAMA_BASE_URL if not settings.OPENAI_API_KEY else None,
    )
    if llm_settings.provider == "Ollama local":
        model = OllamaModel(base_url=llm_settings.base_url or "http://localhost:11434/v1", model_name=llm_settings.model)
    elif llm_settings.provider == "Google Gemini":
        model = GeminiModel(api_key=llm_settings.api_key, model_name=llm_settings.model)
    else:
        model = OpenAIModel(api_key=llm_settings.api_key, base_url=llm_settings.base_url, model_name=llm_settings.model)

    registry = ToolRegistry.from_dir(settings.SKILLS_DIR, tool_timeout_s=settings.TOOL_TIMEOUT_S)
    ctx = AgentContext(
        config=config,
        storage=storage,
        temp_storage=temp_storage,
        llm_settings=llm_settings,
        conversation_history=conversation_history,
        history_turns=settings.HISTORY_TURNS,
        signed_url_ttl=settings.SIGNED_URL_TTL,
        available_docs=manual_names,
    )
    chat_client = ChatClient()
    agent = AgentService(
        model,
        registry,
        max_steps=settings.MAX_TOOL_STEPS,
        instructions_mode=settings.SKILL_INSTRUCTIONS_MODE,
        system_prompt_builder=lambda c: chat_client.build_agent_system_prompt(c.available_docs),
    )
    return agent.run_stream(question, conversation_history, ctx), ctx


def get_repo():
    # Persistencia do historico independe do motor RAG: usa Postgres se DATABASE_URL
    # estiver configurado, senao cai no repo em memoria (fallback de desenvolvimento).
    repo = get_repo_from_url(settings.DATABASE_URL)
    # ensure_ready is a no-op for in-memory repo
    repo.ensure_ready()
    return repo

@router.post("/stream")
async def chat_stream(request: ChatRequest, repo = Depends(get_repo)):
    """
    Endpoint de chat com streaming. Usa LightRAG por padrão; também suporta mecanismos alternativos se configurados.
    """
    
    def generate_response():
        start_time = time.perf_counter()
        conversation_id = request.conversation_id
        # "Modo Agentico" por requisicao: a UI pode desligar o agente (tool calling + Skills)
        # para testar alucinacao. None -> usa o default do servidor (AGENT_ENABLED). Com o
        # agente desligado, NAO ha geracao de planilha/PDF/DOCX (skills) — so o RAG direto.
        agent_on = request.agentic if request.agentic is not None else settings.AGENT_ENABLED

        # 1. Preparar Contexto (resolve o LightRAG acessivel entre os candidatos)
        lightrag_api_url = resolve_lightrag_url(settings.lightrag_candidates())
        config = AppConfig(
            docs_dir=settings.DOCS_DIR,
            database_url=settings.DATABASE_URL,
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dimension=settings.EMBEDDING_DIMENSION,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            reranker_model=settings.RERANKER_MODEL,
            reranker_threshold=settings.RERANKER_THRESHOLD,
            lightrag_api_url=lightrag_api_url,
            lightrag_api_key=settings.LIGHTRAG_API_KEY,
            rerank_url=settings.RERANK_URL,
        )

        # Carregar historico anterior da conversa (turnos previos) para dar contexto ao LightRAG.
        # A pergunta atual NAO entra aqui; ela vai separada no parametro `query`.
        try:
            prior = repo.get_messages(conversation_id, request.user_id) if conversation_id else []
            conversation_history = [
                {"role": m.role, "content": m.content}
                for m in prior if m.role in ("user", "assistant")
            ][-(settings.HISTORY_TURNS * 2):]
        except Exception as e:
            print(f"Erro ao carregar historico: {e}")
            conversation_history = []

        # Lista de manuais reais (objetos do bucket) — alimenta {{LISTA_MANUAIS}} no prompt
        # e o nome canonico das citacoes. Uma unica consulta, reutilizada nos dois usos.
        manual_names = _bucket_manual_names()

        # Citacao (estilo "responder" do WhatsApp): se o usuario mencionou uma mensagem
        # anterior, ela e anexada como contexto explicito a pergunta enviada ao LightRAG.
        # A pergunta original (sem o bloco de citacao) e o que fica salvo no historico;
        # a citacao em si e guardada no metadata da mensagem do usuario.
        effective_question = request.question
        quoted_meta = None
        if request.quoted and request.quoted.content.strip():
            quoted_meta = {"role": request.quoted.role, "content": request.quoted.content}
            quoted_label = "assistente" if request.quoted.role == "assistant" else "usuario"
            quoted_snippet = request.quoted.content.strip()[:1200]
            effective_question = (
                f"[O usuario esta se referindo a esta mensagem anterior do {quoted_label}]:\n"
                f"\"\"\"\n{quoted_snippet}\n\"\"\"\n\n"
                f"Com base nessa mensagem citada, responda:\n{request.question}"
            )

        # Roteamento. Com AGENT_ENABLED, o AGENTE (laco de tool calling + Skills)
        # decide a cada turno se/qual skill usar — incl. consultar o LightRAG SO quando
        # ha necessidade documental. Desligado (default), segue o fluxo fixo atual
        # (gate social + LightRAG), permitindo rollback instantaneo via flag.
        agent_ctx = None
        try:
            if agent_on:
                answer, agent_ctx = _run_agent(config, effective_question, conversation_history)
            else:
                # Gate conversacional: turnos puramente sociais (oi, obrigado, "quem e voce?")
                # respondem direto pelo modelo auxiliar, SEM acionar o LightRAG (economiza o
                # custo de retrieval nesses turnos). Conservador: nunca pula quando ha citacao
                # de mensagem (quoted) ou intencao de download, e o gate so casa mensagens
                # 100% sociais — na duvida, cai no LightRAG.
                use_smalltalk_gate = (
                    settings.SMALLTALK_GATE_ENABLED
                    and not request.quoted
                    and not _maybe_download_request(request.question)
                    and is_smalltalk(request.question)
                )
                if use_smalltalk_gate:
                    manual_names = _bucket_manual_names()
                    gate_settings = ChatSettings(
                        provider="Ollama local" if not settings.OPENAI_API_KEY else "OpenAI API",
                        api_key="ollama" if not settings.OPENAI_API_KEY else settings.OPENAI_API_KEY,
                        model=settings.OLLAMA_MODEL if not settings.OPENAI_API_KEY else "gpt-4o-mini",
                        base_url=settings.OLLAMA_BASE_URL if not settings.OPENAI_API_KEY else None,
                    )
                    answer = ChatClient().answer_conversational(
                        question=request.question,
                        chat_history=conversation_history,
                        settings=gate_settings,
                        available_docs=manual_names,
                    )
                    source_lines = []
                else:
                    # Fluxo padrao: LightRAG (Grafo). Supabase/Postgres desativado.
                    lightrag_service = LightRagService(config=config)
                    answer, _, source_lines = lightrag_service.answer_question_stream(
                        effective_question,
                        request.mode,
                        conversation_history=conversation_history,
                        history_turns=settings.HISTORY_TURNS,
                        available_docs=manual_names,
                    )
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return

        # 2. Processar Resposta (Streaming ou String)
        full_answer = ""
        last_usage = 0

        # Guard determinístico anti-alucinação de referência legal: descarta frases que
        # citem norma cujo número-base não exista no manual (ex.: ISS Lei 116/2003 inventada).
        # Casa pelo número-base, então mantém leis que o manual referencia. Ver legal_guard.py.
        from src.chatbot_fai_docs.legal_guard import LegalRefGuard, manual_law_numbers
        from src.chatbot_fai_docs.pdf_pages import _extract_pages as _law_pages
        from src.chatbot_fai_docs.source_citation import canonical_manual_name, normalize_source_citations, canonicalize_source_line
        _law_storage = None
        if settings.SUPABASE_URL and settings.SERVICE_ROLE_KEY:
            try:
                _law_storage = StorageService(base_url=settings.SUPABASE_URL,
                                              service_key=settings.SERVICE_ROLE_KEY,
                                              bucket=settings.SUPABASE_BUCKET)
            except Exception:
                _law_storage = None
        guard = LegalRefGuard(manual_law_numbers(_law_storage, _law_pages))

        # Nome canonico do manual (a partir dos documentos REAIS do bucket) para normalizar
        # as citacoes "> Fonte: [...]" que o modelo escreve no corpo da resposta — impede
        # nome de arquivo fabricado (ex.: "M-coordenadoresFAI-01-06_1.pdf"). Sem canonico,
        # o normalizador remove o nome e mantem so a pagina. Ver source_citation.py.
        _canon = canonical_manual_name(manual_names)
        _canon_display = _canon.replace("_", " ") if _canon else None
        def _fix_cites(text: str) -> str:
            # page_shift=1 SO no fluxo RAG: o rodape do PDF marca o FIM da pagina, entao o
            # trecho citado e da pagina seguinte. Mantem a citacao inline consistente com a
            # pagina dos cards (que tambem somam +1). No agente as fontes vem por outro
            # caminho (agent_ctx), entao nao deslocamos aqui para nao criar divergencia.
            return normalize_source_citations(text, _canon_display, page_shift=(0 if agent_on else 1))

        # A CONSUMICAO do gerador e onde o streaming do LightRAG realmente acontece
        # (a chamada de rede e preguicosa). O try/except acima so cobre a INVOCACAO;
        # uma falha NO MEIO do stream (timeout do socket numa sintese lenta, ou o
        # servidor encerrando a conexao) subiria sem evento e o stream morreria mudo —
        # o usuario via a resposta truncar sem aviso (o "problema de conexao" percebido).
        # Capturamos aqui para emitir uma mensagem clara e ainda finalizar/persistir o
        # que ja foi gerado.
        try:
            if agent_on:
                # Consumer dedicado do agente: mapeia as tuplas do laco para eventos SSE.
                # 'thought' (raciocinio do modelo) e suprimido; 'tool_status' vai como
                # evento proprio (o frontend ignora por ora; vira chip "Consultando..." depois).
                for kind, payload in answer:
                    if kind == "usage":
                        last_usage = payload
                    elif kind == "answer":
                        cleaned = _fix_cites(guard.feed(payload))
                        if cleaned:
                            full_answer += cleaned
                            yield f"data: {json.dumps({'content': cleaned})}\n\n"
                    elif kind == "tool_status":
                        yield f"data: {json.dumps({'tool_status': payload})}\n\n"
                    # 'thought' suprimido de proposito (nao vai ao usuario)
                tail = _fix_cites(guard.flush())
                if tail:
                    full_answer += tail
                    yield f"data: {json.dumps({'content': tail})}\n\n"
                source_lines = agent_ctx.sources if agent_ctx else []
                # Downloads produzidos por skills (entregar_documento/gerar_*) -> links inline
                # em Markdown, no MESMO formato do fluxo legado (sem mudar o frontend).
                for nome, url in (agent_ctx.downloads if agent_ctx else []):
                    link_md = f"\n\n📎 [Baixar **{nome}**]({url})"
                    full_answer += link_md
                    yield f"data: {json.dumps({'content': link_md})}\n\n"
            elif isinstance(answer, str):
                full_answer = _fix_cites(guard.feed(answer) + guard.flush())
                yield f"data: {json.dumps({'content': full_answer, 'sources': source_lines})}\n\n"
            else:
                # Gerador de streaming
                for item in answer:
                    chunk_content = ""
                    if isinstance(item, tuple):
                        ctype, content = item
                        if ctype == "usage":
                            last_usage = content
                            continue
                        chunk_content = content
                    else:
                        chunk_content = item

                    cleaned = _fix_cites(guard.feed(chunk_content))
                    if cleaned:
                        full_answer += cleaned
                        yield f"data: {json.dumps({'content': cleaned})}\n\n"
                tail = _fix_cites(guard.flush())
                if tail:
                    full_answer += tail
                    yield f"data: {json.dumps({'content': tail})}\n\n"
        except Exception as e:
            # Log completo no servidor (tipo + mensagem) para diagnostico; ao usuario,
            # so um aviso amigavel. Segue o fluxo (entrega de doc + persistencia) com o
            # texto parcial ja gerado, em vez de derrubar a conexao sem explicacao.
            print(f"Erro durante o streaming da resposta: {type(e).__name__}: {e}")
            aviso = (
                "\n\n_A conexão com a base de conhecimento foi interrompida durante a "
                "geração da resposta. Tente novamente em instantes._"
            )
            full_answer += aviso
            yield f"data: {json.dumps({'content': aviso})}\n\n"

        # 2.1. Entrega de documento (FLUXO LEGADO): se o usuario pediu para receber/baixar
        # um manual, um resolvedor por IA identifica QUAL documento ele quer e anexa um link
        # assinado ao final da resposta. No modo agente, isso e feito pela skill
        # entregar_documento (decisao do agente), entao este bloco e pulado.
        if (not agent_on and settings.SUPABASE_URL and settings.SERVICE_ROLE_KEY
                and _maybe_download_request(request.question)):
            try:
                storage = StorageService(
                    base_url=settings.SUPABASE_URL,
                    service_key=settings.SERVICE_ROLE_KEY,
                    bucket=settings.SUPABASE_BUCKET,
                )
                object_names = [o.get("name", "") for o in storage.list_objects(limit=100) if o.get("name")]

                resolver_settings = ChatSettings(
                    provider="Ollama local" if not settings.OPENAI_API_KEY else "OpenAI API",
                    api_key="ollama" if not settings.OPENAI_API_KEY else settings.OPENAI_API_KEY,
                    model=settings.OLLAMA_MODEL if not settings.OPENAI_API_KEY else "gpt-4o-mini",
                    base_url=settings.OLLAMA_BASE_URL if not settings.OPENAI_API_KEY else None,
                )
                decision = resolve_document_request(
                    question=effective_question,
                    conversation_history=conversation_history,
                    cited_sources=source_lines,
                    available_objects=object_names,
                    settings=resolver_settings,
                )

                if decision.get("wants_download"):
                    matched = decision.get("object_name")
                    if matched:
                        signed_url = storage.create_signed_url(matched, expires_in=settings.SIGNED_URL_TTL)
                        link_md = f"\n\n📎 [Baixar **{matched}**]({signed_url})"
                        full_answer += link_md
                        yield f"data: {json.dumps({'content': link_md})}\n\n"
                    else:
                        # Pedido de download ambiguo: perguntar ao usuario qual documento enviar.
                        candidates = decision.get("candidates") or object_names
                        candidates = [c for c in candidates if c in object_names][:8]
                        listed = "\n".join(f"- {c}" for c in candidates)
                        ask_md = (
                            "\n\nNão consegui identificar com certeza qual documento você deseja baixar. "
                            "Poderia me dizer qual destes você quer?\n\n" + listed
                        )
                        full_answer += ask_md
                        yield f"data: {json.dumps({'content': ask_md})}\n\n"
            except Exception as e:
                print(f"Erro ao resolver/anexar documento: {e}")

        # Unifica o nome exibido nas fontes (cards) com o nome canonico citado no texto,
        # quando ha um unico manual — evita "dois nomes para o mesmo documento" (LightRAG
        # cita 'Manual do Coordenador.pdf'; o bucket guarda 'Manual_dos_Coordenadores.pdf').
        if _canon_display and len(manual_names) == 1 and source_lines:
            source_lines = [canonicalize_source_line(s, _canon_display) for s in source_lines]

        # 3. Finalizar e Salvar no Backend
        final_time = time.perf_counter() - start_time
        
        try:
            # Gerar título se for nova conversa
            if not conversation_id:
                chat_client = ChatClient()
                # Simplificação: Usar gpt-4o-mini ou modelo local para título
                title_settings = ChatSettings(
                    provider="Ollama local" if not settings.OPENAI_API_KEY else "OpenAI API",
                    api_key="ollama" if not settings.OPENAI_API_KEY else settings.OPENAI_API_KEY,
                    model=settings.OLLAMA_MODEL if not settings.OPENAI_API_KEY else "gpt-4o-mini",
                    base_url=settings.OLLAMA_BASE_URL if not settings.OPENAI_API_KEY else None
                )
                try:
                    suggested_title = chat_client.generate_title(request.question, title_settings)
                except Exception as e:
                    print(f"Erro ao gerar título: {e}")
                    suggested_title = request.question[:30] + "..."
                
                conversation_id = repo.create_conversation(
                    title=suggested_title,
                    rag_engine=request.rag_engine,
                    user_id=request.user_id,
                )
                repo.add_message(conversation_id, "user", request.question,
                                 metadata={"quoted": quoted_meta} if quoted_meta else None)
            else:
                # Conversa existente: persistir a pergunta deste turno (faltava antes)
                repo.add_message(conversation_id, "user", request.question,
                                 metadata={"quoted": quoted_meta} if quoted_meta else None)

            # Salvar resposta da IA
            repo.add_message(
                conversation_id, 
                "assistant", 
                full_answer, 
                metadata={
                    "sources": source_lines,
                    "gen_time": final_time,
                    "usage": last_usage
                }
            )
            
            # Enviar evento final com metadados
            yield f"data: {json.dumps({'done': True, 'conversation_id': conversation_id, 'gen_time': final_time, 'usage': last_usage, 'sources': source_lines})}\n\n"
        except Exception as e:
            print(f"Erro ao persistir histórico: {e}")
            yield f"data: {json.dumps({'error': 'Erro ao salvar histórico: ' + str(e)})}\n\n"

    return StreamingResponse(generate_response(), media_type="text/event-stream")

@router.get("/ollama/models")
async def get_ollama_models():
    """
    Busca os modelos locais disponíveis no Ollama.
    """
    # Usando o padrão /api/tags que é a API correta do Ollama
    base_url = settings.OLLAMA_BASE_URL.rstrip("/") if hasattr(settings, "OLLAMA_BASE_URL") and settings.OLLAMA_BASE_URL else "http://localhost:11434"
    # Ajuste: se a URL terminar em /v1, removemos pois tags fica em /api/tags
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]
        
    try:
        url = f"{base_url}/api/tags"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = []
            for item in data.get("models", []):
                name = item.get("name", "")
                param_size = item.get("details", {}).get("parameter_size", "unknown")
                models.append({"name": name, "label": f"{name} ({param_size})"})
            return models
        else:
            return []
    except Exception as e:
        print(f"Erro ao buscar modelos Ollama: {e}")
        return []
